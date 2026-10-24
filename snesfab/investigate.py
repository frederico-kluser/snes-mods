"""Investigação dinâmica no MesenCE: quem escreve/lê um endereço, o que executa num endereço
(com M/X reais em cada execução), busca de RAM por diferenças entre frames e CDL para o Ghidra."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from . import evidence
from .disasm65816 import find_access_before
from .emu import Job, Probe, new_run_dir, read_probes, run_job
from .game import clean_rom, load_game, state_path
from .macro import parse_macro, total_frames
from .rom import fmt_addr, load_rom, parse_addr
from .util import FabError, read_json, rel, write_json


def _macro(macro: str | None) -> list:
    if not macro:
        return []
    p = Path(macro)
    return parse_macro(p if p.is_file() else macro)


def _state(game: str, state: str | None) -> Path | None:
    return state_path(game, state) if state else None


def _dyn_profile(game: str, rom: Path, state: Path | None, macro: list, frames: int) -> dict:
    return {"provider": "mesence-testrunner", "rom": rel(rom), "rom_sha256": load_game(game)["hashes"]["clean_sha256"]
            if rom == clean_rom(game) else "build", "state": rel(state) if state else "power-on",
            "macro_frames": total_frames(macro), "frames": frames}


def probe(game: str, kind: str, addr_text: str, end_text: str | None = None, state: str | None = None,
          macro: str | None = None, frames: int = 300, rom: Path | None = None, max_hits: int = 4000) -> dict:
    if kind not in ("write", "read", "exec"):
        raise FabError(f"tipo de sonda inválido: {kind}", "use write, read ou exec")
    rom = Path(rom) if rom else clean_rom(game)
    img = load_rom(rom)
    st = _state(game, state)
    steps = _macro(macro)
    frames = max(frames, total_frames(steps))
    addr = parse_addr(addr_text)
    end = parse_addr(end_text) if end_text else None
    out = new_run_dir(f"probe-{kind}", f"{game}-{fmt_addr(addr).replace(':', '')}")
    job = Job(frames=frames, state=st, macro=steps, probes=[Probe(kind, addr, end, max_hits)], capture_every=0)
    res = run_job(rom, job, out, rom_image=img)
    hits = read_probes(out)
    groups: dict[str, list[dict]] = defaultdict(list)
    for h in hits:
        groups[h["cpu_pc"]].append(h)
    rows = []
    for pc_txt, hs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        k_pc = parse_addr(pc_txt)
        flags = Counter(("m8" if h["m8"] else "m16") + "," + ("x8" if h["x8"] else "x16") for h in hs)
        row = {"pc": pc_txt, "hits": len(hs), "frames": [hs[0]["frame"], hs[-1]["frame"]],
               "flags": dict(flags), "values": sorted({h["value"] for h in hs})[:12],
               "regs_sample": {k: hs[0][k] for k in ("a", "x", "y", "dbr", "d", "sp")}}
        if kind == "exec":
            row["instruction_at"] = pc_txt
        else:
            try:
                pos = img.to_pc(k_pc)
                m8, x8 = hs[0]["m8"], hs[0]["x8"]
                cands = find_access_before(img.data, pos, k_pc, m8, x8, write=(kind == "write"))
                row["pc_next"] = pc_txt
                row["candidates"] = [c.fmt() for c in cands]
            except FabError:
                row["pc_next"] = pc_txt
                row["candidates"] = []
                row["note"] = "PC fora da ROM (código rodando em RAM?)"
        rows.append(row)
    result = {"probe": kind, "target": fmt_addr(addr) + (f"-{fmt_addr(end)}" if end else ""),
              "run": rel(out), "frames_run": res["frames_run"], "total_hits": res["probe_hits"][0] if res["probe_hits"] else 0,
              "recorded_hits": len(hits), "sites": rows}
    return evidence.record(game, f"probe-{kind}", {"addr": result["target"], "state": state, "macro": macro, "frames": frames},
                           _dyn_profile(game, rom, st, steps, frames), result, evidence.DYNAMIC_LIMITS)


def cdl(game: str, state: str | None = None, macro: str | None = None, frames: int = 1800) -> dict:
    from .ghidra import merge_cdl
    rom = clean_rom(game)
    steps = _macro(macro)
    frames = max(frames, total_frames(steps))
    out = new_run_dir("cdl", game)
    job = Job(frames=frames, state=_state(game, state), macro=steps, capture_every=0, cdl_out=out / "cdl.bin")
    run_job(rom, job, out, rom_image=load_rom(rom))
    stats = merge_cdl(game, out / "cdl.bin")
    return {"run": rel(out), "merged": stats}


# ── busca de RAM ──────────────────────────────────────────────────────────────

def ram_search(game: str, state: str | None = None, macro: str | None = None, frames: int = 120,
               every: int = 1, rom: Path | None = None) -> dict:
    rom = Path(rom) if rom else clean_rom(game)
    steps = _macro(macro)
    frames = max(frames, total_frames(steps))
    out = new_run_dir("ramsearch", game)
    job = Job(frames=frames, state=_state(game, state), macro=steps, capture_every=max(every, 1) * 4,
              wram_every=every)
    res = run_job(rom, job, out, rom_image=load_rom(rom))
    write_json(out / "ramsearch.json", {"game": game, "every": every, "frames": frames, "dumps": res["wram_dumps"]})
    from .media import postprocess_run
    postprocess_run(out, title=f"{game} ram search", video=False)
    return {"run": rel(out), "dumps": res["wram_dumps"], "every": every,
            "next": f"fab ram query {rel(out)} --changed A:B --unchanged C:D …"}


def _load_wram(run_dir: Path) -> tuple[np.ndarray, int]:
    meta = read_json(run_dir / "ramsearch.json")
    raw = np.fromfile(run_dir / "wram.bin", dtype=np.uint8)
    n = raw.size // 0x20000
    return raw[: n * 0x20000].reshape(n, 0x20000), int(meta["every"])


def ram_query(run_dir: Path, changed=None, unchanged=None, increased=None, decreased=None, equals=None,
              word: bool = False, limit: int = 40, game: str | None = None) -> dict:
    run_dir = Path(run_dir)
    w, every = _load_wram(run_dir)
    if word:
        w16 = w.astype(np.int64)
        vals = w16[:, :-1] | (w16[:, 1:] << 8)      # palavra little-endian em cada offset
    else:
        vals = w.astype(np.int64)
    n = vals.shape[0]
    mask = np.ones(vals.shape[1], dtype=bool)

    def idx(f: int) -> int:
        i = int(f) // every
        if not 0 <= i < n:
            raise FabError(f"frame {f} fora do intervalo (0..{(n - 1) * every})")
        return i

    def span(t: str) -> tuple[int, int]:
        a, b = t.split(":")
        return idx(a), idx(b)

    applied = []
    for t in changed or []:
        a, b = span(t)
        mask &= vals[a] != vals[b]
        applied.append(f"changed {t}")
    for t in unchanged or []:
        a, b = span(t)
        seg = vals[a:b + 1]
        mask &= (seg == seg[0]).all(axis=0)
        applied.append(f"unchanged {t}")
    for t in increased or []:
        a, b = span(t)
        mask &= vals[b] > vals[a]
        applied.append(f"increased {t}")
    for t in decreased or []:
        a, b = span(t)
        mask &= vals[b] < vals[a]
        applied.append(f"decreased {t}")
    for t in equals or []:
        f, v = t.split("=")
        mask &= vals[idx(f)] == int(v, 0)
        applied.append(f"equals {t}")
    cand = np.nonzero(mask)[0]
    sample_idx = np.linspace(0, n - 1, min(n, 16)).astype(int)
    rows = []
    for off in cand[:limit]:
        series = vals[:, off]
        rows.append({"addr": fmt_addr(0x7E0000 + int(off)), "changes": int(np.count_nonzero(np.diff(series))),
                     "min": int(series.min()), "max": int(series.max()),
                     "timeline": {int(i * every): int(series[i]) for i in sample_idx}})
    result = {"run": rel(run_dir), "filters": applied, "candidates": int(cand.size), "word": word, "rows": rows}
    if game:
        return evidence.record(game, "ram-query", {"run": rel(run_dir), "filters": applied, "word": word},
                               {"provider": "mesence-testrunner", "run": rel(run_dir)}, result, evidence.DYNAMIC_LIMITS)
    return result
