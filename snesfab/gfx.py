"""Export do tileset de QUALQUER jogo pela emulação — sem conhecer o formato de compressão.

Ideia: todo gráfico que aparece na tela passa pela VRAM. O harness grava o que cada DMA para a VRAM deixou lá
(já descomprimido, seja o formato cru, LZ por software, S-DD1, SPC7110…) junto com a origem do DMA. Aqui:
- os tiles são separados pelo alinhamento da VRAM e deduplicados pelo CONTEÚDO (o mesmo desenho em qualquer
  slot conta uma vez);
- cada tile é classificado pela origem: CRU na ROM (o offset na ROM é achado → editável direto),
  ROM TRANSFORMADA (o chip descomprime no DMA: a origem é o fluxo comprimido) ou WRAM (montado/descomprimido
  por software antes do DMA);
- saem folhas PNG numeradas + um índice JSON/Markdown.
A cobertura é a do que os cenários mostram: rode vários states/macros para juntar o tileset inteiro.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import ppu
from .dma import describe_source
from .media import _font
from .rom import fmt_addr
from .util import rel

TILE_BYTES = {2: 16, 4: 32, 8: 64}
# rampa neutra para ver o desenho sem paleta: 0 (transparente) escuro azulado, 1-15 do escuro ao claro
GRAY = [(28, 30, 40)] + [(int(40 + 215 * i / 15),) * 3 for i in range(1, 16)]


def read_uploads(run_dir: Path) -> list[dict]:
    run_dir = Path(run_dir)
    idx, raw = run_dir / "vram_uploads.jsonl", run_dir / "vram_uploads.bin"
    if not idx.exists() or not raw.exists():
        return []
    data = raw.read_bytes()
    out = []
    for line in idx.read_text(encoding="utf-8").splitlines():
        if line.strip():
            u = json.loads(line)
            u["data"] = data[u["offset"]:u["offset"] + u["size"]]
            out.append(u)
    return out


def decode_tile(raw: bytes, bpp: int) -> np.ndarray:
    """Tile 8x8 em 2/4/8 bpp (formato planar do SNES) → índices."""
    if bpp == 4:
        return ppu.decode_4bpp(raw)
    t = np.frombuffer(bytes(raw).ljust(TILE_BYTES[bpp], b"\0"), dtype=np.uint8)
    out = np.zeros((8, 8), np.uint8)
    for pair in range(bpp // 2):
        bits = np.unpackbits(t[16 * pair:16 * pair + 16].reshape(8, 2), axis=-1)
        out |= (bits[:, 0:8] << (2 * pair)) | (bits[:, 8:16] << (2 * pair + 1))
    return out


def encode_tile(px: np.ndarray, bpp: int) -> bytes:
    """Inverso de decode_tile: 8x8 de índices → bytes planares (2/4/8 bpp)."""
    if bpp == 4:
        return ppu.encode_4bpp(px)
    p = np.asarray(px, dtype=np.uint8).reshape(8, 8)
    out = bytearray(TILE_BYTES[bpp])
    for pair in range(bpp // 2):
        for r in range(8):
            for k in (0, 1):
                plane = 2 * pair + k
                out[16 * pair + 2 * r + k] = int(sum(((int(p[r, x]) >> plane) & 1) << (7 - x) for x in range(8)))
    return bytes(out)


def upload_origin(u: dict, rom, cache: dict | None = None) -> str:
    """De onde veio o que este upload deixou na VRAM: cru (bytes iguais na ROM de origem), transformado (o chip
    descomprime no DMA ou a fonte não bate), wram (montado por software antes do DMA), fixo (preenchimento) ou ?."""
    data = u["data"]
    src = describe_source(u["src"], rom)
    if u["mode"] & 0x08:
        # fonte FIXA: ou é preenchimento (limpeza da VRAM: dado uniforme) ou é um chip que descomprime no DMA
        # (S-DD1, SPC7110… exigem canal de endereço fixo): dado variado = o chip transformou o fluxo
        fill = len(data) >= 256 and data == (data[:2] * (len(data) // 2 + 1))[:len(data)]
        return "fixo" if fill else "transformado"
    if src["tipo"] == "ROM":
        pc = src["pc"]
        key = (pc, len(data))
        if cache is None or key not in cache:
            kind = "cru" if rom.data[pc:pc + len(data)] == data else "transformado"
            if cache is None:
                return kind
            cache[key] = kind
        return cache[key]
    return "wram" if src["tipo"] == "WRAM" else "?"


def tile_offsets(u: dict, tb: int) -> range:
    """Offsets (no dado do upload) dos tiles inteiros, pelo alinhamento da VRAM."""
    first = (tb - u["start"] % tb) % tb
    return range(first, len(u["data"]) - tb + 1, tb)


@dataclass
class Tile:
    hash: str
    raw: bytes
    first_frame: int
    count: int = 0
    vram: set = field(default_factory=set)
    origins: Counter = field(default_factory=Counter)      # cru / transformado / wram / ?
    sources: set = field(default_factory=set)              # fonte do DMA (fmt_addr)
    regions: set = field(default_factory=set)              # OBJ / BG
    rom: list = field(default_factory=list)                # offsets onde o desenho está cru na ROM


def obj_regions(snap_meta: dict | None) -> list[tuple[int, int]]:
    """Faixas (bytes) da VRAM das duas tabelas de tiles de sprite, pelo OBSEL do snapshot."""
    if not snap_meta:
        return []
    base = int(snap_meta.get("oamBaseAddress") or 0) * 2
    off = int(snap_meta.get("oamAddressOffset") or 0x1000) * 2
    return [(base & 0xFFFF, (base + 0x2000) & 0x1FFFF), ((base + off) & 0xFFFF, ((base + off) & 0xFFFF) + 0x2000)]


def collect(uploads: list[dict], rom, bpp: int = 4, obj: list[tuple[int, int]] | None = None) -> dict[str, Tile]:
    tb = TILE_BYTES[bpp]
    tiles: dict[str, Tile] = {}
    rom_cache: dict = {}
    for u in uploads:
        data = u["data"]
        src = describe_source(u["src"], rom)
        origin = upload_origin(u, rom, rom_cache)
        start = u["start"]
        for o in tile_offsets(u, tb):
            raw = bytes(data[o:o + tb])
            if not any(raw):
                continue                                       # tile vazio (limpeza da VRAM)
            h = hashlib.sha1(raw).hexdigest()[:12]
            t = tiles.get(h)
            if t is None:
                t = tiles[h] = Tile(h, raw, u["frame"])
            t.count += 1
            addr = (start + o) & 0xFFFF
            t.vram.add(addr)
            t.origins[origin] += 1
            t.sources.add(src["addr"])
            in_obj = any(a <= addr < b for a, b in (obj or []))
            t.regions.add("OBJ" if in_obj else "BG")
    return tiles


def tilemap_regions(meta: dict | None) -> list[tuple[int, int]]:
    """Faixas (bytes) da VRAM ocupadas pelos MAPAS das 4 camadas de BG (32x32 entradas de 2 bytes = 2 KiB,
    ×2 por eixo dobrado) — não são desenho de tile e não entram no tileset."""
    out = []
    for i in range(4):
        base = (meta or {}).get(f"layers[{i}].tilemapAddress")
        if base is None:
            continue
        size = 0x800 * (2 if (meta or {}).get(f"layers[{i}].doubleWidth") else 1) * \
            (2 if (meta or {}).get(f"layers[{i}].doubleHeight") else 1)
        start = (int(base) * 2) & 0xFFFF
        out.append((start, start + size))
    return out


def add_vram_snapshot(tiles: dict[str, Tile], vram: bytes, frame: int, bpp: int = 4,
                      obj: list[tuple[int, int]] | None = None, skip: list[tuple[int, int]] | None = None) -> int:
    """Junta os tiles que estavam na VRAM no fim do cenário (inclusive os carregados ANTES do savestate, que
    nenhum upload mostrou). Origem 'estado' quando o desenho não apareceu em nenhum upload. `skip` = faixas de
    tilemap (mapas das camadas), que não são desenho."""
    tb = TILE_BYTES[bpp]
    added = 0
    for a in range(0, 0x10000, tb):
        if any(lo <= a < hi for lo, hi in (skip or [])):
            continue
        raw = bytes(vram[a:a + tb])
        if not any(raw):
            continue
        h = hashlib.sha1(raw).hexdigest()[:12]
        t = tiles.get(h)
        if t is None:
            t = tiles[h] = Tile(h, raw, frame)
            t.origins["estado"] += 1
            added += 1
        t.vram.add(a)
        t.regions.add("OBJ" if any(lo <= a < hi for lo, hi in (obj or [])) else "BG")
    return added


def find_raw(tiles: dict[str, Tile], rom, limit: int = 4) -> int:
    """Procura cada desenho cru na ROM (para os de origem 'cru' o offset é o da fonte; para os outros, às vezes o
    mesmo desenho também existe cru noutra parte)."""
    found = 0
    data = rom.data
    for t in tiles.values():
        pos = data.find(t.raw)
        while pos != -1 and len(t.rom) < limit:
            t.rom.append(pos)
            pos = data.find(t.raw, pos + 1)
        found += bool(t.rom)
    return found


def sheet(tiles: list[Tile], bpp: int, title: str, start_no: int = 1, cols: int = 32, k: int | None = None) -> Image.Image:
    """Folha numerada: cada tile em blocos de k px, nº a cada 16 tiles; contorno verde = cru na ROM (editável),
    laranja = vem comprimido/transformado, azul = montado na WRAM."""
    if k is None:
        k = 8 if len(tiles) <= 32 else 5 if len(tiles) <= 128 else 3
    cell = 8 * k
    rows = max(1, math.ceil(len(tiles) / cols))
    W, H = 12 + cols * (cell + 3), 60 + rows * (cell + 3)
    out = Image.new("RGB", (W, H), (18, 18, 24))
    d = ImageDraw.Draw(out)
    d.text((10, 8), title, font=_font(15), fill=(235, 235, 235))
    d.text((10, 30), "verde = cru na ROM (editável) · laranja = comprimido/transformado · azul = montado na WRAM · cinza = já estava na VRAM",
           font=_font(12), fill=(170, 170, 180))
    for n, t in enumerate(tiles):
        r, c = divmod(n, cols)
        x, y = 12 + c * (cell + 3), 54 + r * (cell + 3)
        px = decode_tile(t.raw, bpp)
        img = np.zeros((8, 8, 3), np.uint8)
        for i in range(1 << bpp):
            img[px == i] = GRAY[min(15, i * 15 // max(1, (1 << bpp) - 1))] if i else GRAY[0]
        out.paste(Image.fromarray(img).resize((cell, cell), Image.NEAREST), (x, y))
        kind = t.origins.most_common(1)[0][0] if t.origins else "?"
        color = {"cru": (60, 220, 90), "transformado": (255, 150, 40), "wram": (80, 150, 255),
                 "estado": (200, 200, 200)}.get(kind, (120, 120, 120))
        d.rectangle((x - 1, y - 1, x + cell, y + cell), outline=color)
        if (start_no + n) % 16 == 1:
            d.text((x + 1, y + 1), str(start_no + n), font=_font(9), fill=(255, 255, 0))
    return out


def report(tiles: dict[str, Tile], uploads: list[dict], out_dir: Path, bpp: int, title: str, per_sheet: int = 512) -> dict:
    ordered = sorted(tiles.values(), key=lambda t: (0 if "OBJ" in t.regions else 1, t.first_frame, t.hash))
    sheets = []
    for i in range(0, len(ordered), per_sheet):
        p = out_dir / f"tiles-{i // per_sheet + 1:02d}.png"
        sheet(ordered[i:i + per_sheet], bpp, f"{title} · tiles {i + 1}-{min(i + per_sheet, len(ordered))} de {len(ordered)}",
              start_no=i + 1).save(p)
        sheets.append(rel(p))
    kinds = Counter(t.origins.most_common(1)[0][0] for t in ordered if t.origins)
    by_src = defaultdict(lambda: {"uploads": 0, "bytes": 0})
    for u in uploads:
        key = fmt_addr(u["src"])
        by_src[key]["uploads"] += 1
        by_src[key]["bytes"] += u["size"]
    index = [{"n": n, "hash": t.hash, "regiao": sorted(t.regions), "origem": dict(t.origins), "vezes": t.count,
              "primeiro_frame": t.first_frame, "vram": [f"${a:04X}" for a in sorted(t.vram)[:4]],
              "fontes_dma": sorted(t.sources)[:4], "rom_cru": [f"0x{p:06X}" for p in t.rom]}
             for n, t in enumerate(ordered, 1)]
    (out_dir / "tiles.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    summary = {"uploads": len(uploads), "bytes": sum(u["size"] for u in uploads), "tiles_unicos": len(ordered),
               "tiles_sprite": sum(1 for t in ordered if "OBJ" in t.regions),
               "por_origem": dict(kinds), "crus_achados_na_rom": sum(1 for t in ordered if t.rom),
               "folhas": sheets, "indice": rel(out_dir / "tiles.json"),
               "maiores_fontes": sorted(({"fonte": k, **v} for k, v in by_src.items()), key=lambda r: -r["bytes"])[:12]}
    L = [f"# Tileset exportado — {title}", "",
         f"- uploads para a VRAM: {summary['uploads']} ({summary['bytes']} bytes); tiles únicos ({bpp} bpp): "
         f"{summary['tiles_unicos']} (sprites: {summary['tiles_sprite']})",
         f"- origem dos tiles: {summary['por_origem']} · desenho cru achado na ROM: {summary['crus_achados_na_rom']}",
         "- cru = dá para editar o desenho direto na ROM (`fab paint remap`); transformado = o chip descomprime no DMA",
         "  (a fonte do DMA é o fluxo comprimido); wram = o jogo monta/descomprime por software antes do DMA.",
         "- cobertura = o que os cenários mostraram: junte mais states/macros para completar.", "",
         "| fonte do DMA | uploads | bytes |", "|---|---|---|"]
    L += [f"| `{r['fonte']}` | {r['uploads']} | {r['bytes']} |" for r in summary["maiores_fontes"]]
    L += ["", "Folhas: " + ", ".join(f"`{s}`" for s in sheets), f"Índice por tile: `{summary['indice']}`", ""]
    (out_dir / "tileset.md").write_text("\n".join(L), encoding="utf-8", newline="\n")
    summary["report"] = rel(out_dir / "tileset.md")
    return summary
