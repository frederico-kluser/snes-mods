"""Memória do PPU do SNES em Python puro (numpy): cores BGR555, CGRAM, OAM, tiles 4bpp e o
renderizador da camada de SPRITES (OBJ) com dono por píxel.

Para que serve: dizer, para cada píxel da tela, QUE sprite (entrada do OAM), QUE tile da VRAM,
QUE píxel dentro do tile e QUE índice de cor o desenhou — a base de qualquer recoloração/edição de
sprite sem adivinhação. Regras de hardware que já custaram caro e ficam aqui codificadas:

- **Sprites usam SEMPRE a metade de cima da CGRAM**: paleta `p` do OAM (0-7) → cores `128 + 16·p`
  (paleta `p + 8` da CGRAM). Em Mode 1 os BGs de 4bpp usam 0-127; os sprites, 128-255.
- Cor 0 de cada paleta é transparente.
- Entrada de OAM: X (9 bits com sinal), Y, tile (9 bits: bit 8 = segunda tabela de nomes),
  atributo `vhoopppN`; tabela alta: 2 bits por sprite (bit 8 do X, tamanho grande).
- Tile de um sprite grande: coluna soma no nibble baixo, linha no nibble alto (com volta em 16).
- Endereços de VRAM em PALAVRAS (como o Mesen: `ppu.oamBaseAddress`, `ppu.oamAddressOffset`).

Cores: BGR555 → RGB888 por replicação de bits `(v << 3) | (v >> 2)`, a mesma do MesenCE.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# tamanhos (pequeno, grande) por OBSEL bits 5-7 (= ppu.oamMode no Mesen); 6 e 7 são os não documentados
OBJ_SIZES = {
    0: ((8, 8), (16, 16)), 1: ((8, 8), (32, 32)), 2: ((8, 8), (64, 64)), 3: ((16, 16), (32, 32)),
    4: ((16, 16), (64, 64)), 5: ((32, 32), (64, 64)), 6: ((16, 32), (32, 64)), 7: ((16, 32), (32, 32)),
}

SCREEN_W, SCREEN_H = 256, 224


# ── cores ────────────────────────────────────────────────────────────────────

def bgr555_to_rgb(value: int) -> tuple[int, int, int]:
    r, g, b = value & 0x1F, (value >> 5) & 0x1F, (value >> 10) & 0x1F
    return ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2))


def rgb_to_bgr555(r: int, g: int, b: int) -> int:
    """Inverso exato para cores vindas do emulador (replicação de bits); para RGB qualquer, arredonda."""
    return (round(r * 31 / 255) & 0x1F) | ((round(g * 31 / 255) & 0x1F) << 5) | ((round(b * 31 / 255) & 0x1F) << 10)


def bgr555_array_to_rgb(values: np.ndarray) -> np.ndarray:
    """Array de BGR555 (qualquer forma) → array (..., 3) uint8."""
    v = np.asarray(values, dtype=np.int32)
    ch = np.stack([v & 0x1F, (v >> 5) & 0x1F, (v >> 10) & 0x1F], axis=-1)
    return ((ch << 3) | (ch >> 2)).astype(np.uint8)


def rgb_image_to_bgr555(img: np.ndarray) -> np.ndarray:
    """Imagem HxWx3 do emulador → HxW de BGR555 (exato: o emulador replica os bits)."""
    a = np.asarray(img, dtype=np.int32)
    return (a[..., 0] >> 3) | ((a[..., 1] >> 3) << 5) | ((a[..., 2] >> 3) << 10)


def fmt_color(value: int) -> str:
    return f"${value & 0x7FFF:04X}"


def parse_color(text: str | int) -> int:
    """'$2908', '0x2908', '2908' (BGR555) ou '#rrggbb' (convertido) → BGR555."""
    if isinstance(text, int):
        return text & 0x7FFF
    s = str(text).strip()
    if s.startswith("#") and len(s) == 7:
        return rgb_to_bgr555(int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16))
    s = s.lstrip("$")
    if s.lower().startswith("0x"):
        s = s[2:]
    v = int(s, 16)
    if v > 0x7FFF:
        raise ValueError(f"cor BGR555 tem 15 bits (até $7FFF): {text!r}")
    return v


def cgram_colors(cgram: bytes) -> np.ndarray:
    """512 bytes de CGRAM → 256 valores BGR555 (uint16)."""
    b = np.frombuffer(bytes(cgram[:512]).ljust(512, b"\0"), dtype="<u2")
    return (b & 0x7FFF).astype(np.uint16)


def obj_palette_cgram(p: int) -> int:
    """Paleta de sprite do OAM (0-7) → nº da paleta na CGRAM (8-15). Cor n = 16·(p+8) + n."""
    if not 0 <= p <= 7:
        raise ValueError(f"paleta de sprite vai de 0 a 7 (veio {p})")
    return p + 8


# ── falsa cor: um run com a CGRAM trocada por cores-código diz o ÍNDICE de cada píxel ──

def false_color(i: int) -> int:
    """Cor-código da entrada i (0-255) da CGRAM: r/g ímpares carregam os 8 bits, b = 16 é o selo.
    Píxel misturado (color math, brilho < 15) quebra a paridade/selo e é recusado na decodificação."""
    return (((i & 15) << 1) | 1) | ((((i >> 4) << 1) | 1) << 5) | (16 << 10)


FALSE_COLORS = [false_color(i) for i in range(256)]


def decode_false_color(img: np.ndarray) -> np.ndarray:
    """Imagem capturada com a CGRAM em falsa cor → HxW int16 com o índice da CGRAM (0-255) ou -1."""
    v = rgb_image_to_bgr555(img)
    r, g, b = v & 0x1F, (v >> 5) & 0x1F, (v >> 10) & 0x1F
    ok = ((r & 1) == 1) & ((g & 1) == 1) & (b == 16)
    # o emulador replica bits: confere que o RGB888 é exatamente o de um BGR555 (sem mistura)
    exact = np.all(bgr555_array_to_rgb(v) == np.asarray(img, dtype=np.uint8), axis=-1)
    idx = (r >> 1) | ((g >> 1) << 4)
    return np.where(ok & exact, idx, -1).astype(np.int16)


# ── tiles ─────────────────────────────────────────────────────────────────────

def decode_4bpp(tile: bytes) -> np.ndarray:
    """32 bytes de tile 4bpp (planos 0/1 intercalados nas linhas, depois 2/3) → 8x8 de índices 0-15."""
    t = np.frombuffer(bytes(tile[:32]).ljust(32, b"\0"), dtype=np.uint8)
    bits = np.unpackbits(t.reshape(2, 8, 2), axis=-1)            # (metade, linha, plano-do-par, bit 7..0)
    p0, p1 = bits[0, :, 0:8], bits[0, :, 8:16]
    p2, p3 = bits[1, :, 0:8], bits[1, :, 8:16]
    return (p0 | (p1 << 1) | (p2 << 2) | (p3 << 3)).astype(np.uint8)


def encode_4bpp(pixels: np.ndarray) -> bytes:
    """Inverso de decode_4bpp: 8x8 de índices 0-15 → 32 bytes."""
    p = np.asarray(pixels, dtype=np.uint8).reshape(8, 8)
    out = bytearray(32)
    for r in range(8):
        for plane in range(4):
            byte = 0
            for x in range(8):
                byte |= ((int(p[r, x]) >> plane) & 1) << (7 - x)
            base = 0 if plane < 2 else 16
            out[base + 2 * r + (plane & 1)] = byte
    return bytes(out)


# ── OAM ───────────────────────────────────────────────────────────────────────

@dataclass
class ObjEntry:
    index: int          # 0-127 (ordem do OAM: menor = mais à frente)
    x: int              # -256..255
    y: int              # 0..255
    tile: int           # 0..511 (bit 8 = segunda tabela de nomes)
    palette: int        # 0..7 (paleta de SPRITE; CGRAM = palette + 8)
    priority: int       # 0..3 (prioridade contra os BGs)
    hflip: bool
    vflip: bool
    large: bool
    width: int = 8
    height: int = 8
    attr: int = 0       # byte de atributo cru (vhoopppN)

    @property
    def cgram_palette(self) -> int:
        return self.palette + 8

    def to_dict(self) -> dict:
        return {"oam": self.index, "x": self.x, "y": self.y, "tile": f"${self.tile:03X}", "pal_oam": self.palette,
                "pal_cgram": self.cgram_palette, "prio": self.priority, "hflip": self.hflip, "vflip": self.vflip,
                "size": f"{self.width}x{self.height}", "attr": f"${self.attr:02X}"}


def parse_oam(oam: bytes, obj_mode: int = 0) -> list[ObjEntry]:
    """544 bytes de OAM → 128 entradas (com tamanho resolvido pelo OBSEL)."""
    data = bytes(oam[:0x220]).ljust(0x220, b"\0")
    small, big = OBJ_SIZES.get(obj_mode & 7, OBJ_SIZES[0])
    out = []
    for i in range(128):
        x_lo, y, t, a = data[4 * i:4 * i + 4]
        hi = (data[0x200 + i // 4] >> (2 * (i % 4))) & 3
        x = x_lo | ((hi & 1) << 8)
        if x >= 256:
            x -= 512
        large = bool(hi & 2)
        w, h = big if large else small
        out.append(ObjEntry(i, x, y, t | ((a & 1) << 8), (a >> 1) & 7, (a >> 4) & 3, bool(a & 0x40), bool(a & 0x80),
                            large, w, h, a))
    return out


@dataclass
class ObjLayer:
    """Camada de sprites renderizada: por píxel, o sprite da frente e o que ele desenhou (-1 = vazio)."""
    oam: np.ndarray          # HxW int16: entrada do OAM (-1 = sem sprite)
    color: np.ndarray        # HxW int16: índice 0-15 dentro da paleta (-1 = vazio)
    palette: np.ndarray      # HxW int16: paleta de sprite 0-7 (-1 = vazio)
    tile_addr: np.ndarray    # HxW int32: endereço em BYTES na VRAM do tile 8x8 (-1 = vazio)
    tile_px: np.ndarray      # HxW int16: píxel dentro do tile, y*8+x já com espelhamento (-1 = vazio)
    priority: np.ndarray     # HxW int16 (-1 = vazio)
    entries: list[ObjEntry] = field(default_factory=list)
    dropped_lines: list[int] = field(default_factory=list)   # linhas com mais de 32 sprites/34 fatias

    @property
    def cgram_index(self) -> np.ndarray:
        """HxW int16: índice na CGRAM (128-255) de cada píxel de sprite (-1 = vazio)."""
        return np.where(self.color >= 0, 128 + self.palette * 16 + self.color, -1).astype(np.int16)

    def rgb(self, colors: np.ndarray, background: tuple[int, int, int] = (0, 0, 0)) -> np.ndarray:
        cg = self.cgram_index
        rgb = bgr555_array_to_rgb(np.asarray(colors)[np.clip(cg, 0, 255)])
        rgb[cg < 0] = background
        return rgb


def tile_word_address(base_words: int, offset_words: int, tile: int) -> int:
    """Endereço em PALAVRAS do tile 8x8 `tile` (9 bits) da tabela de sprites."""
    second = (tile >> 8) & 1
    return (base_words + (offset_words if second else 0) + (tile & 0xFF) * 16) & 0x7FFF


def render_obj(oam: bytes, vram: bytes, obj_mode: int, base_words: int, offset_words: int,
               height: int = SCREEN_H, y_offset: int = 0, limits: bool = True, first: int = 0) -> ObjLayer:
    """Renderiza a camada de sprites como o PPU: a partir da entrada `first` do OAM (0, ou a da rotação de
    prioridade), a anterior fica à frente; cor 0 transparente; por linha, só os 32 primeiros sprites
    (range over) e só 34 fatias de 8 px (time over). As fatias são carregadas do ÚLTIMO sprite da linha
    para o primeiro, por isso no time over quem perde fatias são os de MAIOR prioridade.

    `y_offset`: linha da imagem onde aparece o Y=0 do OAM. Nas imagens de 224 linhas do `fab` (overscan
    cortado como no MesenCE) é 0 — medido no SFA2 e no testbed; `fit_y_offset` confere."""
    entries = parse_oam(oam, obj_mode)
    order = [entries[(first + k) & 0x7F] for k in range(128)]
    vram = bytes(vram[:0x10000]).ljust(0x10000, b"\0")
    W = SCREEN_W
    oam_map = np.full((height, W), -1, np.int16)
    col_map = np.full((height, W), -1, np.int16)
    pal_map = np.full((height, W), -1, np.int16)
    tad_map = np.full((height, W), -1, np.int32)
    tpx_map = np.full((height, W), -1, np.int16)
    pri_map = np.full((height, W), -1, np.int16)
    tile_cache: dict[int, np.ndarray] = {}

    def tile_pixels(word_addr: int) -> np.ndarray:
        t = tile_cache.get(word_addr)
        if t is None:
            b = word_addr * 2
            t = decode_4bpp(vram[b:b + 32])
            tile_cache[word_addr] = t
        return t

    # que sprites entram em cada linha: os 32 primeiros na ordem de prioridade (X = -256 conta, mas não desenha)
    per_line: list[list[ObjEntry]] = [[] for _ in range(height)]
    dropped = set()
    for e in order:
        if not (-e.width < e.x < W or e.x == -256):
            continue
        for dy in range(e.height):
            line = ((e.y + dy) & 0xFF) + y_offset
            if 0 <= line < height:
                if limits and len(per_line[line]) >= 32:
                    dropped.add(line)
                    continue
                per_line[line].append(e)

    for line in range(height):
        sprites = per_line[line]
        if not sprites:
            continue
        # time over: 34 fatias, carregadas do último sprite da linha para o primeiro
        budget = 34
        cols_of: dict[int, list[int]] = {}
        for e in reversed(sprites):
            cols = [cx for cx in range(e.width // 8) if -8 < e.x + cx * 8 < W]
            if limits:
                if len(cols) > budget:
                    dropped.add(line)
                    cols = cols[:budget]
                budget -= len(cols)
            cols_of[e.index] = cols
        for e in reversed(sprites):            # de trás para a frente: o de maior prioridade pinta por último
            dy = ((line - y_offset) - e.y) & 0xFF
            if dy >= e.height:
                continue
            sy = e.height - 1 - dy if e.vflip else dy
            trow, py = sy // 8, sy % 8
            for cx in cols_of[e.index]:
                sx0 = e.x + cx * 8
                tcol = (e.width // 8 - 1 - cx) if e.hflip else cx
                t_low = (((e.tile >> 4) + trow) & 0x0F) << 4 | (((e.tile & 0x0F) + tcol) & 0x0F)
                waddr = tile_word_address(base_words, offset_words, (e.tile & 0x100) | t_low)
                pix = tile_pixels(waddr)[py]
                for px in range(8):
                    sx = sx0 + px
                    if not 0 <= sx < W:
                        continue
                    tx = 7 - px if e.hflip else px
                    c = int(pix[tx])
                    if c == 0:
                        continue
                    oam_map[line, sx] = e.index
                    col_map[line, sx] = c
                    pal_map[line, sx] = e.palette
                    tad_map[line, sx] = waddr * 2
                    tpx_map[line, sx] = py * 8 + tx
                    pri_map[line, sx] = e.priority
    return ObjLayer(oam_map, col_map, pal_map, tad_map, tpx_map, pri_map, entries, sorted(dropped))


def visible_mask(layer: ObjLayer, colors: np.ndarray, screen: np.ndarray) -> np.ndarray:
    """Píxeis de sprite que aparecem na tela com a cor esperada (os outros estão cobertos por um BG
    de prioridade maior, misturados por color math ou com brilho reduzido)."""
    expect = layer.rgb(colors)
    return (layer.color >= 0) & np.all(expect == np.asarray(screen)[:layer.color.shape[0]], axis=-1)


def fit_y_offset(oam: bytes, vram: bytes, obj_mode: int, base_words: int, offset_words: int,
                 colors: np.ndarray, screen: np.ndarray, candidates=(-8, -7, -1, 0, 1)) -> tuple[int, float]:
    """Acha o deslocamento vertical entre o Y do OAM e a imagem (depende do corte de overscan):
    o que maximiza os píxeis de sprite com a cor certa. Devolve (deslocamento, fração que bateu)."""
    best = (0, -1.0)
    h = screen.shape[0]
    for off in candidates:
        layer = render_obj(oam, vram, obj_mode, base_words, offset_words, height=h, y_offset=off)
        n = int((layer.color >= 0).sum())
        if n == 0:
            continue
        frac = float(visible_mask(layer, colors, screen).sum()) / n
        if frac > best[1]:
            best = (off, frac)
    return best
