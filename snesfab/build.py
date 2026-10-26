"""Montagem de mods com o Asar sobre uma CÓPIA da base limpa, com relatório verificável:
regiões alteradas (hijacks vs. dados declarados vs. freespace com RATS), geometria do hijack
(regra dos 4 bytes e fronteiras de instrução), símbolos WLA e patch BPS para distribuição."""

from __future__ import annotations

import re
from pathlib import Path

from . import bps
from .disasm65816 import BRANCHES, ENDS_FLOW, OPCODES, apply_flags, decode, disassemble
from .game import clean_rom, load_game
from .mods import load_mod
from .paths import BUILD, toolchain
from .rom import addr_or_pc, expansion_notes, fmt_addr, load_rom, parse_addr, pc_to_snes, snes_to_pc
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
    if mapping in ("lorom", "sa1") and size > 0x400000:
        raise FabError("LoROM acima de 4 MB não é suportado aqui")
    if mapping == "sdd1" and size > 0x800000:
        raise FabError("S-DD1 acima de 8 MiB não é suportado aqui", "o snes9x só aceita S-DD1 abaixo de 8 MiB")
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


def parse_sym_lines(path: Path) -> tuple[list[tuple[int, int, int]], dict[int, Path]]:
    """[addr-to-line mapping] e [source files] do .sym WLA do Asar: [(endereço do Asar, arquivo, linha)], {arquivo: caminho}."""
    rows, files, section = [], {}, None
    if not path.exists():
        return rows, files
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("["):
            section = line
            continue
        if section == "[addr-to-line mapping]":
            m = re.match(r"([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+([0-9A-Fa-f]{4}):([0-9A-Fa-f]{8})", line)
            if m:
                rows.append(((int(m.group(1), 16) << 16) | int(m.group(2), 16), int(m.group(3), 16), int(m.group(4), 16)))
        elif section == "[source files]":
            m = re.match(r"([0-9A-Fa-f]{4})\s+[0-9A-Fa-f]{8}\s+(.+)$", line)
            if m:
                files[int(m.group(1), 16)] = Path(m.group(2))
    return rows, files


_MNEMONICS = {mn for mn, _ in OPCODES.values()}


def _source_instruction(text: str) -> str | None:
    """A instrução 65816 de uma linha de fonte do Asar (sem rótulo nem comentário), ou None (dado/diretiva)."""
    code = text.split(";", 1)[0].strip()
    code = re.sub(r"^[.\w!+\-]+:\s*", "", code)            # rótulo "Nome:" / ".local:"
    if code.startswith("autoclean "):
        code = code[len("autoclean "):].strip()
    head = code.split(None, 1)[0] if code else ""
    return code if head.split(".")[0].upper() in _MNEMONICS else None


def verify_code_widths(rom: bytes, mapping: str, sym: Path, entries: list[tuple[int, bool, bool]]) -> dict:
    """Confere, instrução a instrução, que o que o Asar montou tem o tamanho que a CPU vai LER com o M/X real.

    Parte de cada destino de hijack (com o M/X declarado em hijacks[]) e segue o fluxo dentro do NOSSO código
    (linhas do .sym), rastreando SEP/REP. Se um imediato saiu com 16 bits onde M ou X é 8 (ou vice-versa), a
    CPU lê menos bytes e o que sobra vira outra instrução (o `00` de `A9 08 00` é BRK): o build acusa a linha."""
    rows, files = parse_sym_lines(sym)
    if not rows:
        return {"instructions": 0, "issues": [], "note": "sem [addr-to-line mapping] no .sym"}
    src_cache: dict[int, list[str]] = {}

    def line_text(f: int, n: int) -> str:
        if f not in src_cache:
            try:
                src_cache[f] = files[f].read_text(encoding="utf-8", errors="replace").splitlines()
            except (KeyError, OSError):
                src_cache[f] = []
        lines = src_cache[f]
        return lines[n - 1].strip() if 0 < n <= len(lines) else "?"

    starts: dict[int, tuple[int, int, str]] = {}
    ordered = sorted(rows)
    data_rows = {a for a, _, _ in rows}
    for addr, f, n in ordered:
        txt = line_text(f, n)
        ins = _source_instruction(txt)
        if ins is not None:
            starts[addr] = (f, n, ins)
    # tamanho montado = distância até a próxima linha que emitiu bytes (no mesmo bloco contíguo)
    assembled: dict[int, int] = {}
    addrs = [a for a, _, _ in ordered]
    for i, a in enumerate(addrs[:-1]):
        if a in starts and 0 < addrs[i + 1] - a <= 4:
            assembled[a] = addrs[i + 1] - a

    def to_pc(addr: int) -> int:
        bank, off = (addr >> 16) & 0xFF, addr & 0xFFFF
        if mapping in ("lorom", "sdd1"):
            return ((bank & 0x7F) << 15) | (off & 0x7FFF)
        if mapping == "hirom":
            return ((bank & 0x3F) << 16) | off
        return snes_to_pc(addr, mapping, len(rom))

    issues, seen, n_ins = [], set(), 0
    work = [(a, m8, x8) for a, m8, x8 in entries if a in starts]
    while work:
        addr, m8, x8 = work.pop()
        uncertain = False
        while (addr, m8, x8) not in seen:
            seen.add((addr, m8, x8))
            if addr not in starts and addr in data_rows:
                break                       # linha de dado (db/dw: ex. bytes originais copiados) — não dá para conferir
            if addr not in starts:
                prev = max((a for a in starts if a < addr), default=None)
                where = f"{files.get(starts[prev][0], Path('?')).name}:{starts[prev][1]} ({starts[prev][2]})" if prev else "?"
                issues.append(f"a CPU chega a {fmt_addr(addr)} no MEIO de uma instrução montada (depois de {where}): "
                              "algum imediato tem o tamanho errado para o M/X do ponto — use .b/.w")
                break
            f, n, text = starts[addr]
            try:
                pc = to_pc(addr)
            except FabError:
                break
            ins = decode(rom, pc, addr, m8, x8, uncertain)
            if ins is None:
                break
            n_ins += 1
            got = assembled.get(addr)
            if got is not None and got != ins.size:
                flags = ("m8" if m8 else "m16") + "," + ("x8" if x8 else "x16")
                issues.append(f"{files.get(f, Path('?')).name}:{n} `{text}` foi montada com {got} bytes, mas com "
                              f"{flags} a CPU lê {ins.size} ({ins.text}) → o resto vira outra instrução. "
                              f"Ponha o sufixo certo (.b = 8 bits, .w = 16 bits) no imediato")
                break
            m8, x8, uncertain = apply_flags(ins, m8, x8, uncertain)
            if uncertain:
                break                       # PLP/RTI/XCE: M/X daqui em diante não se sabe estaticamente
            mn = ins.mnemonic
            if mn in ("JSR", "JSL", "JMP", "JML") and ins.target is not None and ins.target in starts:
                work.append((ins.target, m8, x8))
            if mn in BRANCHES and ins.target is not None and ins.target in starts:
                work.append((ins.target, m8, x8))
            if mn in ENDS_FLOW:
                break
            addr = (addr & 0xFF0000) | ((addr + ins.size) & 0xFFFF)
    return {"instructions": n_ins, "issues": issues}


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


def parse_data_regions(entries, mapping: str) -> list[dict]:
    """`mod.json → data[]`: regiões de DADOS (paletas, tabelas…) declaradas com evidência.
    Devolve cada região em PCs da imagem (`start_pc`, `end_pc`) + o que foi declarado."""
    out = []
    for i, d in enumerate(entries or []):
        if not isinstance(d, dict):
            raise FabError(f"data[{i}] do mod.json tem de ser um objeto {{addr, length, evidence}}",
                           'ex.: {"addr": "BE:8272", "length": 10, "evidence": "paleta do personagem: fab sprite snap ev-…"}')
        if not str(d.get("evidence", "")).strip():
            raise FabError(f"data[{i}] do mod.json precisa de 'evidence' (endereço · como foi verificado)",
                           'ex.: {"addr": "BE:8272", "length": 10, "evidence": "paleta do personagem: fab sprite snap ev-…"}')
        try:
            length = int(d["length"])
            if "pc" in d:                       # offset no arquivo: sem ambiguidade de mapa (S-DD1!)
                start = int(str(d["pc"]), 0)
                shown = addr_or_pc(start, mapping)
            else:
                addr = parse_addr(str(d["addr"]))
                start = snes_to_pc(addr, mapping)
                shown = fmt_addr(addr)
        except (KeyError, TypeError, ValueError, FabError) as e:
            raise FabError(f"data[{i}] do mod.json inválido: {e}",
                           'use {"addr": "BB:AAAA", "length": N, "evidence": "…"} ou {"pc": "0x1F0272", …}') from e
        if length <= 0:
            raise FabError(f"data[{i}] do mod.json: length tem de ser > 0 (veio {length})")
        out.append({"addr": shown, "length": length, "evidence": str(d["evidence"]).strip(),
                    "start_pc": start, "end_pc": start + length})
    return out


def data_coverage(regions: list[dict], start: int, end: int) -> dict | None:
    """A região de dados declarada que cobre INTEIRAMENTE [start, end) em PC; None se não houver.
    (Cobertura parcial NÃO conta: região de dados que estoura vira hijack com problema.)"""
    for r in regions:
        if r["start_pc"] <= start and end <= r["end_pc"]:
            return r
    return None


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


def build_mod(mod_dir: Path, quiet: bool = False, variant: dict | None = None) -> dict:
    """Monta o mod. `variant` = {"name": "off", "defines": {...}} monta a MESMA fonte com defines extra numa ROM
    à parte (`<id>.<name>.sfc`) — a base A/B de mods com código (ver `variant_safety`)."""
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
    suffix = f".{variant['name']}" if variant else ""
    out_rom = out_dir / f"{mod['id']}{suffix}.sfc"
    work = bytearray(clean)
    if mod.get("expand_to"):
        work = expand_rom(work, parse_size(mod["expand_to"]), img.mapping, img.header.offset)
    base_for_diff = bytes(work)
    for i, blob in enumerate(mod.get("blobs", [])):     # dados prontos num offset (ex.: área expandida): gerados pelo fab
        pc, raw = int(str(blob["pc"]), 0), (mod_dir / blob["file"]).read_bytes()
        if pc + len(raw) > len(work):
            raise FabError(f"blobs[{i}] ({blob['file']}) passa do fim da ROM", "aumente expand_to no mod.json")
        work[pc:pc + len(raw)] = raw
    if out_rom.exists():
        out_rom.chmod(0o666)
    out_rom.write_bytes(work)

    logs, warnings, errors, syms = [], [], [], {}
    for i, patch in enumerate(mod.get("patches", ["patch.asm"])):
        asm = (mod_dir / patch).resolve()
        if not asm.exists():
            raise FabError(f"patch não encontrado: {asm}")
        sym = out_dir / (f"{mod['id']}{suffix}.sym" if i == 0 else f"{mod['id']}{suffix}.{i}.sym")
        all_defines = {**(mod.get("defines") or {}), **((variant or {}).get("defines") or {})}
        defines = [f"-D{k}={v}" for k, v in all_defines.items()]
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
        "mod": mod["id"], "game": mod["game"], "built": now_iso(), "variant": variant,
        "rom": rel(out_rom), "asar": logs, "errors": errors, "warnings": warnings,
        "leak_warning": any("freespace_leaked" in w.lower() for w in warnings),
        "ok": not errors and all(entry["exit"] == 0 for entry in logs),
    }
    if not report["ok"]:
        write_json(out_dir / f"build{suffix}.json", report)
        raise FabError("o Asar falhou:\n  " + "\n  ".join(errors or [logs[-1]["output"][-800:]]),
                       "corrija o .asm (erros acima) e rode de novo")

    new = out_rom.read_bytes()
    data_regions = parse_data_regions(mod.get("data", []), img.mapping)
    regions = []
    hijacks = []
    # M/X declarados por hijack, indexados pelo OFFSET no arquivo: qualquer espelho do mesmo byte vale
    # (00:82CB ≡ 80:82CB em LoROM; C0:0312 ≡ 80:8312 no S-DD1, onde o código roda nas janelas $C0-$FF)
    flags_by_pc: dict[int, tuple[bool, bool]] = {}
    for h in mod.get("hijacks", []):
        addr = parse_addr(h["addr"])
        flags = (h.get("m", 8) == 8, h.get("x", 8) == 8)
        try:
            flags_by_pc[snes_to_pc(addr, img.mapping)] = flags
        except FabError as e:
            raise FabError(f"hijack {h['addr']} do mod.json não aponta para a ROM: {e.what}",
                           "use o endereço de CPU do ponto (ex.: 80:A420) — `fab addr <jogo> <endereço>` confere")
    for a, b in _diff_regions(base_for_diff, new):
        orig_bytes = base_for_diff[a:b]
        kind = "freespace" if all(x == 0 for x in orig_bytes) else "overwrite"
        if a >= img.header.offset - 0x10 and b <= img.header.offset + 0x40:
            kind = "header"
        # 'data' ganha de 'freespace': um byte declarado em data[] pode ter 0x00 no original
        # (é o caso das flags de cel marcadas) e não é espaço livre do Asar.
        dr = data_coverage(data_regions, a, b) if kind != "header" else None
        if dr:
            kind = "data"
        reg = {"kind": kind, "start": addr_or_pc(a, img.mapping), "end": addr_or_pc(b - 1, img.mapping),
               "pc": f"0x{a:06X}", "length": b - a}
        if kind == "data":
            reg["declared"] = dr["addr"]
            reg["evidence"] = dr["evidence"]
        if kind == "freespace" and new[a:a + 4] == b"STAR":
            size = (new[a + 4] | (new[a + 5] << 8)) + 1
            reg["rats"] = {"size": size, "code_start": addr_or_pc(a + 8, img.mapping)}
        if kind == "overwrite":
            snes_a = pc_to_snes(a, img.mapping)
            hint = flags_by_pc.get(a)
            m8, x8 = hint or (True, True)
            h = _hijack_report(base_for_diff, new, a, b, img.mapping, m8, x8, len(new))
            h["flags_source"] = "mod.json hijacks[] (m/x verificados)" if hint else "padrão m8,x8 (sem evidência!)"
            if hint is None:
                h["ok"] = False
                h["issues"].append(
                    f"sobrescrita NÃO declarada em {fmt_addr(snes_a)} (PC 0x{a:06X}, {b - a} B): se é um hijack, declare em "
                    "hijacks[] com o M/X medido; se é dado, em data[]; se não era para mexer aí, confira o org — no "
                    "S-DD1/LoROM o org é o endereço do Asar, não o da CPU (`fab addr <jogo> 0x<pc> --pc` mostra os dois)")
            hit = next((r for r in data_regions if r["start_pc"] < b and a < r["end_pc"]), None)
            if hit:
                h["ok"] = False
                h["issues"].append(
                    f"mudança estoura a região de dados declarada {hit['addr']} ({hit['length']} B): "
                    "corrija 'data[]' no mod.json ou declare-a como hijack com evidência")
            reg["hijack"] = h
            hijacks.append(h)
        prev = regions[-1] if regions else None
        if kind == "data" and prev and prev["kind"] == "data" and prev["declared"] == reg["declared"]:
            prev["end"] = reg["end"]                  # o mesmo bloco declarado (ex.: blob com zeros no meio): uma linha só
            prev["length"] = b - int(prev["pc"], 16)
            continue
        regions.append(reg)
    report["regions"] = regions
    report["hijacks"] = hijacks
    grown = expansion_notes(img.mapping, len(img.data), len(new))
    if grown:
        report["rom_expandida"] = grown          # quem roda a ROM que cresceu (pedido: recomendar emuladores)
    # tamanho de cada instrução do NOSSO código × M/X real (pega `lda #$08` montado como A9 08 00 com M=8)
    entries = []
    for h in hijacks:
        if h.get("is_long_jump") and h.get("jump_target"):
            m8, x8 = (h["assumed_flags"].split(",")[0] == "m8"), (h["assumed_flags"].split(",")[1] == "x8")
            entries.append((parse_addr(h["jump_target"]), m8, x8))
    for h in mod.get("hijacks", []):          # pontos extras do nosso código (ex.: depois de bytes originais copiados)
        for v in h.get("verify", []):
            if v.get("label") in syms:
                entries.append((syms[v["label"]], v.get("m", 8) == 8, v.get("x", 8) == 8))
    code_issues, n_ins = [], 0
    for i in range(len(mod.get("patches", ["patch.asm"]))):
        sym = out_dir / (f"{mod['id']}{suffix}.sym" if i == 0 else f"{mod['id']}{suffix}.{i}.sym")
        cw = verify_code_widths(new, img.mapping, sym, entries)
        code_issues += cw["issues"]
        n_ins += cw["instructions"]
    report["code_check"] = {"instructions_checked": n_ins, "issues": code_issues}
    if code_issues:
        report["ok"] = False
    report["data"] = []
    for dr in data_regions:
        seg_base = base_for_diff[dr["start_pc"]:dr["end_pc"]]
        seg_new = new[dr["start_pc"]:dr["end_pc"]]
        changed = sum(1 for x, y in zip(seg_base, seg_new) if x != y)
        entry = {"addr": dr["addr"], "length": dr["length"], "evidence": dr["evidence"],
                 "bytes_changed": changed, "ok": changed > 0}
        if changed == 0:
            entry["issue"] = "nenhum byte mudou aqui: o patch não escreveu na região declarada"
        report["data"].append(entry)
    report["labels"] = {k: fmt_addr(v) for k, v in sorted(syms.items(), key=lambda kv: kv[1])}
    report["sha256"] = sha256_bytes(new)
    # BPS sobre a base limpa original (sem expansão); a variante (base A/B) não gera BPS de distribuição
    if variant:
        report["bps"], report["bps_size"] = None, 0
    else:
        patch = bps.create(clean, new, metadata=f"snesfab mod {mod['id']} for {game['title']} ({game['hashes']['clean_sha256'][:16]})")
        assert bps.apply(clean, patch) == new
        bps_path = out_dir / f"{mod['id']}.bps"
        bps_path.write_bytes(patch)
        report["bps"] = rel(bps_path)
        report["bps_size"] = len(patch)
    if any(not h["ok"] for h in hijacks):
        report["ok"] = False
    write_json(out_dir / f"build{suffix}.json", report)
    return report


def variant_safety(main: dict, var: dict) -> dict:
    """A variante (base A/B) só pode mudar VALORES: mesmo layout (rótulos iguais), nenhum OPCODE diferente.
    Assim o código executado tem o mesmo tamanho e ciclos — o timing (e o RNG do jogo) não descola.
    ⚠ Mude valores que são ESCRITOS (cores, tabelas), nunca valores COMPARADOS (o desvio tomado muda o tempo)."""
    from .paths import ROOT
    issues = []
    if main.get("labels") != var.get("labels"):
        diff = sorted(set(main.get("labels", {}).items()) ^ set(var.get("labels", {}).items()))[:6]
        issues.append(f"o layout do código mudou entre o mod e a variante (rótulos diferentes: {diff}) — o timing muda")
    a, b = (ROOT / main["rom"]).read_bytes(), (ROOT / var["rom"]).read_bytes()
    diffs = [i for i in range(min(len(a), len(b))) if a[i] != b[i]] if len(a) == len(b) else []
    if len(a) != len(b):
        issues.append("as ROMs têm tamanhos diferentes")
    mapping = load_rom(ROOT / main["rom"]).mapping
    starts = set()
    out_dir, mid = (ROOT / main["rom"]).parent, main["mod"]
    main_syms = [out_dir / f"{mid}.sym", *sorted(out_dir.glob(f"{mid}.[0-9]*.sym"))]   # só os do build principal
    for sym in main_syms:
        rows, files = parse_sym_lines(sym)
        cache: dict[int, list[str]] = {}
        for addr, f, n in rows:
            if f not in cache:
                try:
                    cache[f] = files[f].read_text(encoding="utf-8", errors="replace").splitlines()
                except (KeyError, OSError):
                    cache[f] = []
            text = cache[f][n - 1] if 0 < n <= len(cache[f]) else ""
            if _source_instruction(text) is None:
                continue                                   # linha de dado (db/dw): mudar o valor é permitido
            bank, off = (addr >> 16) & 0xFF, addr & 0xFFFF
            try:
                starts.add(((bank & 0x7F) << 15) | (off & 0x7FFF) if mapping in ("lorom", "sdd1") else snes_to_pc(addr, mapping))
            except FabError:
                pass
    bad = [i for i in diffs if i in starts]               # o byte que muda é o OPCODE de uma instrução nossa
    if bad:
        issues.append(f"{len(bad)} OPCODE(s) diferentes (ex.: PC 0x{bad[0]:06X}): a variante muda instruções, não só valores")
    return {"bytes_diferentes": len(diffs), "ok": not issues, "issues": issues,
            "regra": "a variante só pode trocar valores escritos (cores/tabelas); nada de instruções nem comparações"}


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
