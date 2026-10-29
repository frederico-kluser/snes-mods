"""Override de gráfico SEM codec: muda o desenho de gráficos comprimidos de QUALQUER jogo.

Todo gráfico passa pela VRAM, e o `fab gfx dump` grava o que cada DMA deixou lá (já descomprimido) e de onde veio.
Quando o desenho não está cru na ROM (chip que descomprime no DMA, ou descompressão por software num buffer da
WRAM), não é preciso conhecer o formato:
  1. o bloco EDITADO vai cru para a ROM (espaço livre, área expandida ou offset informado), um por upload editado;
  2. um hook na instrução que dispara o DMA (STA/STX/STY $420B) confere cada canal ligado contra uma TABELA:
     destino VRAM, fonte e tamanho iguais aos do upload capturado e — quando a fonte é um buffer da WRAM, que o jogo
     reaproveita para vários gráficos — os bytes do buffer iguais à IMPRESSÃO DIGITAL do bloco original. Batendo, a
     fonte do canal passa a ser a cópia editada;
  3. fonte de endereço FIXO (chip que descomprime no DMA): o canal volta a andar e, com `--chip-disarm`, o chip é
     desarmado naquele DMA (registro e valor tirados da evidência: o que o jogo escreve antes do DMA comprimido).
O código do hook tem tamanho fixo (a tabela cresce, o código não): cabe até em ROM quase cheia. ROM sem espaço:
`--expand` (no S-DD1 a área nova, acima de 4 MiB, é lida trocando a janela $F0-$FF só durante o DMA trocado).
Nada de descompressor ou tabela de terceiros: o dado editado nasce do que o próprio jogo pôs na VRAM.
Limites: cobre os disparos vistos nos cenários do dump (junte states/macros); upload não linear fica de fora; o
hook não restaura DMAP/fonte depois do DMA (jogos reescrevem os registros a cada DMA — confira com `fab gfx check`).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import gfx
from .oamhook import choose_hijack
from .rom import ASAR_DIRECTIVE, asar_org, cpu_view, fmt_addr, parse_addr
from .util import FabError, now_iso, rel, write_json

OVR_ASM = "gfx_override.asm"
OVR_BLOB = "gfx_override.bin"
OVR_BLOB_BASE = "gfx_override.base.bin"      # base A/B: cópias ORIGINAIS (mesmo layout), ver `variant_safety`
FP_WIDTH = 8                 # bytes da impressão digital (4 comparações de 16 bits)
ENTRY = 24                   # bytes por entrada da tabela
MAX_BLOCKS = 80              # o `prot` do Asar protege até 85 rótulos por área (hook, conferência, tabela, cópias)
MAX_BLOCK = 0x7FF8           # um bloco cabe num banco LoROM (32 KiB menos a etiqueta RATS)
STACK_SLOT = {"STA": 6, "STX": 4, "STY": 2}      # onde o registro do disparo fica depois de php/pha/phx/phy/phb
F_FIXED, F_DISARM, F_FP7E, F_FP7F = 0x01, 0x02, 0x04, 0x08


def _h(raw: bytes) -> str:
    return hashlib.sha1(raw).hexdigest()[:12]


@dataclass
class Block:
    kind: str                 # "wram" (buffer montado por software) | "rom" (fonte na ROM transformada no DMA)
    src: int                  # fonte do DMA (24 bits, como o jogo escreve em $43x2-$43x4)
    size: int
    data: bytes               # o que chegou na VRAM (original)
    new: bytes                # a cópia editada
    tiles: list               # [(offset no bloco, hash do tile original)]
    mode: int                 # DMAP do upload
    sites: dict               # PC seguinte ao disparo → {flags M/X vistas}
    frames: list
    fingerprint: list = field(default_factory=list)   # [(offset, bytes)] — só fonte WRAM
    label: str = ""


# ── dump ──────────────────────────────────────────────────────────────────────

def load_dump(dump_dir: Path) -> dict:
    """O dump do `fab gfx dump`: uploads (com os bytes), índice das folhas (nº → hash) e os cenários."""
    dump_dir = Path(dump_dir)
    meta_p = dump_dir / "tileset.json"
    if not meta_p.exists():
        raise FabError(f"{rel(dump_dir)} não é um dump do `fab gfx dump`", "rode `fab gfx dump <jogo> …` e passe o diretório")
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    uploads = []
    for d in sorted(dump_dir.glob("run-*")):
        for u in gfx.read_uploads(d):
            u["run"] = d.name
            uploads.append(u)
    if not uploads:
        raise FabError(f"{rel(dump_dir)} não guardou os uploads (vram_uploads.bin)", "refaça o `fab gfx dump` (versão atual)")
    if any("ps" not in u for u in uploads):
        raise FabError("dump antigo: os uploads não têm as flags M/X do disparo", "refaça o `fab gfx dump`")
    index = json.loads((dump_dir / "tiles.json").read_text(encoding="utf-8"))
    return {"dir": dump_dir, "meta": meta, "uploads": uploads, "index": index, "bpp": int(meta.get("bpp", 4))}


def parse_selection(text: str, index: list[dict]) -> list[str]:
    """'12,13,40-45' (nºs das folhas do dump) ou hashes de 12 hex → hashes, na ordem."""
    by_n = {int(t["n"]): t["hash"] for t in index}
    out = []
    for part in str(text).replace(";", ",").split(","):
        part = part.strip().lower()
        if not part:
            continue
        if re.fullmatch(r"[0-9a-f]{12}", part):
            out.append(part)
            continue
        a, _, b = part.partition("-")
        if not a.isdigit() or (b and not b.isdigit()):
            raise FabError(f"seleção inválida: {part!r}", "nºs das folhas (ex.: 12,13,40-45) ou hashes de 12 hex")
        for n in range(int(a), int(b or a) + 1):
            if n not in by_n:
                raise FabError(f"o tile nº {n} não existe no dump (1-{max(by_n)})", "use os nºs das folhas tiles-NN.png")
            out.append(by_n[n])
    return list(dict.fromkeys(out))


def parse_map(text: str, bpp: int) -> dict[int, int]:
    mapping = {}
    for pair in str(text).split(","):
        a, sep, b = pair.strip().partition(":")
        if not sep or not a.strip().isdigit() or not b.strip().isdigit():
            raise FabError(f"mapa inválido: {text!r}", "pares índice:índice, ex.: 14:9,15:12")
        mapping[int(a)] = int(b)
    top = (1 << bpp) - 1
    if any(not (0 <= k <= top and 0 <= v <= top) for k, v in mapping.items()):
        raise FabError(f"índice fora de 0-{top} no mapa {text!r}", f"com {bpp} bpp os índices vão de 0 a {top}")
    return mapping


def tile_bytes(dump: dict, hashes: list[str]) -> dict[str, bytes]:
    """Os bytes de cada tile pedido, tirados dos uploads (tiles só vistos no state não têm upload)."""
    tb = gfx.TILE_BYTES[dump["bpp"]]
    want, out = set(hashes), {}
    for u in dump["uploads"]:
        for o in gfx.tile_offsets(u, tb):
            raw = bytes(u["data"][o:o + tb])
            h = _h(raw)
            if h in want and h not in out:
                out[h] = raw
        if len(out) == len(want):
            break
    return out


def _find_raw(data: bytes, raw: bytes, limit: int = 8) -> list[int]:
    if not any(raw):
        return []
    hits, p = [], data.find(raw)
    while p != -1 and len(hits) < limit:
        hits.append(p)
        p = data.find(raw, p + 1)
    return hits


def add_edits(mod_dir: Path, dump: dict, hashes: list[str], mapping: dict[int, int], name: str, evidence: str,
              rom) -> dict:
    """Aplica o mapa de índices aos tiles escolhidos e grava no paint.json: desenho cru na ROM → "tiles" (patch de
    dados, igual ao `fab paint remap`); senão → "vram_tiles" (vai pelo override)."""
    from .paint import PAINT_JSON, _load_spec
    if not evidence.strip():
        raise FabError("falta a evidência", 'ex.: --evidence "fab gfx dump runs/…: tiles 12-13 = luva (folha tiles-01.png)"')
    bpp = dump["bpp"]
    raw = tile_bytes(dump, hashes)
    spec = _load_spec(mod_dir)
    spec.setdefault("tiles", [])
    spec.setdefault("vram_tiles", [])
    direct, via, same = [], [], []
    for h in hashes:
        if h not in raw:
            continue
        px = gfx.decode_tile(raw[h], bpp)
        new = px.copy()
        for a, b in mapping.items():
            new[px == a] = b
        if (new == px).all():
            same.append(h)
            continue
        entry = {"name": name, "hash": h, "bpp": bpp, "original": raw[h].hex(), "new": gfx.encode_tile(new, bpp).hex(),
                 "map": {str(k): v for k, v in mapping.items()}, "evidence": evidence.strip(), "updated": now_iso()}
        hits = _find_raw(rom.data, raw[h])
        if hits:
            for pc in hits:
                spec["tiles"] = [e for e in spec["tiles"] if int(e["pc"], 0) != pc]
                spec["tiles"].append({**entry, "pc": f"0x{pc:06X}"})
            direct.append({"hash": h, "rom": [f"0x{pc:06X}" for pc in hits]})
        else:
            spec["vram_tiles"] = [e for e in spec["vram_tiles"] if e["hash"] != h] + [entry]
            via.append(h)
    write_json(Path(mod_dir) / PAINT_JSON, spec)
    return {"crus_na_rom": direct, "via_override": via, "sem_mudanca": same,
            "sem_upload": [h for h in hashes if h not in raw]}


# ── plano ─────────────────────────────────────────────────────────────────────

def choose_fingerprint(content: bytes, others: list[bytes], src: int, width: int = FP_WIDTH) -> list[tuple[int, bytes]]:
    """A janela de `width` bytes do bloco original que o distingue de todos os OUTROS conteúdos vistos no mesmo
    buffer (mesma fonte e tamanho). Entre as que separam, a mais variada (robusta a conteúdos não vistos)."""
    lo = src & 0xFFFF
    low_ram = (src >> 16) & 0xFF not in (0x7E, 0x7F)            # $00-$3F:0000-1FFF = espelho dos 8 KiB de baixo
    cands = [o for o in range(0, len(content) - width + 1, 2)
             if ((lo + o) & 0xFFFF) <= 0x10000 - width and (not low_ram or lo + o + width <= 0x2000)]
    if not cands:
        raise FabError(f"bloco de {len(content)} B sem janela para impressão digital")

    def score(o: int) -> tuple[int, int, bool, int]:
        w = content[o:o + width]
        return sum(1 for c in others if c[o:o + width] != w), len(set(w)), any(w), -o

    best = max(cands, key=score)
    if any(c[best:best + width] == content[best:best + width] for c in others):
        raise FabError(f"o buffer {fmt_addr(src)} recebe desenhos que nenhuma janela de {width} B separa",
                       "edite também os outros desenhos desse buffer ou aumente a cobertura do dump")
    return [(best, content[best:best + width])]


def plan(dump: dict, edits: dict[str, bytes], rom) -> dict:
    """Blocos a sobrescrever: cada upload (fonte, tamanho e conteúdo) com tile editado, a cópia editada, a impressão
    digital (fonte WRAM) e os pontos de disparo; + o que ficou de fora e por quê."""
    tb = gfx.TILE_BYTES[dump["bpp"]]
    groups: dict[tuple, dict[bytes, list[dict]]] = defaultdict(dict)
    cache: dict = {}
    for u in dump["uploads"]:
        origin = gfx.upload_origin(u, rom, cache)
        if origin not in ("wram", "transformado"):
            continue                      # cru: patch de dados (paint.json "tiles"); fixo/?: não é desenho
        groups[("wram" if origin == "wram" else "rom", u["src"], u["size"])].setdefault(bytes(u["data"]), []).append(u)
    blocks, skipped = [], []
    for (kind, src, size), contents in groups.items():
        edited = []
        for content, ups in contents.items():
            hits = [(o, h) for o in gfx.tile_offsets(ups[0], tb) if (h := _h(content[o:o + tb])) in edits]
            if hits:
                edited.append((content, ups, hits))
        if not edited:
            continue
        where = f"{fmt_addr(src)} ({size} B)"
        if kind == "rom" and len(contents) > 1:
            skipped.append({"fonte": where, "motivo": f"a mesma fonte deu {len(contents)} desenhos diferentes na VRAM e o "
                                                      "dado só existe durante o DMA: sem impressão digital possível"})
            continue
        sites: dict[int, set] = {}
        for ups in contents.values():
            for u in ups:
                sites.setdefault((u["k"] << 16) | u["pc"], set()).add(u["ps"] & 0x30)
        for content, ups, hits in edited:
            if not all(u.get("linear") for u in ups):
                skipped.append({"fonte": where, "motivo": "upload não linear (incremento/remapeamento especial da VRAM): "
                                                          "a cópia crua não reproduziria o desenho"})
                continue
            if size > MAX_BLOCK:
                skipped.append({"fonte": where, "motivo": f"bloco maior que um banco ({MAX_BLOCK} B)"})
                continue
            new = bytearray(content)
            for o, h in hits:
                new[o:o + tb] = edits[h]
            try:
                fp = choose_fingerprint(content, [c for c in contents if c != content], src) if kind == "wram" else []
            except FabError as e:
                skipped.append({"fonte": where, "motivo": e.what})
                continue
            blocks.append(Block(kind, src, size, content, bytes(new), hits, ups[0]["mode"], sites,
                                sorted({u["frame"] for u in ups}), fp))
    for n, b in enumerate(blocks, 1):
        b.label = f"GfxNovo{n}"
    return {"blocks": blocks, "skipped": skipped}


# ── tabela e colocação ────────────────────────────────────────────────────────

def _entry_fields(b: Block, chip: bool) -> tuple[int, int, bytes]:
    """flags, endereço da impressão (16 bits) e os 8 bytes dela."""
    flags = (F_FIXED if b.mode & 0x18 else 0) | (F_DISARM if b.kind == "rom" and chip else 0)
    if not b.fingerprint:
        return flags, 0, bytes(FP_WIDTH)
    off, win = b.fingerprint[0]
    bank = (b.src >> 16) & 0xFF
    flags |= F_FP7F if bank == 0x7F else F_FP7E                 # espelho baixo ($00-$3F:0000-1FFF) = $7E
    return flags, ((b.src & 0xFFFF) + off) & 0xFFFF, win


def table_bytes(blocks: list[Block], new_src: dict[str, int], chip: bool) -> bytes:
    """Tabela de entradas de 24 bytes: +0 banco, +1 endereço e +3 tamanho da fonte; +5 endereço e +7 banco da cópia;
    +8 flags; +9 endereço da impressão; +11 DMAP original; +12 os 8 bytes da impressão."""
    out = bytearray()
    for b in blocks:
        flags, fa, fp = _entry_fields(b, chip)
        ns = new_src[b.label]
        out += bytes([(b.src >> 16) & 0xFF]) + (b.src & 0xFFFF).to_bytes(2, "little") + (b.size & 0xFFFF).to_bytes(2, "little")
        out += (ns & 0xFFFF).to_bytes(2, "little") + bytes([(ns >> 16) & 0xFF, flags]) + fa.to_bytes(2, "little")
        out += bytes([b.mode & 0xFF]) + fp + bytes(ENTRY - 20)
    return bytes(out)


def table_asm(blocks: list[Block], chip: bool) -> list[str]:
    """A mesma tabela em .asm, com as cópias por rótulo (espaço livre: o Asar escolhe onde ficam)."""
    out = []
    for i, b in enumerate(blocks, 1):
        flags, fa, fp = _entry_fields(b, chip)
        out += [f"    db ${(b.src >> 16) & 0xFF:02X} : dw ${b.src & 0xFFFF:04X}, ${b.size & 0xFFFF:04X}   ; {i}: fonte {fmt_addr(b.src)}",
                f"    dw {b.label}&$FFFF : db {b.label}>>16, ${flags:02X} : dw ${fa:04X} : db ${b.mode & 0xFF:02X}",
                "    db " + ",".join(f"${x:02X}" for x in fp) + "," + ",".join("$00" for _ in range(ENTRY - 20))]
    return out


def place(sizes: list[int], start: int, rom) -> list[int]:
    """Offsets consecutivos a partir de `start`, sem cruzar banco da CPU (nem o DMA nem a leitura da tabela passam
    de um banco para outro) e, numa janela de chip, sem sair da página da janela."""
    out, pc = [], start
    for n in sizes:
        while True:
            try:
                a, wa = cpu_view(pc, rom.mapping)
                z, wz = cpu_view(pc + n - 1, rom.mapping)
            except FabError as e:
                raise FabError(f"0x{pc:X} + {n} B sai do que a CPU enxerga ({e.what})",
                               "escolha outro offset ou use --expand") from None
            if z - a == n - 1 and (wa or {}).get("page") == (wz or {}).get("page"):
                break
            pc = (pc | 0x7FFF) + 1                        # começa no próximo banco
        out.append(pc)
        pc += n
    return out


def rats(size: int) -> bytes:
    """Etiqueta RATS ('STAR' + tamanho-1 + complemento): o Asar não aloca espaço livre dentro dela."""
    n = min(size, 0x10000) - 1
    return b"STAR" + n.to_bytes(2, "little") + (n ^ 0xFFFF).to_bytes(2, "little")


# ── .asm ──────────────────────────────────────────────────────────────────────

def _db(data: bytes, per_line: int = 32) -> list[str]:
    return ["    db " + ",".join(f"${b:02X}" for b in data[i:i + per_line]) for i in range(0, len(data), per_line)]


def site_routine(n: int, hj: dict, trig: int, window: dict | None) -> list[str]:
    """Rotina de um disparo: instruções originais antes do STA; cada canal ligado passa pela conferência (JSL); o
    STA original (o DMA acontece aqui); depois, `GfxOvrDevolve` devolve o DMAP e a fonte que o jogo deixou nos canais
    trocados (há jogo que escreve o DMAP uma vez só e conta com ele). `window`: troca a janela do chip para ler a
    tabela/cópias, só a mantém durante o DMA se algum canal foi trocado, e roda tudo com IRQ desligado."""
    last = hj["sizes"][-1]
    prefix, final = hj["bytes"][:-last], hj["bytes"][-last:]
    slot = STACK_SLOT[hj["store"]]
    win, back = [], []
    if window:
        win = [f"    lda.b #${window['page']:02X}", f"    sta.l ${window['reg']:06X}          ; janela → página da tabela e das cópias"]
        back = [f"    lda.b #${window['restore']:02X}", f"    sta.l ${window['reg']:06X}          ; janela de volta (valor do reset do chip)"]

    def channels(call: str, tag: str, extra: list[str]) -> list[str]:
        return ["    ldy.w #$0000             ; Y = 16 × canal", f".canal{tag}", "    lsr", f"    bcc .prox{tag}", "    pha",
                f"    jsl {call}"] + extra + ["    pla", f".prox{tag}", "    pha", "    rep #$21", "    tya", "    adc.w #$0010",
                                             "    tay", "    sep #$20", "    pla", f"    bne .canal{tag}"]

    save = ["    rep #$30", "    pha", "    phx", "    phy", "    phb", "    sep #$20"]
    restore = ["    plb", "    rep #$30", "    ply", "    plx", "    pla", "    plp"]
    R = [f"GfxOvr{n}:"]
    if prefix:
        R += _db(prefix) + ["    ; ↑ instruções originais antes do disparo (copiadas, sem desvios)"]
    R += [f"GfxOvr{n}Corpo:", "    php"] + (["    sei                      ; sem IRQ com a janela do chip trocada"] if window else [])
    R += save
    if window:
        R += ["    lda.b #$00", "    pha                      ; 0 = nenhum canal trocado"] + win
    R += [f"    lda ${slot + (1 if window else 0):02X},s              ; canais que o {hj['store']} $420B vai disparar"]
    R += channels("GfxOvrConfere            ; C = 1: trocou a fonte deste canal", "",
                  ["    bcc .igual", "    lda.b #$01", "    sta $02,s", ".igual"] if window else [])
    if window:
        R += ["    pla", "    bne .trocou", back[0], f"    sta.l ${window['reg']:06X}          ; nada trocado: janela de volta antes do DMA",
              ".trocou"]
    R += restore + (["    php", "    sei"] if window else [])
    R += _db(final) + [f"    ; ↑ o {hj['store']} $420B original: o DMA acontece aqui"]
    R += [f"GfxOvr{n}Volta:", "    php"] + save + win
    R += [f"    lda ${slot:02X},s              ; os mesmos canais"]
    R += channels("GfxOvrDevolve            ; canal que leu uma cópia: DMAP e fonte do jogo de volta", "d", [])
    R += back + restore + (["    plp"] if window else [])
    return R + [f"    jml ${trig:06X}", ""]


def confere_routine(tab: str, n_entries: int, chip_disarm: list[tuple[int, int]] | None, *, fingerprint: bool = True,
                    fixed: bool = True) -> list[str]:
    """Conferência por tabela (tamanho fixo): canal em Y; X anda na tabela; preserva X/Y/B; C = 1 se trocou. Só
    entra o que os blocos usam (impressão digital, fonte fixa, desarme): ROM quase cheia tem trechos livres curtos."""
    def t(off: int) -> str:
        return f"{tab}+{off}" if not tab.startswith("$") else f"${int(tab[1:], 16) + off:06X}"
    R = ["GfxOvrConfere:           ; JSL — canal em Y (16·n, x16), m8. Preserva X/Y/B; C = 1 se trocou a fonte",
         "    phb", "    phx", "    pea.w $0000", "    plb", "    plb                      ; DBR = $00: registradores de DMA",
         "    lda $4301,y", "    cmp.b #$18               ; destino $2118 (VRAM, palavra)", "    bne .nao",
         "    ldx.w #$0000             ; X = entrada da tabela", ".entrada", "    sep #$20",
         f"    lda.l {t(0)},x       ; banco da fonte", "    cmp $4304,y", "    bne .proxima", "    rep #$20",
         f"    lda.l {t(1)},x       ; endereço da fonte", "    cmp $4302,y", "    bne .proxima",
         f"    lda.l {t(3)},x       ; tamanho", "    cmp $4305,y", "    beq .achou",
         ".proxima", "    rep #$21                 ; m16, C = 0", "    txa", f"    adc.w #${ENTRY:04X}", "    tax",
         f"    cpx.w #${n_entries * ENTRY:04X}", "    bne .entrada", ".nao", "    clc", ".sai", "    sep #$20", "    plx",
         "    plb", "    rtl",
         ".achou", "    sep #$20"]
    if fingerprint:
        R += [f"    lda.l {t(8)},x       ; flags", "    and.b #$0C",
              "    beq .troca               ; fonte na ROM: sem impressão digital", "    phy", "    phb", "    and.b #$08",
              "    beq .b7e", "    lda.b #$7F", "    bra .banco", ".b7e", "    lda.b #$7E", ".banco", "    pha",
              "    plb                      ; DBR = banco do buffer", "    rep #$20",
              f"    lda.l {t(9)},x       ; endereço da impressão", "    tay"]
        for j in range(0, FP_WIDTH, 2):
            R += [f"    lda ${j:04X},y", f"    cmp.l {t(12 + j)},x", "    bne .naobate"]
        R += ["    plb", "    ply", "    bra .troca", ".naobate", "    plb", "    ply", "    brl .proxima"]
    R += [".troca", "    rep #$20", f"    lda.l {t(5)},x       ; fonte → cópia editada", "    sta $4302,y", "    sep #$20",
          f"    lda.l {t(7)},x", "    sta $4304,y"]
    if fixed:
        R += [f"    lda.l {t(8)},x", "    lsr                      ; bit 0: fonte de endereço fixo (chip)", "    bcc .anda",
              "    lda $4300,y", "    and.b #$E7               ; endereço que ANDA: a cópia é crua, em ordem",
              "    sta $4300,y", ".anda"]
    if chip_disarm:
        R += [f"    lda.l {t(8)},x", "    and.b #$02               ; bit 1: desarma o chip neste DMA", "    beq .feito"]
        for addr, val in chip_disarm:
            R += [f"    lda.b #${val:02X}", f"    sta.l ${addr:06X}          ; --chip-disarm"]
        R += [".feito"]
    return R + ["    sec", "    brl .sai", ""]


def devolve_routine(tab: str, n_entries: int) -> list[str]:
    """Depois do DMA: o canal que leu uma cópia (parou em cópia + tamanho, no banco da cópia) recebe de volta o DMAP
    original e a fonte onde o DMA do jogo teria parado (fonte fixa: a própria fonte; senão fonte + tamanho)."""
    def t(off: int) -> str:
        return f"{tab}+{off}" if not tab.startswith("$") else f"${int(tab[1:], 16) + off:06X}"
    return ["GfxOvrDevolve:           ; JSL — canal em Y (16·n, x16), m8. Preserva X/Y/B",
            "    phb", "    phx", "    pea.w $0000", "    plb", "    plb", "    ldx.w #$0000", ".entrada", "    sep #$20",
            f"    lda.l {t(7)},x       ; banco da cópia", "    cmp $4304,y", "    bne .proxima", "    rep #$21",
            f"    lda.l {t(5)},x       ; cópia + tamanho = onde o DMA parou", f"    adc.l {t(3)},x", "    cmp $4302,y",
            "    beq .achou", ".proxima", "    rep #$21", "    txa", f"    adc.w #${ENTRY:04X}", "    tax",
            f"    cpx.w #${n_entries * ENTRY:04X}", "    bne .entrada", ".sai", "    sep #$20", "    plx", "    plb", "    rtl",
            ".achou", "    rep #$20", f"    lda.l {t(1)},x       ; fonte do jogo", "    sta $4302,y", "    sep #$20",
            f"    lda.l {t(0)},x", "    sta $4304,y", f"    lda.l {t(11)},x      ; DMAP do jogo", "    sta $4300,y",
            "    and.b #$08", "    bne .sai                 ; fonte fixa: o DMA não andou", "    rep #$21",
            f"    lda.l {t(1)},x", f"    adc.l {t(3)},x       ; endereço que anda: parou em fonte + tamanho", "    sta $4302,y",
            "    bra .sai", ""]


def generate(rom, blocks: list[Block], *, chip_disarm: list[tuple[int, int]] | None = None, evidence: str = "",
             data_at: int | None = None, data_evidence: str = "") -> dict:
    """O .asm (hooks + conferência + tabela/cópias), os hijacks[] e — com `data_at` (tabela e cópias num blob a
    partir desse offset, ex.: área expandida) — o blob e as regiões data[] para o mod.json."""
    if not blocks:
        raise FabError("nenhum bloco para sobrescrever", "confira se os tiles editados aparecem em uploads do dump")
    if len(blocks) > MAX_BLOCKS:
        raise FabError(f"{len(blocks)} blocos (o Asar protege até {MAX_BLOCKS} por área)", "divida a edição em dois mods")
    sites: dict[int, set] = defaultdict(set)
    for b in blocks:
        for t, ps in b.sites.items():
            sites[t] |= ps
    chip = bool(chip_disarm)
    data_cmd = "freecode" if rom.mapping == "sdd1" else "freedata"   # S-DD1: só os 2 MiB de baixo são LoROM
    blob, blob_base, data, window, tab = None, None, [], None, "GfxOvrTabela"
    if data_at is not None:
        tsize = len(blocks) * ENTRY
        pcs = place([8 + tsize] + [b.size for b in blocks], data_at, rom)
        views = [cpu_view(pc, rom.mapping) for pc in pcs]
        pages = {(w or {}).get("page") for _, w in views}
        if len(pages) > 1:
            raise FabError("a tabela e as cópias caem em páginas diferentes da janela do chip",
                           "edite menos blocos por vez (uma página = 1 MiB)")
        window = views[0][1]
        tab = f"${views[0][0] + 8:06X}"
        new_src = {b.label: views[i + 1][0] for i, b in enumerate(blocks)}
        end = pcs[-1] + blocks[-1].size
        buf = bytearray(end - data_at)
        body = table_bytes(blocks, new_src, chip)
        buf[pcs[0] - data_at:pcs[0] - data_at + 8 + tsize] = rats(end - pcs[0] - 8) + body
        buf_base = bytearray(buf)             # base A/B (build da variante): mesma tabela, mesmo tamanho e mesmo
        for b, pc in zip(blocks, pcs[1:]):    # trabalho do hook — só as cópias são ORIGINAIS (pintura desligada)
            buf[pc - data_at:pc - data_at + b.size] = b.new
            buf_base[pc - data_at:pc - data_at + b.size] = b.data
        blob, blob_base = bytes(buf), bytes(buf_base)
        data = [{"pc": f"0x{data_at:06X}", "length": len(blob), "source": "gfx-override",
                 "evidence": f"tabela + {len(blocks)} cópia(s) editada(s) do gfx override: {data_evidence}"}]
    L = ["; GERADO por `fab gfx override` — NÃO edite à mão (refaça o comando).",
         f"; {evidence}" if evidence else ";",
         f"; override de gráfico sem codec: {len(blocks)} bloco(s) editado(s) servido(s) cru(s); hook em {len(sites)} "
         f"disparo(s) de DMA para a VRAM; tabela e cópias "
         + (f"no blob {OVR_BLOB} a partir de PC 0x{data_at:06X}" if blob else "em espaço livre"),
         ASAR_DIRECTIVE[rom.mapping]]
    R, hijacks, avisos = [], [], []
    protect = ["GfxOvrConfere", "GfxOvrDevolve"] + ([] if blob else ["GfxOvrTabela"] + [b.label for b in blocks])
    for n, (trig, pss) in enumerate(sorted(sites.items()), 1):
        if len(pss) != 1:
            raise FabError(f"o disparo antes de {fmt_addr(trig)} roda com M/X diferentes",
                           "o hijack copia instruções cujo tamanho depende de M/X: escolha o ponto à mão")
        ps = next(iter(pss))
        m8, x8 = bool(ps & 0x20), bool(ps & 0x10)
        flags = ("m8" if m8 else "m16") + "," + ("x8" if x8 else "x16")
        hj = choose_hijack(rom, trig, m8, x8)
        L += ["", f"; disparo {n}: DMA para a VRAM antes de {fmt_addr(trig)} ({flags}); hijack de {hj['length']} B:"]
        L += [f";   {i}" for i in hj["instructions"]]
        L += [f"org ${asar_org(hj['pc'], rom.mapping):06X}", f"    autoclean jml GfxOvr{n}"] + ["    nop"] * (hj["length"] - 4)
        R += ["", "freecode"] + ([f"prot {', '.join(protect)}"] if n == 1 else []) + site_routine(n, hj, trig, window)
        mx = {"m": 8 if m8 else 16, "x": 8 if x8 else 16}
        hijacks.append({"addr": fmt_addr(rom.to_snes(hj["pc"])), **mx, "source": "gfx-override",
                        "evidence": f"fab gfx dump: DMA para a VRAM disparado antes de {fmt_addr(trig)} com {flags}; "
                                    f"hijack = {hj['length']} B de instruções inteiras: "
                                    + " | ".join(i.split('  ', 1)[-1].strip() for i in hj["instructions"]),
                        "verify": [{"label": f"GfxOvr{n}Corpo", **mx}, {"label": f"GfxOvr{n}Volta", **mx},
                                   {"label": "GfxOvrConfere", "m": 8, "x": 16}, {"label": "GfxOvrDevolve", "m": 8, "x": 16}]})
        avisos += [f"disparo {n}: {a}" for a in hj["avisos"]]
    R += ["", "freecode"] + confere_routine(tab, len(blocks), chip_disarm if any(b.kind == "rom" for b in blocks) else None,
                                            fingerprint=any(b.fingerprint for b in blocks),
                                            fixed=any(b.mode & 0x18 for b in blocks))
    R += ["", "freecode"] + devolve_routine(tab, len(blocks))
    if not blob:
        R += ["", data_cmd, "GfxOvrTabela:            ; 24 B por bloco: fonte, tamanho, cópia, flags, impressão digital"]
        R += table_asm(blocks, chip)
        for b in blocks:
            names = ", ".join(h for _, h in b.tiles[:6]) + ("…" if len(b.tiles) > 6 else "")
            R += ["", data_cmd, f"{b.label}:          ; cópia editada de {fmt_addr(b.src)} ({b.size} B; tiles {names})"]
            R += _db(b.new)
    if chip_disarm and not any(b.kind == "rom" for b in blocks):
        avisos.append("--chip-disarm ignorado: nenhum bloco vem de fonte transformada por chip")
    if any(b.kind == "rom" for b in blocks) and not chip_disarm:
        avisos.append("bloco de fonte transformada (chip) sem --chip-disarm: se o chip vigia o endereço do DMA, ele "
                      "transforma também a cópia — passe o registro/valor que o jogo usa para armar o chip")
    if window:
        avisos.append(f"o hook troca a janela {fmt_addr(window['reg'])} para a página {window['page']} e a devolve em "
                      f"{window['restore']} (valor do reset): confirme que o jogo não troca as janelas "
                      f"(`fab probe <jogo> write 00:4804-4807`); o hook roda com IRQ desligado")
    return {"asm": "\n".join(L + R) + "\n", "hijacks": hijacks, "avisos": avisos, "data": data, "blob": blob,
            "blob_base": blob_base, "window": window}


def save(mod_dir: Path, gen: dict, expand_to: int | None = None) -> dict:
    """Grava gfx_override.asm (+ o blob) e liga no mod.json: patches, hijacks[]/data[]/blobs[] com
    source=gfx-override e, com --expand, o expand_to."""
    mod_dir = Path(mod_dir)
    (mod_dir / OVR_ASM).write_text(gen["asm"], encoding="utf-8", newline="\n")
    mj = mod_dir / "mod.json"
    raw = json.loads(mj.read_text(encoding="utf-8"))
    nome_var = ((raw.get("baseline") or {}).get("variant") or {}).get("name", "off")   # base A/B (ver build.py)
    patches = raw.get("patches") or (["patch.asm"] if (mod_dir / "patch.asm").exists() else [])
    if OVR_ASM not in patches:
        patches.append(OVR_ASM)
    raw["patches"] = patches
    raw["hijacks"] = [h for h in raw.get("hijacks", []) if h.get("source") != "gfx-override"] + gen["hijacks"]
    for key, new in (("data", gen["data"]),
                     ("blobs", [{"pc": gen["data"][0]["pc"], "file": OVR_BLOB, "source": "gfx-override",
                                 **({"file_" + nome_var: OVR_BLOB_BASE} if gen.get("blob_base") else [])}]
                      if gen["blob"] else [])):
        raw[key] = [d for d in raw.get(key, []) if d.get("source") != "gfx-override"] + new
        if not raw[key]:
            raw.pop(key)
    if gen["blob"]:
        (mod_dir / OVR_BLOB).write_bytes(gen["blob"])
    else:
        (mod_dir / OVR_BLOB).unlink(missing_ok=True)
    if gen.get("blob_base"):                   # base A/B: mesmo layout, cópias originais (ver `variant_safety`)
        (mod_dir / OVR_BLOB_BASE).write_bytes(gen["blob_base"])
    else:
        (mod_dir / OVR_BLOB_BASE).unlink(missing_ok=True)
    if expand_to:
        from .build import parse_size
        expand_to = max(expand_to, parse_size(raw["expand_to"]) if raw.get("expand_to") else 0)
        raw["expand_to"] = f"{expand_to >> 10}KB" if expand_to & 0xFFFFF else f"{expand_to >> 20}MB"
    write_json(mj, raw)
    return {"asm": rel(mod_dir / OVR_ASM), "blob": rel(mod_dir / OVR_BLOB) if gen["blob"] else None, "patches": patches}


def parse_disarm(items: list[str] | None) -> list[tuple[int, int]]:
    out = []
    for it in items or []:
        a, sep, v = it.partition("=")
        if not sep:
            raise FabError(f"--chip-disarm inválido: {it!r}", "ENDEREÇO=VALOR, ex.: 00:4801=00 (registro e valor da evidência)")
        val = int(v.strip().lstrip("$"), 16)
        out.append((parse_addr(a.strip()), val & 0xFF))
    return out


def expansion_start(rom, need: int) -> tuple[int, int]:
    """Onde começa a área nova e o tamanho final da ROM para caber `need` bytes (S-DD1: páginas de 1 MiB)."""
    size = len(rom.data)
    if rom.mapping == "sdd1":
        start = max(size, 0x400000)
        start = (start + 0xFFFFF) & ~0xFFFFF
        return start, start + ((need + 0xFFFFF) & ~0xFFFFF)
    gran = 0x8000 if rom.mapping in ("lorom", "sa1") else 0x10000
    return size, size + ((need + gran - 1) // gran) * gran


def override(mod_dir: Path, dump: dict, rom, *, chip_disarm: list[tuple[int, int]] | None = None,
             data_at: int | None = None, data_evidence: str = "", expand: bool = False) -> dict:
    """paint.json "vram_tiles" + uploads do dump → gfx_override.asm (+ blob) + hijacks[]/data[]/blobs[]."""
    from .paint import PAINT_JSON, _load_spec
    from .rom import expansion_notes
    spec = _load_spec(Path(mod_dir))
    vt = spec.get("vram_tiles") or []
    if not vt:
        raise FabError("paint.json sem 'vram_tiles' (desenho comprimido editado)",
                       "escolha os tiles: `fab gfx override <mod> --dump <dir> --tiles 12,13 --map 14:9` "
                       "ou `fab paint remap` num sprite comprimido")
    edits = {e["hash"]: bytes.fromhex(e["new"]) for e in vt if int(e.get("bpp", 4)) == dump["bpp"]}
    p = plan(dump, edits, rom)
    if not p["blocks"]:
        raise FabError("nenhum upload do dump leva os tiles editados por uma fonte comprimida/WRAM",
                       "; ".join(s["motivo"] for s in p["skipped"]) or "confira o dump (cenário certo?)")
    ev = f"dump {rel(dump['dir'])}: " + "; ".join(sorted({e['name'] + ': ' + e['evidence'] for e in vt}))[:400]
    expand_to = None
    if expand:
        need = 8 + len(p["blocks"]) * ENTRY + sum(b.size + 0x8000 * (b.size > 0x4000) for b in p["blocks"])
        start, expand_to = expansion_start(rom, need)
        if rom.mapping == "sdd1":
            data_at = start
            data_evidence = data_evidence or f"área nova da ROM expandida (PC 0x{start:06X}+, vazia na base)"
    if data_at is not None and not data_evidence.strip():
        raise FabError("--data-at sem --data-evidence", "prove que a região está livre/sem uso (ex.: área expandida, "
                       "ou gráfico que nenhum cenário carrega) — o build exige evidência para sobrescrever a ROM")
    gen = generate(rom, p["blocks"], chip_disarm=chip_disarm, evidence=ev, data_at=data_at, data_evidence=data_evidence)
    saved = save(Path(mod_dir), gen, expand_to)
    by_hash = {t["hash"]: t["n"] for t in dump["index"]}
    covered = {h for b in p["blocks"] for _, h in b.tiles}
    spec["gfx_override"] = {"dump": rel(dump["dir"]), "chip_disarm": [f"{fmt_addr(a)}={v:02X}" for a, v in chip_disarm or []],
                            "data_at": f"0x{data_at:06X}" if data_at is not None else None, "expand": expand,
                            "updated": now_iso()}
    write_json(Path(mod_dir) / PAINT_JSON, spec)
    res = {**saved, "hijacks": [h["addr"] for h in gen["hijacks"]],
           "blocos": [{"rotulo": b.label, "tipo": b.kind, "fonte": fmt_addr(b.src), "bytes": b.size,
                       "tiles": sorted({by_hash.get(h, h) for _, h in b.tiles}, key=str),
                       "impressao": [f"+{o}: {w.hex()}" for o, w in b.fingerprint],
                       "disparos": [fmt_addr(t) for t in sorted(b.sites)], "frames": b.frames[:6]} for b in p["blocks"]],
           "fora": p["skipped"], "tiles_sem_bloco": sorted({by_hash.get(h, h) for h in edits if h not in covered}, key=str),
           "bytes_novos": sum(b.size for b in p["blocks"]) + len(p["blocks"]) * ENTRY, "avisos": gen["avisos"]}
    if expand_to:
        res["rom_expandida"] = expansion_notes(rom.mapping, len(rom.data), expand_to)
    return res


# ── verificação na VRAM ───────────────────────────────────────────────────────

def rotulos_check(index: list[dict], new_seen: dict, old: dict, base_hashes: set) -> tuple[dict, list]:
    """Rótulos (nº da folha do dump quando existe, senão o hash — sempre texto) do que chegou e do que faltou.
    Já houve crash de `sorted` por misturar int (nº) e str (hash) aqui; o teste de regressão cobre o caso."""
    by_hash = {t["hash"]: str(t["n"]) for t in index}
    chegou = {by_hash.get(h, h): c for h, c in new_seen.items()}
    faltou = sorted(by_hash.get(h, h) for h in old if h not in new_seen and h in base_hashes)
    return chegou, faltou


def check(mod_dir: Path, dump: dict, rom_mod: Path, out_dir: Path) -> dict:
    """Roda os cenários do dump na ROM do mod e confere nos uploads: o desenho editado chegou, o velho sumiu e
    nenhum tile estranho apareceu (o que não é da edição nem existia na base = colateral)."""
    from .emu import Job, run_job
    from .game import state_path
    from .macro import parse_macro
    from .paint import _load_spec
    spec = _load_spec(Path(mod_dir))
    vt = [e for e in spec.get("tiles", []) + spec.get("vram_tiles", []) if int(e.get("bpp", 4)) == dump["bpp"]]
    if not vt:
        raise FabError("paint.json sem tiles editados", "rode `fab gfx override` (ou `fab paint remap`) antes")
    old = {e["hash"]: e["name"] for e in vt}
    new: dict[str, set] = defaultdict(set)             # desenho novo → originais (dois tiles podem virar o mesmo)
    for e in vt:
        new[_h(bytes.fromhex(e["new"]))].add(e["hash"])
    sc = dump["meta"].get("cenarios") or {}
    tb = gfx.TILE_BYTES[dump["bpp"]]
    base_hashes = {_h(bytes(u["data"][o:o + tb])) for u in dump["uploads"] for o in gfx.tile_offsets(u, tb)}
    old_seen, new_seen, strange = [], defaultdict(int), defaultdict(list)
    states = sc.get("states") or [None]
    for n, st in enumerate(states):
        d = Path(out_dir) / f"run-{n + 1}"
        run_job(rom_mod, Job(frames=int(sc.get("frames", 600)), state=state_path(dump["meta"]["game"], st) if st else None,
                             macro=parse_macro(sc["macro"]) if sc.get("macro") else [], capture_every=0,
                             vram_uploads=True), d)
        for u in gfx.read_uploads(d):
            for o in gfx.tile_offsets(u, tb):
                raw = bytes(u["data"][o:o + tb])
                if not any(raw):
                    continue
                h = _h(raw)
                if h in old and h not in new:
                    old_seen.append({"frame": u["frame"], "tile": h, "fonte": fmt_addr(u["src"]),
                                     "vram": f"${(u['start'] + o) & 0xFFFF:04X}"})
                elif h in new:
                    for orig in new[h]:
                        new_seen[orig] += 1
                elif h not in base_hashes:
                    strange[h].append({"frame": u["frame"], "fonte": fmt_addr(u["src"]), "vram": f"${(u['start'] + o) & 0xFFFF:04X}"})
        (d / "vram_uploads.bin").unlink(missing_ok=True)
    chegou, missing = rotulos_check(dump["index"], new_seen, old, base_hashes)
    ok = not old_seen and not strange and not missing
    res = {"ok": ok, "desenho_novo_chegou": chegou,
           "desenho_velho_ainda_aparece": old_seen[:12], "tiles_editados_que_nao_chegaram": missing,
           "colaterais": [{"tile": h, "onde": v[:3]} for h, v in list(strange.items())[:12]],
           "leitura": "OK: todo upload dos tiles editados chegou com o desenho novo e nada mais mudou" if ok else
                      "ERRO: veja desenho_velho_ainda_aparece (disparo sem hook / impressão que não bateu), "
                      "tiles_editados_que_nao_chegaram e colaterais (bloco errado)"}
    write_json(Path(out_dir) / "gfx_check.json", res)
    return res
