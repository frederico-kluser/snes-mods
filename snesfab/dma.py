"""Log de DMA/HDMA por frame (qualquer ROM): de onde vêm a PALETA, o OAM e os GRÁFICOS, e que instrução dispara
cada transferência. Responde às perguntas que travam qualquer pintura/edição de sprite:

- Onde fica o buffer de paletas na WRAM e quem o manda para a CGRAM? (ponto de hook para truques de paleta)
- Onde fica a sombra do OAM? (ponto de hook para mexer em sprites antes de irem para a tela)
- Os gráficos vêm CRUS da ROM (editáveis direto) ou passam por descompressão (buffer na WRAM, chip)?

O harness registra cada escrita em MDMAEN/HDMAEN por qualquer banco-espelho (`job.dma_log`); aqui agrupamos,
reconstruímos a instrução que escreveu ($420B) a partir do PC seguinte e conferimos se o que foi para a VRAM é
igual aos bytes da ROM de origem (gráfico cru) usando o snapshot do PPU do mesmo frame.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .disasm65816 import find_access_before
from .rom import fmt_addr, wram_offset
from .util import FabError

B_BUS = {0x18: "VRAM", 0x19: "VRAM", 0x04: "OAM", 0x22: "CGRAM", 0x80: "WRAM",
         0x21: "CGRAM-endereço", 0x16: "VRAM-endereço", 0x02: "OAM-endereço"}


def read_dma(run_dir: Path) -> list[dict]:
    p = Path(run_dir) / "dma.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def describe_source(addr: int, rom) -> dict:
    """Fonte A-bus de 24 bits → WRAM (7E:xxxx), ROM (PC) ou outro."""
    w = wram_offset(addr)
    if w is not None:
        return {"tipo": "WRAM", "addr": f"7E:{w:04X}" if w < 0x10000 else f"7F:{w - 0x10000:04X}", "offset": w}
    try:
        pc = rom.to_pc(addr)
        return {"tipo": "ROM", "addr": fmt_addr(addr), "pc": pc}
    except FabError:
        return {"tipo": "?", "addr": fmt_addr(addr)}


def trigger_instruction(ev: dict, rom) -> str | None:
    """A instrução que escreveu MDMAEN/HDMAEN (o harness vê o PC SEGUINTE)."""
    k_pc = (ev["k"] << 16) | ev["pc"]
    try:
        pos = rom.to_pc(k_pc)
    except FabError:
        return None
    m8, x8 = bool(ev["ps"] & 0x20), bool(ev["ps"] & 0x10)
    cands = find_access_before(rom.data, pos, k_pc, m8, x8, write=True)
    return cands[0].fmt() if cands else None


def summarize(events: list[dict], rom, snaps: dict | None = None) -> dict:
    """Agrupa as transferências (destino, fonte, tamanho, quem dispara) e explica cada grupo."""
    groups: dict[tuple, dict] = {}
    for ev in events:
        dest = B_BUS.get(ev["bbad"], f"$21{ev['bbad']:02X}")
        reverse = bool(ev["dmap"] & 0x80)
        size = ev["size"] or 0x10000
        if dest == "VRAM":
            dst = f"palavra ${ev['vram']:04X}" if ev.get("vram") is not None else "?"
        elif dest == "CGRAM":
            dst = f"cor {ev['cgram']}" if ev.get("cgram") is not None else "?"
        elif dest == "OAM":
            dst = f"byte ${ev['oam']:03X}" if ev.get("oam") is not None else "?"
        else:
            dst = ""
        key = (ev["kind"], dest, ev["src"], size if ev["kind"] == "dma" else 0, ev["k"], ev["pc"], dst, reverse)
        g = groups.setdefault(key, {"kind": ev["kind"], "destino": dest, "onde": dst, "fonte": ev["src"], "tamanho": size,
                                    "trigger": ((ev["k"] << 16) | ev["pc"]), "ps": ev["ps"], "frames": [], "ev": ev,
                                    "reverso": reverse})
        g["frames"].append(ev["frame"])
    rows = []
    for g in sorted(groups.values(), key=lambda g: (g["destino"], -len(g["frames"]))):
        src = describe_source(g["fonte"], rom)
        n_frames = len(set(g["frames"]))
        row = {"tipo": g["kind"], "destino": g["destino"], "onde": g["onde"], "bytes": g["tamanho"] if g["kind"] == "dma" else None,
               "fonte": src["addr"], "fonte_tipo": src["tipo"], "vezes": len(g["frames"]), "frames": n_frames,
               "primeiro_frame": min(g["frames"]), "dispara_pc_seguinte": fmt_addr(g["trigger"]),
               "m/x": ("m8" if g["ps"] & 0x20 else "m16") + "," + ("x8" if g["ps"] & 0x10 else "x16")}
        ins = trigger_instruction(g["ev"], rom)
        if ins:
            row["instrucao"] = ins
        if src["tipo"] == "ROM":
            row["pc_rom"] = f"0x{src['pc']:06X}"
            if g["destino"] == "VRAM" and snaps and g["kind"] == "dma" and not g["reverso"]:
                row["cru"] = _raw_in_vram(g, src["pc"], rom, snaps)
        row["leitura"] = _explain(row, g)
        rows.append(row)
    return {"transferencias": rows, "eventos": len(events), "resumo": _headline(rows)}


def _raw_in_vram(g: dict, pc: int, rom, snaps: dict) -> bool | None:
    """Os bytes que foram para a VRAM são IGUAIS aos da ROM? (gráfico cru → editável direto na ROM)."""
    ev = g["ev"]
    if ev.get("vram") is None:
        return None
    start = (ev["vram"] * 2) & 0xFFFF
    n = min(g["tamanho"], 0x10000 - start, 4096)
    want = rom.data[pc:pc + n]
    for f in sorted(set(g["frames"])):
        for ff in (f, f + 1):
            s = snaps.get(ff)
            if s is not None and bytes(s.vram[start:start + n]) == bytes(want):
                return True
    seen = [snaps.get(f) or snaps.get(f + 1) for f in set(g["frames"])]
    return False if any(seen) else None


def _explain(row: dict, g: dict) -> str:
    d, t = row["destino"], row["fonte_tipo"]
    every = row["frames"] > 1
    if row["tipo"] == "hdma":
        if d == "CGRAM" or d == "CGRAM-endereço":
            return "HDMA na paleta: a cor muda de linha para linha (degradê) — a falsa cor desses píxeis falha"
        return f"HDMA para {d}: efeito por linha (scroll/janela/cor)"
    if d == "CGRAM":
        base = "buffer de PALETAS na WRAM: mude cores nele (ou na origem dele) e o jogo copia para a CGRAM" if t == "WRAM" \
            else "paleta copiada direto da ROM para a CGRAM"
        return base + (" — todo frame" if every else " — só às vezes (na troca de tela/carga)") + \
            f"; a instrução em {row['dispara_pc_seguinte']} (antes dela) é um ponto de hook para truques de paleta"
    if d == "OAM":
        return ("SOMBRA do OAM na WRAM: os sprites do frame são montados nela antes deste DMA — ponto de hook para mexer "
                "em sprites (paleta/tile) depois que o jogo os monta") if t == "WRAM" else "OAM carregado direto da ROM"
    if d == "VRAM":
        if t == "WRAM":
            return "gráficos montados/DESCOMPRIMIDOS num buffer da WRAM antes de irem para a VRAM (compressão por software)"
        if row.get("cru") is True:
            return "gráficos CRUS da ROM (iguais na VRAM): dá para editar o desenho direto na ROM"
        if row.get("cru") is False:
            return "gráficos da ROM que chegam DIFERENTES na VRAM: compressão em hardware (S-DD1/SA-1…) ou transformação"
        return "gráficos lidos da ROM (sem snapshot da VRAM para conferir se são crus)"
    return f"DMA para {d}"


PPU_DESTS = {0x18, 0x19, 0x04, 0x22}       # VRAM, OAM, CGRAM: só podem ser escritos no VBlank/forced blank


def active_display_dmas(events: list[dict], visible_lines: int = 225) -> list[dict]:
    """DMAs para VRAM/OAM/CGRAM com o display LIGADO no meio da imagem: o PPU ignora/corrompe essas escritas.
    Num mod com código, aparecer aqui o que na ROM limpa caía no VBlank = o hook ESTOUROU o VBlank."""
    out = []
    for e in events:
        if e["kind"] != "dma" or e["bbad"] not in PPU_DESTS:
            continue
        sl = e.get("scanline")
        if sl is not None and 0 <= int(sl) < visible_lines and e.get("fb") is False:
            out.append(e)
    return out


def vblank_budget(base_events: list[dict], mod_events: list[dict]) -> dict:
    """Compara mod × base: DMAs que passaram para a área visível (estouro de VBlank) e a linha média de cada grupo."""
    def key(e):
        return (e["bbad"], e["src"] >> 16, e["k"], e["pc"])
    bad_base = {key(e) for e in active_display_dmas(base_events)}
    bad_mod = [e for e in active_display_dmas(mod_events) if key(e) not in bad_base]
    lines = defaultdict(list)
    for e in mod_events:
        if e["kind"] == "dma" and e["bbad"] in PPU_DESTS and e.get("scanline") is not None:
            lines[B_BUS.get(e["bbad"], "?")].append(int(e["scanline"]))
    base_lines = defaultdict(list)
    for e in base_events:
        if e["kind"] == "dma" and e["bbad"] in PPU_DESTS and e.get("scanline") is not None:
            base_lines[B_BUS.get(e["bbad"], "?")].append(int(e["scanline"]))
    resumo = {d: {"base": sorted(set(base_lines[d]))[:6], "mod": sorted(set(v))[:6]} for d, v in lines.items()}
    custo = {}
    for d, v in lines.items():
        if base_lines.get(d):
            b, m = sorted(base_lines[d])[len(base_lines[d]) // 2], sorted(v)[len(v) // 2]
            if m != b:
                custo[d] = f"o DMA de {d} passou da linha {b} para a {m} ({(m - b) % 262} linhas de VBlank a mais)"
    ok = not bad_mod
    return {"ok": ok, "estouros": len(bad_mod), "exemplos": [{"frame": e["frame"], "linha": e["scanline"],
                                                              "destino": B_BUS.get(e["bbad"], "?")} for e in bad_mod[:6]],
            "linhas": resumo, "custo": custo,
            "leitura": ("o código do mod cabe no VBlank" + (" — " + "; ".join(custo.values()) if custo else "")) if ok else
                       "ESTOURO DE VBLANK: o hook demora demais e o DMA cai com a imagem sendo desenhada (gráficos/sprites "
                       "corrompidos). Encurte o código no VBlank ou mova o trabalho para fora dele (hook no escritor do OAM)"}


def _headline(rows: list[dict]) -> list[str]:
    out = []
    pal = [r for r in rows if r["destino"] == "CGRAM" and r["tipo"] == "dma"]
    if pal:
        r = max(pal, key=lambda r: r["vezes"])
        out.append(f"paleta: {r['fonte_tipo']} {r['fonte']} → CGRAM ({r['bytes']} B, {r['onde']}), {r['frames']} frame(s); "
                   f"dispara antes de {r['dispara_pc_seguinte']} ({r['m/x']})")
    oam = [r for r in rows if r["destino"] == "OAM" and r["tipo"] == "dma"]
    if oam:
        r = max(oam, key=lambda r: r["vezes"])
        out.append(f"OAM: {r['fonte_tipo']} {r['fonte']} → OAM ({r['bytes']} B), {r['frames']} frame(s); "
                   f"dispara antes de {r['dispara_pc_seguinte']}")
    vram = [r for r in rows if r["destino"] == "VRAM" and r["tipo"] == "dma"]
    if vram:
        kinds = defaultdict(int)
        for r in vram:
            kinds["crus da ROM" if r.get("cru") else "WRAM (descomprimidos)" if r["fonte_tipo"] == "WRAM"
                  else "ROM transformada (chip/compressão)" if r.get("cru") is False else "ROM (não conferido)"] += r["vezes"]
        out.append("gráficos para a VRAM: " + ", ".join(f"{k}: {v}" for k, v in kinds.items()))
    if any(r["tipo"] == "hdma" and r["destino"].startswith("CGRAM") for r in rows):
        out.append("⚠ há HDMA na paleta (degradê por linha)")
    return out
