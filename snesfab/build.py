"""Montagem de mods com o Asar sobre uma CÓPIA da base limpa, com relatório verificável:
regiões alteradas (hijacks vs. freespace com RATS), geometria do hijack (regra dos 4 bytes e
fronteiras de instrução), símbolos WLA e patch BPS para distribuição."""

from __future__ import annotations

import re
from pathlib import Path

from . import bps
from .disasm65816 import disassemble
from .game import clean_rom, load_game
from .mods import load_mod
from .paths import BUILD, toolchain
from .rom import fmt_addr, load_rom, parse_addr, pc_to_snes
from .util import FabError, now_iso, rel, run, sha256_bytes, write_json

ROM_SIZE_BYTE = {0x20000: 0x07, 0x40000: 0x08, 0x80000: 0x09, 0x100000: 0x0A, 0x200000: 0x0B, 0x400000: 0x0C}


def parse_size(text) -> int:
    if isinstance(text, int):
        return text
    m = re.fullmatch(r"\s*(\d+)\s*(k|kb|kib|m|mb|mib)?\s*", str(text).lower())
    if not m:
        raise FabError(f"tamanho inválido: {text!r}", "use p.ex. 1MB, 2MB, 1536KB")
    n = int(m.group(1))
    unit = m.group(2) or ""
    return n * (1 << 20 if unit.startswith("m") else 1 << 10 if unit.startswith("k") else 1)


def expand_rom(data: bytearray, size: int, mapping: str, header_offset: int) -> bytearray:
    """Expande com $00 (freespace do Asar) e atualiza o byte de tamanho do cabeçalho."""
    if size <= len(data):
        return data
    if mapping in ("lorom", "sa1", "sdd1") and size > 0x400000:
        raise FabError("LoROM acima de 4 MB não é suportado aqui")
    data.extend(b"\x00" * (size - len(data)))
    sb = ROM_SIZE_BYTE.get(1 << (size - 1).bit_length())
    if sb is not None:
        data[header_offset + 0x17] = sb
    return data


def parse_sym(path: Path) -> dict[str, int]:
    labels = {}
    if not path.exists():
        return labels
    section = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("["):
            section = line
            continue
        if section == "[labels]":
            m = re.match(r"([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)", line)
            if m and not m.group(3).startswith(":"):
                labels[m.group(3)] = (int(m.group(1), 16) << 16) | int(m.group(2), 16)
    return labels


def _diff_regions(a: bytes, b: bytes, merge_gap: int = 2) -> list[tuple[int, int]]:
    n = max(len(a), len(b))
    regions = []
    i = 0
    while i < n:
        if (a[i] if i < len(a) else 0) != (b[i] if i < len(b) else 0):
            j = i
            gap = 0
            k = i
            while k < n and gap <= merge_gap:
                if (a[k] if k < len(a) else 0) != (b[k] if k < len(b) else 0):
                    j = k
                    gap = 0
                else:
                    gap += 1
                k += 1
            regions.append((i, j + 1))
            i = j + 1
        else:
            i += 1
    return regions


def _hijack_report(orig: bytes, new: bytes, start_pc: int, end_pc: int, mapping: str, m8: bool, x8: bool,
                   rom_size: int) -> dict:
    addr = pc_to_snes(start_pc, mapping)
    length = end_pc - start_pc
    win = 16
    n_ins = disassemble(new[start_pc:start_pc + max(length, 4) + win], addr, m8=m8, x8=x8)
    if n_ins and n_ins[0].mnemonic in ("JML", "JSL"):
        # bytes do salto podem coincidir com os originais e encurtar a região diferente
        length = max(length, n_ins[0].size)
        end_pc = start_pc + length
    o_ins = disassemble(orig[start_pc:start_pc + length + win], addr, m8=m8, x8=x8)
    covered, boundary = 0, None
    for ins in o_ins:
        covered += ins.size
        if covered >= length:
            boundary = covered
            break
    orphan = (boundary or length) - length
    first = n_ins[0] if n_ins else None
    rep = {
        "addr": fmt_addr(addr),
        "length": length,
        "assumed_flags": ("m8" if m8 else "m16") + "," + ("x8" if x8 else "x16"),
        "original": [i.fmt() for i in o_ins[:8]],
        "patched": [i.fmt() for i in n_ins[:8]],
        "is_long_jump": bool(first and first.mnemonic in ("JML", "JSL")),
        "jump_target": fmt_addr(first.target) if first and first.target is not None else None,
        "orig_instr_bytes_covered": boundary,
        "orphan_bytes_after": orphan,
        "ok": True,
        "issues": [],
    }
    if rep["is_long_jump"] and length < 4:
        rep["ok"] = False
        rep["issues"].append("JML/JSL precisa de 4 bytes; região menor (bytes iguais coincidentes?)")
    if orphan > 0:
        rep["issues"].append(
            f"{orphan} byte(s) de operando órfão após o patch em {fmt_addr(pc_to_snes(end_pc, mapping))}: "
            "preencha com NOP ou garanta que a execução nunca volte para lá")
        if first and first.mnemonic == "JSL":
            rep["ok"] = False   # JSL volta para start+4 → executaria o operando órfão
    return rep


def build_mod(mod_dir: Path, quiet: bool = False) -> dict:
    tc = toolchain()
    tc.require("asar")
    mod = load_mod(mod_dir)
    mod_dir = Path(mod["_dir"])
    game = load_game(mod["game"])
    clean_path = clean_rom(mod["game"])
    clean = clean_path.read_bytes()
    img = load_rom(clean_path)
    out_dir = BUILD / mod["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_rom = out_dir / f"{mod['id']}.sfc"
    work = bytearray(clean)
    if mod.get("expand_to"):
        work = expand_rom(work, parse_size(mod["expand_to"]), img.mapping, img.header.offset)
    base_for_diff = bytes(work)
    if out_rom.exists():
        out_rom.chmod(0o666)
    out_rom.write_bytes(work)

    logs, warnings, errors, syms = [], [], [], {}
    for i, patch in enumerate(mod.get("patches", ["patch.asm"])):
        asm = (mod_dir / patch).resolve()
        if not asm.exists():
            raise FabError(f"patch não encontrado: {asm}")
        sym = out_dir / (f"{mod['id']}.sym" if i == 0 else f"{mod['id']}.{i}.sym")
        defines = [f"-D{k}={v}" for k, v in (mod.get("defines") or {}).items()]
        cmd = [tc.asar, "--fix-checksum=on", "--symbols=wla", f"--symbols-path={sym}", f"-I{mod_dir}", *defines, asm, out_rom]
        proc = run(cmd, cwd=mod_dir, timeout=120)
        text = (proc.stdout + proc.stderr).strip()
        logs.append({"patch": patch, "exit": proc.returncode, "output": text})
        for line in text.splitlines():
            if re.search(r"\berror\b", line, re.I):
                errors.append(line.strip())
            elif re.search(r"\bwarning\b", line, re.I):
                warnings.append(line.strip())
        if proc.returncode != 0:
            break
        syms.update(parse_sym(sym))

    report: dict = {
        "mod": mod["id"], "game": mod["game"], "built": now_iso(),
        "rom": rel(out_rom), "asar": logs, "errors": errors, "warnings": warnings,
        "leak_warning": any("freespace_leaked" in w.lower() for w in warnings),
        "ok": not errors and all(l["exit"] == 0 for l in logs),
    }
    if not report["ok"]:
        write_json(out_dir / "build.json", report)
        raise FabError("o Asar falhou:\n  " + "\n  ".join(errors or [logs[-1]["output"][-800:]]),
                       "corrija o .asm (erros acima) e rode de novo")

    new = out_rom.read_bytes()
    regions = []
    hijacks = []
    flags_hint = {fmt_addr(parse_addr(h["addr"])): (h.get("m", 8) == 8, h.get("x", 8) == 8)
                  for h in mod.get("hijacks", [])}
    for a, b in _diff_regions(base_for_diff, new):
        snes_a = pc_to_snes(a, img.mapping)
        orig_bytes = base_for_diff[a:b]
        kind = "freespace" if all(x == 0 for x in orig_bytes) else "overwrite"
        if a >= img.header.offset - 0x10 and b <= img.header.offset + 0x40:
            kind = "header"
        reg = {"kind": kind, "start": fmt_addr(snes_a), "end": fmt_addr(pc_to_snes(b - 1, img.mapping)),
               "pc": f"0x{a:06X}", "length": b - a}
        if kind == "freespace" and new[a:a + 4] == b"STAR":
            size = (new[a + 4] | (new[a + 5] << 8)) + 1
            reg["rats"] = {"size": size, "code_start": fmt_addr(pc_to_snes(a + 8, img.mapping))}
        if kind == "overwrite":
            m8, x8 = flags_hint.get(fmt_addr(snes_a), (True, True))
            h = _hijack_report(base_for_diff, new, a, b, img.mapping, m8, x8, len(new))
            h["flags_source"] = "mod.json hijacks[]" if fmt_addr(snes_a) in flags_hint else "padrão m8,x8 (sem evidência!)"
            reg["hijack"] = h
            hijacks.append(h)
        regions.append(reg)
    report["regions"] = regions
    report["hijacks"] = hijacks
    report["labels"] = {k: fmt_addr(v) for k, v in sorted(syms.items(), key=lambda kv: kv[1])}
    report["sha256"] = sha256_bytes(new)
    # BPS sobre a base limpa original (sem expansão)
    patch = bps.create(clean, new, metadata=f"snesfab mod {mod['id']} for {game['title']} ({game['hashes']['clean_sha256'][:16]})")
    assert bps.apply(clean, patch) == new
    bps_path = out_dir / f"{mod['id']}.bps"
    bps_path.write_bytes(patch)
    report["bps"] = rel(bps_path)
    report["bps_size"] = len(patch)
    if any(not h["ok"] for h in hijacks):
        report["ok"] = False
    write_json(out_dir / "build.json", report)
    return report


def build_testbed() -> Path:
    """Monta a ROM homebrew de testes (fixtures/testbed) — material próprio, sem copyright de terceiros."""
    from .paths import FIXTURES
    tc = toolchain()
    tc.require("asar")
    out_dir = BUILD / "testbed"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "testbed.sfc"
    if out.exists():
        out.chmod(0o666)
        out.unlink()
    proc = run([tc.asar, "--fix-checksum=on", "--symbols=wla", f"--symbols-path={out_dir / 'testbed.sym'}",
                FIXTURES / "testbed" / "testbed.asm", out], timeout=60)
    if proc.returncode != 0:
        raise FabError(f"falha a montar o testbed: {(proc.stdout + proc.stderr)[-1500:]}")
    return out
