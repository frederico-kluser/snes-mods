"""Lane estático: Ghidra 12 headless + extensão ghidra-snes (loader LoROM/HiROM, língua 65816:LE:24:snes).

`fab re analyze <jogo>` importa a base limpa (só leitura), semeia vetores + CDL do MesenCE com M/X,
roda a auto-análise e exporta TSVs para work/ghidra/<jogo>/export/. As consultas (funcs, func,
xrefs, search, decompile) leem esses arquivos e devolvem registros de evidência.
"""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

from . import evidence
from .game import clean_rom
from .paths import GHIDRA_SCRIPTS, WORK, manifest, toolchain
from .rom import fmt_addr, load_rom, parse_addr, pc_to_snes, wram_offset
from .util import FabError, now_iso, read_json, rel, run, write_json

CDL_CODE, CDL_DATA, CDL_JUMP, CDL_SUB, CDL_X8, CDL_M8 = 0x01, 0x02, 0x04, 0x08, 0x10, 0x20


def gdir(game: str) -> Path:
    return WORK / "ghidra" / game


def export_dir(game: str) -> Path:
    return gdir(game) / "export"


def cdl_path(game: str) -> Path:
    return gdir(game) / "cdl.bin"


def merge_cdl(game: str, new_cdl: Path) -> dict:
    """OR-merge do CDL de uma run no CDL acumulado do jogo."""
    data = new_cdl.read_bytes()
    dest = cdl_path(game)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        old = dest.read_bytes()
        if len(old) == len(data):
            data = bytes(a | b for a, b in zip(old, data))
    dest.write_bytes(data)
    return cdl_stats(data)


def cdl_stats(data: bytes) -> dict:
    code = sum(1 for b in data if b & CDL_CODE)
    return {"bytes": len(data), "code_bytes": code, "data_bytes": sum(1 for b in data if b & CDL_DATA),
            "sub_entries": sum(1 for b in data if b & CDL_SUB), "jump_targets": sum(1 for b in data if b & CDL_JUMP),
            "coverage_pct": round(100 * code / max(len(data), 1), 3)}


def ghidra_addr(pc: int, mapping: str) -> int:
    """Endereço canônico no programa do ghidra-snes: o do pc_to_snes, exceto no SA-1, que o loader põe na
    vista HiROM ($C0-$FF) em vez da LoROM do Asar (as duas valem no hardware com o MMC padrão)."""
    addr = pc_to_snes(pc, mapping)
    return 0xC00000 | pc if mapping == "sa1" else addr


def build_seeds(game: str) -> list[tuple[int, int, int, int, str]]:
    """Sementes (endereço canônico, m8, x8, e, nome): vetores do cabeçalho + entradas do CDL."""
    img = load_rom(clean_rom(game))
    seeds: dict[int, tuple[int, int, int, int, str]] = {}
    cdl = cdl_path(game).read_bytes() if cdl_path(game).exists() else b""

    def canon(addr16: int, bank: int = 0x00) -> int | None:
        try:
            return ghidra_addr(img.to_pc((bank << 16) | addr16), img.mapping)
        except FabError:
            return None

    vec = img.header.vectors
    for name, emu_mode in (("emu_reset", 1), ("native_nmi", 0), ("native_irq", 0), ("native_brk", 0), ("native_cop", 0)):
        target = vec.get(name, 0)
        if target < 0x8000:
            continue
        a = canon(target)
        if a is None:
            continue
        m = x = 1
        if cdl:
            pc = img.to_pc(a)
            if pc < len(cdl) and cdl[pc] & CDL_CODE:
                m, x = int(bool(cdl[pc] & CDL_M8)), int(bool(cdl[pc] & CDL_X8))
        if emu_mode:
            m = x = 1
        seeds[a] = (a, m, x, emu_mode, name.replace("native_", "").replace("emu_", "").upper() + "_handler")
    if cdl:
        for pc, flags in enumerate(cdl):
            if flags & CDL_SUB and flags & CDL_CODE:
                a = ghidra_addr(pc, img.mapping)
                if a not in seeds:
                    seeds[a] = (a, int(bool(flags & CDL_M8)), int(bool(flags & CDL_X8)), 0, "")
    return sorted(seeds.values())


def profile(game: str) -> dict:
    p = export_dir(game) / "meta.json"
    meta = read_json(p) if p.exists() else {}
    src = manifest().get("sources", {}).get("ghidra_snes", {})
    prof = read_json(gdir(game) / "profile.json") if (gdir(game) / "profile.json").exists() else {}
    return {"provider": "ghidra-headless", "ghidra": meta.get("ghidra"), "language": meta.get("language"),
            "loader": meta.get("format"), "ghidra_snes": src.get("commit"), "rom_sha256": meta.get("sha256"),
            "seeds": prof.get("seeds"), "cdl": prof.get("cdl"), "analyzed": prof.get("time")}


def analyze(game: str, timeout: int = 3600) -> dict:
    tc = toolchain()
    tc.require("analyze_headless", "java")
    rom = clean_rom(game)
    g = gdir(game)
    g.mkdir(parents=True, exist_ok=True)
    seeds = build_seeds(game)
    seeds_file = g / "seeds.tsv"
    with open(seeds_file, "w", encoding="utf-8", newline="\n") as f:
        f.write("# addr\tm8\tx8\te\tname\n")
        for a, m, x, e, name in seeds:
            f.write(f"{a:06X}\t{m}\t{x}\t{e}\t{name}\n")
    out = export_dir(game)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*"):
        if old.is_file():
            old.unlink()
    proj = g / "project"
    proj.mkdir(exist_ok=True)
    cmd = [tc.analyze_headless, proj, game, "-import", rom, "-overwrite", "-noanalysis",
           "-scriptPath", GHIDRA_SCRIPTS,
           "-postScript", "SnesSeedAndAnalyze.java", seeds_file,
           "-postScript", "ExportSnesEvidence.java", out,
           "-max-cpu", str(max(2, (os.cpu_count() or 4) // 2))]
    proc = run(cmd, env=tc.java_env(), timeout=timeout)
    log = (proc.stdout or "") + (proc.stderr or "")
    (g / "analyze.log").write_text(log, encoding="utf-8")
    if proc.returncode != 0 or not (out / "meta.json").exists():
        tail = "\n".join(line for line in log.splitlines() if "ERROR" in line or "Exception" in line)[-2000:]
        raise FabError(f"o Ghidra falhou a analisar {game}: {tail or log[-1500:]}", f"veja {rel(g / 'analyze.log')}")
    m = re.search(r"sementes aplicadas=(\d+) falhadas=(\d+)", log)
    meta = read_json(out / "meta.json")
    prof = {"time": now_iso(), "seeds": {"total": len(seeds), "applied": int(m.group(1)) if m else None,
                                         "failed": int(m.group(2)) if m else None},
            "cdl": cdl_stats(cdl_path(game).read_bytes()) if cdl_path(game).exists() else None,
            "functions": meta.get("function_count")}
    write_json(g / "profile.json", prof)
    return {"game": game, "export": rel(out), "functions": meta.get("function_count"), **prof}


# ── consultas sobre o export ──────────────────────────────────────────────────

class Index:
    def __init__(self, game: str):
        d = export_dir(game)
        if not (d / "listing.tsv").exists():
            raise FabError(f"sem análise estática para '{game}'", f"rode `fab re analyze {game}` (idealmente depois de `fab re cdl`)")
        self.game = game
        self.funcs = self._tsv(d / "functions.tsv")
        self.listing = self._tsv(d / "listing.tsv")
        self.refs = self._tsv(d / "refs.tsv")
        self.symbols = self._tsv(d / "symbols.tsv")
        self.by_addr = {int(r["addr"], 16): r for r in self.listing}
        self.addrs = sorted(self.by_addr)
        self.func_by_entry = {int(f["entry"], 16): f for f in self.funcs}
        self.sym_by_addr: dict[int, list[str]] = {}
        for s in self.symbols:
            self.sym_by_addr.setdefault(int(s["addr"], 16), []).append(s["name"])

    @staticmethod
    def _tsv(p: Path) -> list[dict]:
        if not p.exists():
            return []
        with open(p, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f, delimiter="\t"))

    def func_containing(self, addr: int) -> dict | None:
        for f in self.funcs:
            for rng in f["ranges"].split(","):
                if not rng:
                    continue
                a, b = (int(x, 16) for x in rng.split("-"))
                if a <= addr <= b:
                    return f
        return None

    def instr_line(self, r: dict) -> str:
        a = int(r["addr"], 16)
        flags = ("m8" if r.get("mf") == "1" else "m16" if r.get("mf") == "0" else "m?") + "," + \
                ("x8" if r.get("xf") == "1" else "x16" if r.get("xf") == "0" else "x?")
        names = self.sym_by_addr.get(a)
        lab = f"{names[0]}:" if names else ""
        return f"{fmt_addr(a)}  {r['bytes']:<10} {r['mnemonic']} {r['operands']:<24} ; {flags} {lab}".rstrip()


def _equivalents(addr: int) -> list[int]:
    """Endereços equivalentes no espaço do Ghidra (WRAM baixa espelhada em $00, $7E…)."""
    out = {addr}
    off = wram_offset(addr)
    if off is not None:
        out.add(0x7E0000 + off)
        if off < 0x2000:
            out.add(off)
            out.add(0x800000 | off)
    bank, a16 = (addr >> 16) & 0xFF, addr & 0xFFFF
    if (bank <= 0x3F or 0x80 <= bank <= 0xBF) and 0x2000 <= a16 < 0x6000:
        out.add(a16)
        out.add(0x800000 | a16)
    return sorted(out)


def q_xrefs(game: str, addr_text: str) -> dict:
    ix = Index(game)
    addr = parse_addr(addr_text)
    eq = set(_equivalents(addr))
    hits = []
    for r in ix.refs:
        to = int(r["to"], 16)
        if to in eq:
            fr = int(r["from"], 16)
            ins = ix.by_addr.get(fr)
            f = ix.func_containing(fr)
            hits.append({"from": fmt_addr(fr), "to": fmt_addr(to), "type": r["type"],
                         "instruction": ix.instr_line(ins) if ins else None,
                         "function": fmt_addr(int(f["entry"], 16)) if f else None})
    # complemento textual: operandos que mencionam o endereço baixo (DP/abs) sem referência criada
    low = addr & 0xFFFF
    pats = {f"0x{low:x}", f"0x{low:02x}"} if low < 0x100 else {f"0x{low:x}"}
    seen = {h["from"] for h in hits}
    textual = []
    for r in ix.listing:
        ops = r["operands"].lower()
        if any(re.search(rf"(?<![0-9a-fx]){re.escape(p)}(?![0-9a-f])", ops) for p in pats):
            a = fmt_addr(int(r["addr"], 16))
            if a not in seen:
                textual.append(ix.instr_line(r))
    res = {"target": fmt_addr(addr), "equivalents": [fmt_addr(e) for e in sorted(eq)], "refs": hits,
           "textual_operand_matches": textual[:200]}
    lim = evidence.STATIC_LIMITS + ["Correspondências textuais são candidatas (mesmo operando baixo, base D/DB não verificada)."]
    return evidence.record(game, "xrefs", {"addr": fmt_addr(addr)}, profile(game), res, lim)


def q_funcs(game: str, limit: int = 60, pattern: str | None = None) -> dict:
    ix = Index(game)
    rows = []
    for f in ix.funcs:
        if pattern and not re.search(pattern, f["name"], re.I):
            continue
        rows.append({"entry": fmt_addr(int(f["entry"], 16)), "name": f["name"], "size": int(f["size"]),
                     "callers": len([c for c in f["callers"].split(",") if c]),
                     "callees": len([c for c in f["callees"].split(",") if c])})
    rows.sort(key=lambda r: (-r["callers"], r["entry"]))
    return evidence.record(game, "functions", {"pattern": pattern}, profile(game),
                           {"count": len(rows), "functions": rows[:limit]}, evidence.STATIC_LIMITS)


def q_func(game: str, addr_text: str, max_lines: int = 200) -> dict:
    ix = Index(game)
    addr = parse_addr(addr_text)
    f = ix.func_containing(addr)
    lines = []
    if f:
        for rng in f["ranges"].split(","):
            if not rng:
                continue
            a, b = (int(x, 16) for x in rng.split("-"))
            for k in ix.addrs:
                if a <= k <= b:
                    lines.append(ix.instr_line(ix.by_addr[k]))
    else:
        import bisect
        i = bisect.bisect_left(ix.addrs, addr)
        for k in ix.addrs[max(0, i - 8): i + 40]:
            lines.append(ix.instr_line(ix.by_addr[k]))
    sep_rep = [x for x in lines if any(op in x for op in (" SEP ", " REP ", " PLP ", " XCE "))]
    res = {
        "query": fmt_addr(addr),
        "function": None if not f else {
            "entry": fmt_addr(int(f["entry"], 16)), "name": f["name"], "size": int(f["size"]),
            "callers": [fmt_addr(int(c, 16)) for c in f["callers"].split(",") if c],
            "callees": [fmt_addr(int(c, 16)) for c in f["callees"].split(",") if c],
        },
        "instructions": lines[:max_lines],
        "truncated": len(lines) > max_lines,
        "mx_changes": sep_rep,
    }
    return evidence.record(game, "function", {"addr": fmt_addr(addr)}, profile(game), res, evidence.STATIC_LIMITS)


def q_search(game: str, regex: str, limit: int = 100) -> dict:
    ix = Index(game)
    rx = re.compile(regex, re.I)
    hits = [ix.instr_line(r) for r in ix.listing if rx.search(f"{r['mnemonic']} {r['operands']}")]
    return evidence.record(game, "search", {"regex": regex}, profile(game),
                           {"count": len(hits), "matches": hits[:limit]}, evidence.STATIC_LIMITS)


def q_decompile(game: str, addrs: list[str], timeout: int = 900) -> dict:
    tc = toolchain()
    proj = gdir(game) / "project"
    if not proj.exists():
        raise FabError(f"sem projeto Ghidra para '{game}'", f"rode `fab re analyze {game}`")
    out = gdir(game) / "decompile"
    out.mkdir(exist_ok=True)
    jl = out / "decompile.jsonl"
    if jl.exists():
        jl.unlink()
    hexes = [f"{parse_addr(a):06X}" for a in addrs]
    cmd = [tc.analyze_headless, proj, game, "-process", clean_rom(game).name, "-noanalysis", "-readOnly",
           "-scriptPath", GHIDRA_SCRIPTS, "-postScript", "DecompileFunctions.java", out, *hexes]
    proc = run(cmd, env=tc.java_env(), timeout=timeout)
    if not jl.exists():
        raise FabError(f"decompilação falhou: {(proc.stdout + proc.stderr)[-1500:]}")
    items = [json.loads(line) for line in jl.read_text(encoding="utf-8").splitlines() if line.strip()]
    lim = evidence.STATIC_LIMITS + ["O pseudocódigo C do 65816 é uma aproximação: cruza SEMPRE com `fab re func` (instruções e M/X)."]
    return evidence.record(game, "decompile", {"addrs": hexes}, profile(game), items, lim)
