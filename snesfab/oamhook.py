"""Gerador do mecanismo de NÍVEL 2 (qualquer jogo): paleta-espelho por tabela de tiles, num hook antes do DMA do OAM.

Quando a peça a pintar divide índices de cor com outra (luva × cabelo) mas cada NÚMERO de tile é sempre de uma
peça só (`fab sprite census` → separabilidade nível 2), basta, a cada frame, depois que o jogo montou a sombra
do OAM e antes de ela ir para o PPU:
  1. trocar a paleta dos sprites (paleta OAM = origem) cujo tile está na tabela para uma paleta OAM LIVRE;
  2. deixar nessa paleta livre uma CÓPIA da original com só os índices-alvo trocados (pele/contorno idênticos).

Tudo o que o agente informa sai de comandos do fab: sombra do OAM e instrução que dispara o DMA (`fab ppu dma`),
paleta de origem e paleta livre (`fab sprite snap` → overview.png/palettes.png), tiles (`fab sprite census`) e
cores (`fab palette ramp`). O gerador escolhe instruções inteiras para o hijack (≥ 4 bytes, sem desvios),
copia os bytes originais, decide o modo da paleta pelo log de DMA (buffer na WRAM ou CGRAM direto) e escreve o
.asm com sufixos de tamanho explícitos.
"""

from __future__ import annotations

import re
from pathlib import Path

from .disasm65816 import BRANCHES, ENDS_FLOW, disassemble
from .rom import ASAR_DIRECTIVE, asar_org, fmt_addr
from .util import FabError

CONTROL = BRANCHES | ENDS_FLOW | {"JSR", "JSL", "RTS", "RTL", "RTI", "BRK", "COP", "WAI", "STP", "PER", "PHK", "PLB",
                                  "PLD", "PLP", "TCS", "TXS", "XCE"}
MDMAEN = re.compile(r"^\$(?:[0-9A-F]{2})?420B$")          # STA $420B / STA $00420B (sem índice)
REL8 = {0x10, 0x30, 0x50, 0x70, 0x80, 0x90, 0xB0, 0xD0, 0xF0}


def incoming_jumps(rom, start: int, end: int, cpu_addr: int) -> list[str]:
    """Desvios que podem cair no MEIO da janela do hijack (depois do 1.º byte) — o JML de 4 bytes quebraria quem
    pula para lá. Busca linear, pode dar falso positivo em dado: branches a até ±128 B, JMP/JSR absolutos no mesmo
    banco da CPU e JML/JSL em toda a ROM. Confirme com `fab probe exec` no endereço apontado."""
    data, inside = rom.data, range(start + 1, end)
    out = []
    for p in range(max(0, start - 130), min(len(data) - 2, end + 130)):
        op = data[p]
        if op in REL8:
            t = p + 2 + (data[p + 1] - 256 if data[p + 1] >= 128 else data[p + 1])
        elif op == 0x82:
            off = data[p + 1] | (data[p + 2] << 8)
            t = p + 3 + (off - 65536 if off >= 32768 else off)
        else:
            continue
        if t in inside:
            out.append(f"possível desvio relativo em PC 0x{p:06X} para PC 0x{t:06X}, dentro do hijack")
    bank = cpu_addr & 0xFF0000
    lo16 = {((cpu_addr & 0xFFFF) + i) & 0xFFFF for i in range(1, end - start)}
    try:
        b0 = rom.to_pc(bank | 0x8000) & ~0x7FFF
        b1 = b0 + (0x10000 if rom.to_pc(bank | 0xFFFF) - rom.to_pc(bank | 0x8000) > 0x7FFF else 0x8000)
    except FabError:
        b0, b1 = max(0, start - 0x8000), min(len(data), end + 0x8000)
    for op in (0x4C, 0x20):
        for a in lo16:
            pat = bytes((op, a & 0xFF, a >> 8))
            p = data.find(pat, b0, b1)
            while p != -1:
                out.append(f"possível {'JMP' if op == 0x4C else 'JSR'} em PC 0x{p:06X} para {fmt_addr(bank | a)}, dentro do hijack")
                p = data.find(pat, p + 1, b1)
    for op in (0x5C, 0x22):
        for a in lo16:
            for bk in {bank >> 16, (bank >> 16) ^ 0x80}:
                pat = bytes((op, a & 0xFF, a >> 8, bk))
                if pat in data:
                    out.append(f"possível {'JML' if op == 0x5C else 'JSL'} em PC 0x{data.find(pat):06X} para "
                               f"{fmt_addr((bk << 16) | a)}, dentro do hijack")
    return out


def choose_hijack(rom, trigger_next: int, m8: bool, x8: bool, stores: tuple[str, ...] = ("STA", "STX", "STY")) -> dict:
    """Instruções INTEIRAS que terminam na que dispara o DMA (STA/STX/STY $420B; o harness vê o PC seguinte) e
    somam ≥ 4 bytes, sem desvio/pilha. Procura o início para trás e confirma desmontando para a frente até cair
    exatamente no fim. Devolve também o tamanho de cada instrução e os avisos de desvio para dentro da janela."""
    end_pc = rom.to_pc(trigger_next)
    for back in range(4, 12):
        start = end_pc - back
        if start < 0:
            continue
        addr = (trigger_next & 0xFF0000) | ((trigger_next - back) & 0xFFFF)
        ins = disassemble(rom.data[start:end_pc + 4], addr, length=back, m8=m8, x8=x8)
        if sum(i.size for i in ins) != back or not ins:
            continue
        if any(i.mnemonic in CONTROL or i.mnemonic in ("SEP", "REP") for i in ins):
            continue
        if ins[-1].mnemonic not in stores or not MDMAEN.match(ins[-1].operand.upper()):
            continue
        return {"addr": addr, "pc": start, "length": back, "bytes": rom.data[start:end_pc],
                "instructions": [i.fmt() for i in ins], "sizes": [i.size for i in ins], "store": ins[-1].mnemonic,
                "return": trigger_next, "avisos": incoming_jumps(rom, start, end_pc, addr)}
    raise FabError(f"não achei instruções inteiras (≥4 bytes, sem desvios) terminando antes de {fmt_addr(trigger_next)}",
                   "escolha o hijack à mão (fab disasm) e declare-o em hijacks[] com o M/X medido")


def generate(*, rom, oam_shadow: int, trigger_next: int, m8: bool, x8: bool, src_palette: int, mirror_palette: int,
             tiles: list[int], colors: dict[int, int], pal_buffer: int | None, evidence: str) -> tuple[str, dict]:
    """O .asm do mecanismo e o registro do hijack para o mod.json. Roda no VBlank (antes do DMA do OAM), por isso
    é enxuto: índices de 8 bits, 4 sprites por volta do laço e descarte imediato dos sprites desligados (Y ≥ 224).
    Confira SEMPRE o orçamento com `fab paint check` (seção vblank)."""
    if not (0 <= src_palette <= 7 and 0 <= mirror_palette <= 7) or src_palette == mirror_palette:
        raise FabError("paletas OAM inválidas", "origem e espelho entre 0 e 7, diferentes (o espelho tem de estar LIVRE)")
    if not tiles:
        raise FabError("nenhum tile na tabela", "use os 'tiles_seguros' do fab sprite census (nível 2)")
    hj = choose_hijack(rom, trigger_next, m8, x8)
    shadow_bank, shadow_lo = (oam_shadow >> 16) & 0xFF, oam_shadow & 0xFFFF
    table = bytearray(512)
    for t in tiles:
        table[t & 0x1FF] = 1
    flags = ("m8" if m8 else "m16") + "," + ("x8" if x8 else "x16")
    src2, mir2 = src_palette << 1, mirror_palette << 1
    L = ["; GERADO por `fab paint oam-mirror` — NÃO edite à mão (refaça o comando).",
         f"; {evidence}",
         f"; paleta-espelho por tabela de tiles: sprites da paleta OAM {src_palette} com tile na tabela → paleta OAM "
         f"{mirror_palette} (CGRAM {mirror_palette + 8}), cópia da {src_palette} com os índices {sorted(colors)} trocados.",
         ASAR_DIRECTIVE[rom.mapping], "",
         f"; hijack: {hj['length']} B de instruções inteiras antes do DMA do OAM ({flags}):"]
    L += [f";   {i}" for i in hj["instructions"]]
    L += [f"org ${asar_org(hj['pc'], rom.mapping):06X}", "    autoclean jml OamEspelho"] + ["    nop"] * (hj["length"] - 4)
    L += ["", "freecode", "OamEspelho:", "    php", "    rep #$30", "    pha", "    phx", "    phy", "    phb",
          f"    pea.w ${shadow_bank:02X}{shadow_bank:02X}      ; DBR = banco da sombra do OAM", "    plb", "    plb",
          "    sep #$30                 ; A, X e Y de 8 bits: a sombra é varrida em 2 metades de 256 bytes"]
    for half in (0, 1):
        base = shadow_lo + 0x100 * half
        tab = f"Tab{half}"
        L += ["    ldy.b #$00", f".metade{half}"]
        for k in range(4):
            o = base + 4 * k
            skip = f".pula{half}_{k}"
            L += [f"    lda.w ${o + 1:04X},y        ; Y do sprite",
                  "    cmp.b #$E0",
                  f"    bcs {skip}               ; Y >= 224: desligado/fora da tela",
                  f"    lda.w ${o + 3:04X},y        ; atributo vhoopppN",
                  "    and.b #$0E",
                  f"    cmp.b #${src2:02X}            ; paleta de origem?",
                  f"    bne {skip}",
                  f"    lda.w ${o + 3:04X},y",
                  "    lsr                      ; C = bit 8 do nº do tile",
                  f"    lda.w ${o + 2:04X},y        ; nº do tile (8 bits baixos)",
                  "    tax",
                  f"    bcs .alta{half}_{k}",
                  f"    lda.l {tab}Baixa,x",
                  f"    bra .tem{half}_{k}",
                  f".alta{half}_{k}",
                  f"    lda.l {tab}Alta,x",
                  f".tem{half}_{k}",
                  f"    beq {skip}",
                  f"    lda.w ${o + 3:04X},y",
                  "    and.b #$F1",
                  f"    ora.b #${mir2:02X}            ; → paleta-espelho",
                  f"    sta.w ${o + 3:04X},y",
                  skip]
        L += ["    tya", "    clc", "    adc.b #$10", "    tay",
              f"    beq .fim{half}             ; o corpo desenrolado passa de 128 B: bne não alcança",
              f"    brl .metade{half}", f".fim{half}"]
    if pal_buffer is not None:
        src = pal_buffer + 2 * (128 + 16 * src_palette)
        dst = pal_buffer + 2 * (128 + 16 * mirror_palette)
        L += ["; modo BUFFER: o jogo copia o buffer de paletas da WRAM para a CGRAM (fab ppu dma) — o espelho vai nele",
              "    rep #$20", "    ldx.b #$00               ; X = 2·índice da cor", ".cor",
              f"    lda.l ${src:06X},x          ; cor da linha de origem",
              "    and.l TrocaInv,x", "    ora.l NovaCor,x",
              f"    sta.l ${dst:06X},x          ; linha do espelho",
              "    inx", "    inx", "    cpx.b #$20", "    bne .cor", "    sep #$20"]
    else:
        L += ["; modo CGRAM: sem buffer de paletas, lê a linha de origem da CGRAM e escreve a do espelho (VBlank)",
              "    pea.w $0000              ; DBR = $00 (registradores do PPU)", "    plb", "    plb",
              "    ldx.b #$00               ; X = 2·índice da cor", ".cor", "    txa", "    lsr",
              f"    ora.b #${128 + 16 * src_palette:02X}", "    sta.w $2121", "    lda.w $213B              ; baixo",
              "    xba", "    lda.w $213B              ; alto", "    xba                      ; A = baixo, B = alto",
              "    pha", "    lda.l Troca,x", "    beq .mantem", "    pla", "    lda.l NovaCor,x", "    xba",
              "    lda.l NovaCor+1,x", "    xba", "    pha", ".mantem", "    txa", "    lsr",
              f"    ora.b #${128 + 16 * mirror_palette:02X}", "    sta.w $2121", "    pla", "    sta.w $2122", "    xba",
              "    sta.w $2122", "    inx", "    inx", "    cpx.b #$20", "    bne .cor"]
    mask = [0xFFFF if i in colors else 0 for i in range(16)]
    newc = [colors.get(i, 0) & 0x7FFF for i in range(16)]
    L += ["    plb", "    rep #$30", "    ply", "    plx", "    pla", "    plp",
          "    ; instruções originais substituídas pelo hijack (bytes copiados, sem desvios):",
          "    db " + ",".join(f"${b:02X}" for b in hj["bytes"]),
          f"    jml ${hj['return']:06X}", "",
          "Troca:                   ; 1 = este índice da paleta muda (um byte por cor, passo 2)",
          "    db " + ",".join("$01,$00" if m else "$00,$00" for m in mask),
          "TrocaInv:", "    dw " + ", ".join(f"${(~m) & 0xFFFF:04X}" for m in mask),
          "NovaCor:", "    dw " + ", ".join(f"${c & m:04X}" for c, m in zip(newc, mask))]
    for half in (0, 1):
        for part, sl in (("Baixa", slice(0, 256)), ("Alta", slice(256, 512))):
            L.append(f"Tab{half}{part}:          ; 1 = tile {'0-255' if part == 'Baixa' else '256-511'} vai para o espelho")
            data = table[sl]
            for i in range(0, 256, 32):
                L.append("    db " + ",".join(f"${b:02X}" for b in data[i:i + 32]))
    hijack = {"addr": fmt_addr(rom.to_snes(hj["pc"])), "m": 8 if m8 else 16, "x": 8 if x8 else 16, "source": "oam-mirror",
              "evidence": f"fab ppu dma: o DMA do OAM é disparado antes de {fmt_addr(trigger_next)} com {flags}; "
                          f"hijack = {hj['length']} B de instruções inteiras: " + " | ".join(
                              i.split('  ', 1)[-1].strip() for i in hj["instructions"])}
    return "\n".join(L) + "\n", hijack


def parse_tiles(text: str) -> list[int]:
    out = []
    for part in str(text).replace(";", ",").split(","):
        part = part.strip()
        if part:
            out.append(int(part.lstrip("$"), 16) if part.startswith("$") else int(part, 0))
    return out


def save(mod_dir: Path, asm: str, hijack: dict) -> dict:
    """Grava oam_mirror.asm e liga no mod.json (patches + hijacks[] com source=oam-mirror)."""
    import json

    from .util import write_json
    (mod_dir / "oam_mirror.asm").write_text(asm, encoding="utf-8", newline="\n")
    mj = mod_dir / "mod.json"
    raw = json.loads(mj.read_text(encoding="utf-8"))
    patches = raw.get("patches") or (["patch.asm"] if (mod_dir / "patch.asm").exists() else [])
    if "oam_mirror.asm" not in patches:
        patches.append("oam_mirror.asm")
    raw["patches"] = patches
    raw["hijacks"] = [h for h in raw.get("hijacks", []) if h.get("source") != "oam-mirror"] + [hijack]
    write_json(mj, raw)
    return {"asm": str(mod_dir / "oam_mirror.asm"), "patches": patches, "hijack": hijack}

