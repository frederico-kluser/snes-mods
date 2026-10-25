"""Execução headless no MesenCE (`--testRunner`) com o harness Lua.

Um *job* descreve: savestate inicial (ou power-on), nº de frames, macro de input, capturas de
frame, RAM vigiada por frame, sondas de memória, dumps de WRAM, pokes e savestates a gravar.
O resultado fica num diretório de run: frames.rgb, trace.csv, probes.jsonl, wram.bin, result.json.
"""

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import HARNESS_VERSION
from .macro import parse_macro, total_frames
from .paths import LUA, RUNS, toolchain
from .rom import fmt_addr, is_mmio, parse_addr, wram_offset
from .util import FabError, read_json, run, stamp, write_json

MESEN_SNES_SETTINGS = {
    ("Debug", "ScriptWindow", "AllowIoOsAccess"): True,
    ("Debug", "ScriptWindow", "AllowNetworkAccess"): False,
    ("Preferences", "AutomaticallyCheckForUpdates"): False,
    ("Preferences", "SingleInstance"): False,
    ("Snes", "RamPowerOnState"): "AllZeros",
    # em velocidade máxima (testRunner) o PPU salta a renderização de frames; sem isto as
    # capturas ficam desalinhadas da RAM (imagem de 1-5 frames antes)
    ("Snes", "DisableFrameSkipping"): True,
}


def ensure_mesen_settings() -> Path:
    """Garante o settings.json portátil do MesenCE com Lua I/O ligado e comando SNES na porta 1."""
    tc = toolchain()
    path = tc.mesen_dir / "settings.json"
    if path.exists():
        raw = path.read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        data = json.loads(raw.decode("utf-8-sig"))
    else:
        bom = False
        data = {"ConfigUpgrade": 1}
    changed = not path.exists()
    for keys, value in MESEN_SNES_SETTINGS.items():
        node = data
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        if node.get(keys[-1]) != value:
            node[keys[-1]] = value
            changed = True
    sw = data["Debug"]["ScriptWindow"]
    if int(sw.get("ScriptTimeout", 1)) < 60:
        sw["ScriptTimeout"] = 60
        changed = True
    port1 = data.setdefault("Snes", {}).setdefault("Port1", {})
    if port1.get("Type") in (None, "None"):
        port1["Type"] = "SnesController"
        changed = True
    if changed:
        text = json.dumps(data, indent=2, ensure_ascii=False)
        path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
    return path


def to_lua(obj) -> str:
    if obj is None:
        return "nil"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, float):
        return repr(obj)
    if isinstance(obj, Path):
        obj = obj.as_posix()
    if isinstance(obj, str):
        out = []
        for b in obj.encode("utf-8"):
            ch = chr(b)
            if ch in ('"', "\\"):
                out.append("\\" + ch)
            elif 32 <= b < 127:
                out.append(ch)
            else:
                out.append(f"\\{b:03d}")
        return '"' + "".join(out) + '"'
    if isinstance(obj, (list, tuple)):
        return "{" + ", ".join(to_lua(x) for x in obj) + "}"
    if isinstance(obj, dict):
        return "{" + ", ".join(f"[{to_lua(str(k))}] = {to_lua(v)}" for k, v in obj.items()) + "}"
    raise TypeError(f"não serializável para Lua: {type(obj)}")


# memória do PPU lida direto pelo harness: o "endereço" é um offset em bytes dentro dela, não um endereço de CPU
PPU_SPACES = {"cgram": ("snesCgRam", 0x200), "vram": ("snesVideoRam", 0x10000), "oam": ("snesSpriteRam", 0x220)}


def _split_space(text: str) -> tuple[str, str]:
    head, sep, tail = str(text).strip().partition(":")
    if sep and head.strip().lower() in PPU_SPACES:
        return head.strip().lower(), tail
    return "", str(text)


@dataclass
class Watch:
    name: str
    addr: int
    size: int = 1
    signed: bool = False
    space: str = ""      # "" = espaço da CPU; cgram | vram | oam = offset na memória do PPU

    @classmethod
    def from_spec(cls, spec: dict | str) -> "Watch":
        """Aceita {"name","addr","size","signed"} ou "nome=7E:0096:2s" (tamanho e 's' opcionais). Paleta, VRAM e
        OAM levam prefixo e offset em bytes: "gi=cgram:01D2:2" (cor 233 = bytes $1D2-$1D3 da CGRAM)."""
        if isinstance(spec, str):
            import re
            name, _, rest = spec.partition("=")
            space, rest = _split_space(rest)
            parts = rest.strip().split(":")
            size_txt = "1"
            if space:
                if len(parts) > 2:
                    raise FabError(f"watch inválido: {spec!r}", f"formato nome={space}:OFFSET[:1|2|4][s]")
                addr_txt, size_txt = parts[0], parts[1] if len(parts) == 2 else "1"
            elif len(parts) == 3:                                 # BB:AAAA:tamanho
                addr_txt, size_txt = parts[0] + ":" + parts[1], parts[2]
            elif len(parts) == 2 and re.fullmatch(r"[124]s?", parts[1]) and len(parts[0].lstrip("$")) > 2:
                addr_txt, size_txt = parts                        # $BBAAAA:tamanho
            elif len(parts) == 2:
                addr_txt = parts[0] + ":" + parts[1]              # BB:AAAA
            else:
                addr_txt = parts[0]
            if not re.fullmatch(r"[124]s?", size_txt):
                raise FabError(f"watch inválido: {spec!r}", "formato nome=BB:AAAA[:1|2|4][s] (s = com sinal)")
            w = cls(name.strip(), parse_addr(addr_txt), int(size_txt.rstrip("s")), size_txt.endswith("s"), space)
        else:
            space, addr_txt = _split_space(spec["addr"])
            w = cls(spec["name"], parse_addr(addr_txt), int(spec.get("size", 1)), bool(spec.get("signed", False)), space)
        if w.space and w.addr + w.size > PPU_SPACES[w.space][1]:
            raise FabError(f"watch {w.name}: {w.space}:{w.addr:04X} passa do fim da {w.space.upper()} "
                           f"(${PPU_SPACES[w.space][1]:X} bytes)", "o offset é em bytes: cor n da CGRAM = 2·n")
        return w

    def lua(self) -> dict:
        if self.space:
            return {"name": self.name, "mem": PPU_SPACES[self.space][0], "offset": self.addr, "size": self.size,
                    "signed": self.signed}
        off = wram_offset(self.addr)
        if off is not None:
            return {"name": self.name, "mem": "snesWorkRam", "offset": off, "size": self.size, "signed": self.signed}
        return {"name": self.name, "mem": "snesDebug", "offset": self.addr, "size": self.size, "signed": self.signed}

    def to_dict(self) -> dict:
        addr = f"{self.space}:{self.addr:04X}" if self.space else fmt_addr(self.addr)
        return {"name": self.name, "addr": addr, "size": self.size, "signed": self.signed}


@dataclass
class Probe:
    kind: str            # write | read | exec
    addr: int
    end: int | None = None
    max_hits: int = 500
    label: str = ""

    def lua(self, rom=None) -> list[dict]:
        start, stop = self.addr, self.end if self.end is not None else self.addr
        label = self.label or f"{self.kind} {fmt_addr(start)}" + (f"-{fmt_addr(stop)}" if stop != start else "")
        base = {"kind": self.kind, "max_hits": self.max_hits, "label": label}
        w0, w1 = wram_offset(start), wram_offset(stop)
        if w0 is not None and w1 is not None:
            return [{**base, "mem": "snesWorkRam", "start": w0, "stop": w1}]
        if is_mmio(start):
            bank = (start >> 16) & 0xFF
            mirror = 0x80 if bank < 0x80 else -0x80
            return [{**base, "mem": "snesMemory", "start": start, "stop": stop},
                    {**base, "mem": "snesMemory", "start": start + (mirror << 16), "stop": stop + (mirror << 16)}]
        if rom is not None:
            try:
                p0, p1 = rom.to_pc(start), rom.to_pc(stop)
                return [{**base, "mem": "snesPrgRom", "start": p0, "stop": p1}]
            except FabError:
                pass
        return [{**base, "mem": "snesMemory", "start": start, "stop": stop}]


@dataclass
class Job:
    frames: int
    state: Path | None = None
    macro: list = field(default_factory=list)       # [(frames, mask)]
    watches: list[Watch] = field(default_factory=list)
    probes: list[Probe] = field(default_factory=list)
    capture_every: int = 1
    capture_start: int = 0
    warmup: int = 0                                  # frames iniciais sem medir (state traz RAM velha)
    wram_every: int = 0
    pokes: list[dict] = field(default_factory=list)  # {"frame", "addr", "value", "size"}
    save_end: Path | None = None
    save_at: list[dict] = field(default_factory=list)  # {"frame", "path"}
    cdl_out: Path | None = None                         # dump do Code/Data Log da ROM no fim

    def to_lua_table(self, out_dir: Path, rom=None) -> dict:
        probes = []
        for p in self.probes:
            probes.extend(p.lua(rom))
        pokes = []
        for pk in self.pokes:
            addr = parse_addr(pk["addr"])
            off = wram_offset(addr)
            mem, offset = ("snesWorkRam", off) if off is not None else ("snesDebug", addr)
            pokes.append({"frame": int(pk["frame"]), "mem": mem, "offset": offset,
                          "value": int(pk["value"]), "size": int(pk.get("size", 1))})
        return {
            "harness_version": HARNESS_VERSION,
            "out_dir": out_dir.as_posix(),
            "frames": int(self.frames),
            "warmup": int(self.warmup),
            "state": self.state.as_posix() if self.state else None,
            "macro": [[int(n), int(m)] for n, m in self.macro],
            "watch": [w.lua() for w in self.watches],
            "probes": probes,
            "capture": {"every": int(self.capture_every), "start": int(self.capture_start)},
            "wram_every": int(self.wram_every),
            "pokes": pokes,
            "save_end": self.save_end.as_posix() if self.save_end else None,
            "save_at": [{"frame": int(s["frame"]), "path": Path(s["path"]).as_posix()} for s in self.save_at],
            "cdl_out": self.cdl_out.as_posix() if self.cdl_out else None,
        }


def resolve_mem_names(table: dict) -> dict:
    """O harness resolve nomes de memType em runtime; aqui só validamos os nomes usados."""
    valid = {"snesWorkRam", "snesDebug", "snesMemory", "snesPrgRom", "snesSaveRam", *(m for m, _ in PPU_SPACES.values())}
    for group in ("watch", "probes", "pokes"):
        for item in table.get(group, []):
            if item["mem"] not in valid:
                raise FabError(f"memType desconhecido: {item['mem']}")
    return table


def new_run_dir(kind: str, label: str = "") -> Path:
    from .util import slugify
    name = f"{stamp()}-{kind}" + (f"-{slugify(label)}" if label else "")
    d = RUNS / name
    i = 1
    while d.exists():
        i += 1
        d = RUNS / f"{name}-{i}"
    d.mkdir(parents=True)
    return d


def run_job(rom_path: Path, job: Job, out_dir: Path, rom_image=None, timeout_s: int | None = None) -> dict:
    """Roda o job no MesenCE headless. Devolve o result.json (com 'run_dir')."""
    tc = toolchain()
    tc.require("mesen")
    ensure_mesen_settings()
    out_dir.mkdir(parents=True, exist_ok=True)
    if job.frames <= 0:
        raise FabError("o job precisa de frames > 0")
    if not 0 <= job.warmup < job.frames:
        raise FabError(f"warmup inválido: {job.warmup}", f"tem de ser 0 <= warmup < frames ({job.frames})")
    if job.state and not Path(job.state).is_file():
        raise FabError(f"savestate não encontrado: {job.state}", "lista com `fab state list <jogo>`")
    # cópia com nome único: isola SRAM/workspace do Mesen por run e documenta o que correu
    run_rom = out_dir / f"{out_dir.name}.sfc"
    shutil.copyfile(rom_path, run_rom)
    table = resolve_mem_names(job.to_lua_table(out_dir, rom_image))
    (out_dir / "job.lua").write_text("return " + to_lua(table) + "\n", encoding="utf-8")
    write_json(out_dir / "job.json", table)
    if timeout_s is None:
        timeout_s = 30 + job.frames // 25
        if job.wram_every:
            timeout_s += int(job.frames / job.wram_every * 0.3)
    cmd = [tc.mesen, "--testRunner", f"--timeout={timeout_s}", LUA / "harness.lua", run_rom]
    proc = run(cmd, env={"SNESFAB_JOB": (out_dir / "job.lua").as_posix()}, timeout=timeout_s + 60)
    _cleanup_mesen_artifacts(tc.mesen_dir, run_rom.stem)
    result_path = out_dir / "result.json"
    if result_path.exists():
        result = read_json(result_path)
    else:
        log = (out_dir / "harness.log").read_text(encoding="utf-8", errors="replace") if (out_dir / "harness.log").exists() else ""
        result = {"status": "error", "error": f"Mesen terminou (código {proc.returncode}) sem result.json. {log[-1500:]}"}
    result["exit_code"] = proc.returncode
    result["run_dir"] = str(out_dir)
    try:
        run_rom.unlink()
    except OSError:
        pass
    write_json(out_dir / "result.json", result)
    if result.get("status") != "ok":
        raise FabError(f"run falhou: {result.get('error')}", f"veja {out_dir / 'harness.log'}")
    return result


def _cleanup_mesen_artifacts(mesen_dir: Path, stem: str) -> None:
    for sub in ("Saves", "Debugger", "RecentGames", "SaveStates"):
        d = mesen_dir / sub
        if d.is_dir():
            for f in d.glob(f"{stem}*"):
                try:
                    if f.is_dir():
                        shutil.rmtree(f, ignore_errors=True)
                    else:
                        f.unlink()
                except OSError:
                    pass
    lua_data = mesen_dir / "LuaScriptData" / "harness"
    if lua_data.is_dir():
        shutil.rmtree(lua_data, ignore_errors=True)


# ── leitura das saídas ─────────────────────────────────────────────────────────

def read_trace(run_dir: Path) -> dict[str, list[int]]:
    path = Path(run_dir) / "trace.csv"
    cols: dict[str, list[int]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for name in reader.fieldnames or []:
            cols[name] = []
        for row in reader:
            for k, v in row.items():
                cols[k].append(int(v))
    return cols


def read_probes(run_dir: Path) -> list[dict]:
    """Hits das sondas, normalizados: label da sonda, endereço de CPU da instrução (k:pc) e flags M/X.
    Em escritas/leituras o pc reportado é o da instrução SEGUINTE (o 65816 já avançou o PC)."""
    run_dir = Path(run_dir)
    path = run_dir / "probes.jsonl"
    if not path.exists():
        return []
    labels = {}
    if (run_dir / "job.json").exists():
        for i, p in enumerate(read_json(run_dir / "job.json").get("probes", []), 1):
            labels[i] = p.get("label", "")
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            h = json.loads(line)
            h["label"] = labels.get(h["probe"], "")
            h["cpu_pc"] = fmt_addr((h["k"] << 16) | h["pc"])
            h["m8"] = bool(h["ps"] & 0x20)
            h["x8"] = bool(h["ps"] & 0x10)
            out.append(h)
    return out


def job_from_scenario(sc: dict, base_dir: Path, game_dir: Path | None = None) -> Job:
    """Constrói um Job a partir de um cenário (mod.json → scenarios[]) ou de opções da CLI."""
    def resolve(p):
        if p is None:
            return None
        p = Path(p)
        if p.is_absolute():
            return p
        for base in (base_dir, game_dir, Path.cwd()):
            if base is not None and (base / p).exists():
                return (base / p).resolve()
        from .paths import ROOT
        return (ROOT / p).resolve()

    macro_src = sc.get("input", sc.get("macro"))
    if isinstance(macro_src, str) and "\n" not in macro_src:
        mp = resolve(macro_src)
        macro = parse_macro(mp) if mp and mp.exists() else parse_macro(macro_src)
    else:
        macro = parse_macro(macro_src)
    frames = int(sc.get("frames") or total_frames(macro) or 60)
    cap = sc.get("capture", {})
    return Job(
        frames=frames,
        state=resolve(sc.get("state")),
        macro=macro,
        watches=[Watch.from_spec(w) for w in sc.get("watch", [])],
        probes=[Probe(p["kind"], parse_addr(p["addr"]), parse_addr(p["end"]) if p.get("end") else None,
                      int(p.get("max_hits", 500)), p.get("label", "")) for p in sc.get("probes", [])],
        capture_every=int(cap.get("every", 2)),
        capture_start=int(cap.get("start", 0)),
        warmup=int(sc.get("warmup", 0)),
        wram_every=int(sc.get("wram_every", 0)),
        pokes=sc.get("pokes", []),
    )
