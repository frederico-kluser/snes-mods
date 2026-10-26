"""Sprites para pintura: captura, objetos, cores, origem das paletas e imagens rotuladas.

Pensado para quem decide SÓ olhando imagens e lendo texto (inclusive LLMs mais fracas):
cada etapa produz uma imagem com números grandes + uma tabela em texto, e a decisão pedida é
pequena ("que número é o Ken?", "que painéis mostram a roupa?").

Captura (`capture`): duas runs determinísticas do mesmo state/macro —
  1. real: frames pedidos + snapshot do PPU (OAM/CGRAM/VRAM, com o display ligado) + WRAM;
  2. falsa cor: a CGRAM vira cores-código durante esses frames → o ÍNDICE da CGRAM de cada píxel.
O render da camada de sprites (`ppu.render_obj`) diz o DONO de cada píxel (entrada do OAM, tile da VRAM,
píxel dentro do tile); a falsa cor diz o que ficou VISÍVEL. Os dois têm de concordar (é conferido).
"""

from __future__ import annotations

import hashlib
import math
import shutil
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import ppu
from .emu import Job, PpuSnapshot, read_ppu, read_wram, run_job
from .media import _font, load_run_frames
from .rom import fmt_addr, load_rom, pc_to_snes
from .util import FabError, now_iso, read_json, rel, sha1_bytes, write_json

# 15 cores categóricas bem distintas (Trubetskoy) para o mapa de índices; o índice 0 é transparente
INDEX_COLORS = [
    (60, 60, 66), (230, 25, 75), (60, 180, 75), (255, 225, 25), (67, 99, 216), (245, 130, 49), (145, 30, 180),
    (66, 212, 244), (240, 50, 230), (191, 239, 69), (250, 190, 212), (70, 153, 144), (220, 190, 255),
    (154, 99, 36), (255, 250, 200), (128, 0, 0),
]
OBJECT_COLORS = [(255, 64, 64), (64, 200, 255), (255, 210, 0), (120, 255, 120), (255, 120, 255), (255, 160, 60),
                 (170, 140, 255), (0, 230, 180), (255, 255, 255), (200, 200, 120)]
HIGHLIGHT = (255, 0, 255)
BG_DARK = (22, 22, 28)
TEXT = (235, 235, 235)
TEXT_DIM = (160, 160, 170)


# ── captura ───────────────────────────────────────────────────────────────────

@dataclass
class FrameData:
    frame: int
    real: np.ndarray            # 224x256x3 (overscan cortado)
    index: np.ndarray           # 224x256 int16: índice da CGRAM visível (-1 = mistura/forced blank)
    snap: PpuSnapshot | None
    wram: bytes | None = None
    _layer: ppu.ObjLayer | None = None

    @property
    def colors(self) -> np.ndarray:
        return ppu.cgram_colors(self.snap.cgram) if self.snap else np.zeros(256, np.uint16)

    def layer(self) -> ppu.ObjLayer:
        if self._layer is None:
            if self.snap is None:
                raise FabError(f"frame {self.frame} sem snapshot do PPU", "recapture com `fab sprite snap`")
            m = self.snap.meta
            first = ((int(m.get("internalOamAddress") or 0) >> 2) & 0x7F) if m.get("enableOamPriority") else 0
            self._layer = ppu.render_obj(self.snap.oam, self.snap.vram, self.snap.obj_mode, self.snap.obj_base,
                                         self.snap.obj_offset, height=self.real.shape[0], y_offset=0, first=first)
        return self._layer

    def visible_obj(self) -> np.ndarray:
        """Píxeis de sprite visíveis: o render diz que há sprite E a falsa cor confirma o mesmo índice."""
        lay = self.layer()
        return (lay.color >= 0) & (self.index == lay.cgram_index)

    def agreement(self) -> dict:
        """Concordância render × falsa cor (deve ser ~1.0; menos = snapshot fora de hora ou efeito não emulado)."""
        lay = self.layer()
        fc_obj = self.index >= 128
        vis = self.visible_obj()
        n_fc = int(fc_obj.sum())
        return {"obj_px_falsa_cor": n_fc, "obj_px_render": int((lay.color >= 0).sum()), "concordam": int(vis.sum()),
                "fracao": round(float(vis.sum()) / n_fc, 4) if n_fc else 1.0,
                "linhas_com_sprites_perdidos": lay.dropped_lines}


@dataclass
class Capture:
    dir: Path
    meta: dict
    frames: dict[int, FrameData] = field(default_factory=dict)

    def frame(self, f: int | None = None) -> FrameData:
        if f is None:
            f = sorted(self.frames)[0]
        if f not in self.frames:
            raise FabError(f"frame {f} não está na captura {rel(self.dir)}", f"frames capturados: {sorted(self.frames)}")
        return self.frames[f]


def capture(game: str, out_dir: Path, *, rom: Path, state: Path | None, macro: list, frames: list[int],
            warmup: int = 0, label: str = "", rom_image=None, keep_runs: bool = False, with_wram: bool = True,
            probes: list | None = None) -> Capture:
    """Duas runs (real + falsa cor) do mesmo cenário; guarda frames, mapas de índice e snapshots em out_dir."""
    from .macro import total_frames
    frames = sorted({int(f) for f in frames})
    if not frames:
        raise FabError("nenhum frame pedido", "ex.: --frames 60 ou --frames 30,60,90")
    if frames[0] < warmup:
        raise FabError(f"frame {frames[0]} é anterior ao warmup ({warmup})", "peça frames >= warmup")
    n = max(frames[-1] + 1, total_frames(macro))
    out_dir.mkdir(parents=True, exist_ok=True)
    img = rom_image or load_rom(rom)
    real_dir, fc_dir = out_dir / "run-real", out_dir / "run-falsacor"
    run_job(rom, Job(frames=n, state=state, macro=macro, capture_every=0, capture_frames=frames, warmup=warmup,
                     ppu_frames=frames, wram_frames=frames if with_wram else [], probes=list(probes or [])),
            real_dir, rom_image=img)
    run_job(rom, Job(frames=n, state=state, macro=macro, capture_every=0, capture_frames=frames, warmup=warmup,
                     false_color=frames), fc_dir, rom_image=img)
    real = load_run_frames(real_dir).by_frame()
    fc = load_run_frames(fc_dir).by_frame()
    (out_dir / "frames").mkdir(exist_ok=True)
    (out_dir / "index").mkdir(exist_ok=True)
    for f in frames:
        Image.fromarray(real[f]).save(out_dir / "frames" / f"f{f:05d}.png")
        np.save(out_dir / "index" / f"f{f:05d}.npy", ppu.decode_false_color(fc[f]))
    for name in ("ppu.bin", "ppu_index.jsonl", "wram.bin", "wram_index.csv"):
        if (real_dir / name).exists():
            shutil.move(str(real_dir / name), str(out_dir / name))
    if not keep_runs:
        for d in (real_dir, fc_dir):
            for big in ("frames.rgb", "frames_index.csv"):
                (d / big).unlink(missing_ok=True)
    meta = {"game": game, "rom": rel(rom), "rom_sha1": sha1_bytes(img.data), "mapping": img.mapping,
            "state": rel(state) if state else None, "frames": frames, "warmup": warmup, "label": label,
            "created": now_iso(), "macro": [[int(a), int(b)] for a, b in macro]}
    write_json(out_dir / "capture.json", meta)
    return load_capture(out_dir)


def load_capture(cap_dir: Path) -> Capture:
    cap_dir = Path(cap_dir)
    if not (cap_dir / "capture.json").exists():
        raise FabError(f"{cap_dir} não é uma captura de sprites (falta capture.json)", "gere com `fab sprite snap`")
    meta = read_json(cap_dir / "capture.json")
    snaps = read_ppu(cap_dir)
    wram = read_wram(cap_dir)
    cap = Capture(cap_dir, meta)
    for f in meta["frames"]:
        png, npy = cap_dir / "frames" / f"f{f:05d}.png", cap_dir / "index" / f"f{f:05d}.npy"
        if not png.exists() or not npy.exists():
            continue
        cap.frames[f] = FrameData(f, np.asarray(Image.open(png).convert("RGB")), np.load(npy), snaps.get(f), wram.get(f))
    if not cap.frames:
        raise FabError(f"captura vazia em {cap_dir}")
    return cap


# ── componentes conexos (sem scipy) ─────────────────────────────────────────────

def components(mask: np.ndarray, connectivity: int = 8, min_px: int = 1) -> list[np.ndarray]:
    """Componentes conexos de uma máscara booleana → lista de arrays (N, 2) de (y, x), maiores primeiro."""
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    steps = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)] if connectivity == 8 else \
        [(-1, 0), (0, -1), (0, 1), (1, 0)]
    out = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        seen[y0, x0] = True
        q = deque([(y0, x0)])
        pts = []
        while q:
            y, x = q.popleft()
            pts.append((y, x))
            for dy, dx in steps:
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    q.append((ny, nx))
        if len(pts) >= min_px:
            out.append(np.array(pts, dtype=np.int32))
    out.sort(key=len, reverse=True)
    return out


def dilate(mask: np.ndarray, r: int = 1) -> np.ndarray:
    out = mask.copy()
    for _ in range(r):
        m = out.copy()
        m[1:, :] |= out[:-1, :]
        m[:-1, :] |= out[1:, :]
        m[:, 1:] |= out[:, :-1]
        m[:, :-1] |= out[:, 1:]
        out = m
    return out


# ── objetos (grupos de sprites com a mesma paleta, juntos na tela) ────────────────

@dataclass
class SpriteObject:
    number: int
    palette: int                    # paleta de SPRITE (OAM) 0-7
    mask: np.ndarray                # HxW bool: píxeis visíveis deste objeto
    oam: list[int]                  # entradas do OAM que desenham píxeis visíveis
    bbox: tuple[int, int, int, int]  # x0, y0, x1, y1 (inclusivo)
    counts: dict[int, int]          # índice de cor 1-15 → píxeis visíveis

    @property
    def cgram_palette(self) -> int:
        return self.palette + 8

    @property
    def pixels(self) -> int:
        return int(self.mask.sum())

    def describe(self, colors: np.ndarray) -> dict:
        base = 16 * self.cgram_palette
        return {
            "objeto": self.number, "paleta_oam": self.palette, "paleta_cgram": self.cgram_palette,
            "cores_cgram": f"{base}-{base + 15}", "bytes_cgram": f"${2 * base:03X}-${2 * base + 31:03X}",
            "pixeis": self.pixels, "sprites": len(self.oam), "caixa": list(self.bbox),
            "indices": {str(i): {"cor": ppu.fmt_color(int(colors[base + i])), "pixeis": n}
                        for i, n in sorted(self.counts.items())},
        }


@dataclass
class BgArea:
    """Área de BG (retrato, HUD, cenário…): píxeis que NÃO são sprite, com a mesma linha de paleta da CGRAM e
    juntos na tela. Vem só do mapa de índices da falsa cor — vale para qualquer modo de vídeo e qualquer jogo."""
    number: int
    cgram_palette: int              # linha da CGRAM (índice // 16)
    mask: np.ndarray
    bbox: tuple[int, int, int, int]
    counts: dict[int, int]          # índice dentro da linha (0-15) → píxeis

    @property
    def pixels(self) -> int:
        return int(self.mask.sum())

    def describe(self, colors: np.ndarray) -> dict:
        base = 16 * self.cgram_palette
        return {
            "area_bg": self.number, "paleta_cgram": self.cgram_palette, "cores_cgram": f"{base}-{base + 15}",
            "bytes_cgram": f"${2 * base:03X}-${2 * base + 31:03X}", "pixeis": self.pixels, "caixa": list(self.bbox),
            "indices": {str(i): {"cor": ppu.fmt_color(int(colors[base + i])), "pixeis": n}
                        for i, n in sorted(self.counts.items())},
        }


def find_bg_areas(fd: FrameData, gap: int = 1, min_px: int = 48) -> list[BgArea]:
    """Áreas de BG por linha de paleta da CGRAM (sem os sprites visíveis nem o fundo/backdrop, cor 0)."""
    idx = fd.index.astype(np.int32)
    obj = fd.visible_obj() if fd.snap is not None else np.zeros(idx.shape, bool)
    bg = (idx > 0) & ~obj
    areas = []
    for P in range(16):
        m = bg & (idx // 16 == P)
        if m.sum() < min_px:
            continue
        for comp in components(dilate(m, gap), 8):
            cm = np.zeros_like(m)
            cm[comp[:, 0], comp[:, 1]] = True
            cm &= m
            n = int(cm.sum())
            if n < min_px:
                continue
            ys, xs = np.nonzero(cm)
            sub = idx[cm] % 16
            counts = {int(i): int((sub == i).sum()) for i in np.unique(sub)}
            areas.append(BgArea(0, P, cm, (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())), counts))
    areas.sort(key=lambda a: a.pixels, reverse=True)
    for i, a in enumerate(areas, 1):
        a.number = i
    return areas


def palette_target(fd: FrameData, cgram_palette: int, box: tuple[int, int, int, int] | None = None) -> BgArea:
    """Todos os píxeis visíveis de uma linha de paleta da CGRAM (opcionalmente dentro de uma caixa x,y,w,h)."""
    idx = fd.index.astype(np.int32)
    m = (idx >= 0) & (idx // 16 == cgram_palette) & (idx % 16 != 0)
    if box:
        x, y, w, h = box
        keep = np.zeros_like(m)
        keep[max(0, y):y + h, max(0, x):x + w] = True
        m &= keep
    if not m.any():
        raise FabError(f"nenhum píxel da paleta CGRAM {cgram_palette} visível no frame {fd.frame}"
                       + (f" dentro de {box}" if box else ""), "veja palettes.png / overview.png do `fab sprite snap`")
    ys, xs = np.nonzero(m)
    sub = idx[m] % 16
    return BgArea(0, cgram_palette, m, (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())),
                  {int(i): int((sub == i).sum()) for i in np.unique(sub)})


def color_index_map(fd: FrameData, target) -> np.ndarray:
    """Índice 0-15 dentro da paleta do alvo, por píxel (−1 fora do alvo) — igual para sprite e BG."""
    col = fd.index.astype(np.int32) - 16 * target.cgram_palette
    return np.where(target.mask & (col >= 0) & (col < 16), col, -1)


def find_objects(fd: FrameData, gap: int = 2, min_px: int = 12) -> list[SpriteObject]:
    """Agrupa os píxeis de sprite visíveis por paleta e proximidade (até `gap` px de distância)."""
    lay = fd.layer()
    vis = fd.visible_obj()
    objs = []
    for p in range(8):
        m = vis & (lay.palette == p)
        if not m.any():
            continue
        for comp in components(dilate(m, gap), 8):
            cm = np.zeros_like(m)
            cm[comp[:, 0], comp[:, 1]] = True
            cm &= m
            n = int(cm.sum())
            if n < min_px:
                continue
            ys, xs = np.nonzero(cm)
            idxs = lay.color[cm]
            counts = {int(i): int((idxs == i).sum()) for i in np.unique(idxs)}
            objs.append(SpriteObject(0, p, cm, sorted({int(o) for o in np.unique(lay.oam[cm])}),
                                     (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())), counts))
    objs.sort(key=lambda o: o.pixels, reverse=True)
    for i, o in enumerate(objs, 1):
        o.number = i
    return objs


# ── de onde vem uma paleta (ROM e WRAM) ──────────────────────────────────────────

def _search_words(data: bytes, seq: list[int], limit: int = 12) -> list[int]:
    """Offsets (em bytes, qualquer alinhamento) onde a sequência de palavras BGR555 aparece (bit 15 ignorado)."""
    if not seq or len(data) < 2 * len(seq):
        return []
    hits = []
    raw = np.frombuffer(data, dtype=np.uint8)
    for align in (0, 1):
        n = (len(raw) - align) // 2
        words = (raw[align:align + 2 * n:2].astype(np.uint16) | (raw[align + 1:align + 2 * n:2].astype(np.uint16) << 8)) & 0x7FFF
        cand = np.nonzero(words[:n - len(seq) + 1] == seq[0])[0]
        for c in cand:
            if all(int(words[c + k]) == seq[k] for k in range(1, len(seq))):
                hits.append(align + 2 * int(c))
                if len(hits) >= limit:
                    break
    return sorted(hits)[:limit]


def find_palette_sources(colors16: list[int], rom_data: bytes, mapping: str, wram: bytes | None = None,
                         min_run: int = 4) -> dict:
    """Procura uma paleta de 16 cores na ROM (e na WRAM do mesmo frame). Tenta a paleta inteira, depois as
    cores 1-15 (a cor 0 é transparente e o jogo às vezes a troca), depois o maior trecho de >= min_run cores."""
    out = {"rom": [], "wram": [], "como": None}

    def rom_entry(pc: int, first_index: int, n: int) -> dict:
        e = {"pc": f"0x{pc:06X}", "indice_inicial": first_index, "cores": n}
        try:
            e["snes"] = fmt_addr(pc_to_snes(pc, mapping))
            if mapping == "sdd1" and pc < 0x400000:      # MMC padrão: $C0-$FF = os 4 MiB em janelas de 1 MiB
                e["janela_hirom"] = fmt_addr(((0xC0 + (pc >> 16)) << 16) | (pc & 0xFFFF))
        except FabError:
            e["snes"] = None
        return e

    tries = [(0, colors16, "paleta inteira (16 cores)"), (1, colors16[1:], "cores 1-15 (a cor 0 difere)")]
    for first, seq, how in tries:
        hits = _search_words(rom_data, seq)
        if hits:
            out["rom"] = [rom_entry(h, first, len(seq)) for h in hits]
            out["como"] = how
            break
    if not out["rom"]:
        best = None
        for length in range(14, min_run - 1, -1):
            for start in range(1, 16 - length + 1):
                seq = colors16[start:start + length]
                if len(set(seq)) < 2:
                    continue
                hits = _search_words(rom_data, seq, limit=6)
                if hits:
                    best = (start, length, hits)
                    break
            if best:
                break
        if best:
            start, length, hits = best
            out["rom"] = [rom_entry(h, start, length) for h in hits]
            out["como"] = f"trecho parcial: cores {start}-{start + length - 1} (o resto difere na ROM ou é calculado)"
    if wram:
        for first, seq in ((0, colors16), (1, colors16[1:])):
            hits = _search_words(wram, seq, limit=8)
            if hits:
                out["wram"] = [{"addr": f"7E:{h - 2 * first:04X}" if h - 2 * first < 0x10000 else f"7F:{h - 2 * first - 0x10000:04X}",
                                "como": "16 cores" if first == 0 else "cores 1-15"} for h in hits]
                break
    return out


# ── desenho ───────────────────────────────────────────────────────────────────────

def _text(draw: ImageDraw.ImageDraw, xy, text: str, size: int = 14, fill=TEXT, bg=None, pad: int = 3):
    font = _font(size)
    if bg is not None:
        box = draw.textbbox(xy, text, font=font)
        draw.rectangle((box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad), fill=bg)
    draw.text(xy, text, font=font, fill=fill)


def _scale(img: np.ndarray, k: int) -> Image.Image:
    return Image.fromarray(img).resize((img.shape[1] * k, img.shape[0] * k), Image.NEAREST)


def swatch_rgb(value: int) -> tuple[int, int, int]:
    return ppu.bgr555_to_rgb(int(value))


def tag(t) -> str:
    """Como o alvo aparece nas imagens e na CLI: sprite = "2" (--object 2), área de BG = "B1" (--bg 1)."""
    return f"B{t.number}" if isinstance(t, BgArea) else str(t.number)


def describe_target(t) -> str:
    if isinstance(t, SpriteObject):
        return f"sprite {t.number}: paleta OAM {t.palette} = CGRAM {t.cgram_palette}  ·  {t.pixels} px  ·  {len(t.oam)} sprites"
    return f"BG B{t.number}: paleta CGRAM {t.cgram_palette}  ·  {t.pixels} px"


def overview_image(fd: FrameData, items: list, title: str, scale: int = 3,
                   note: tuple[str, ...] = ("Sprites usam as paletas 8-15 da CGRAM:",
                                            "paleta p do OAM = paleta p+8 da CGRAM.")) -> Image.Image:
    """Frame ampliado com cada alvo (objeto de sprite ou área de BG) numerado + legenda."""
    frame_img = _scale(fd.real, scale)
    W = frame_img.width + 450
    H = max(frame_img.height, 120 + 26 * len(items[:24]))
    out = Image.new("RGB", (W, H), BG_DARK)
    out.paste(frame_img, (0, 0))
    d = ImageDraw.Draw(out)
    for o in items[:24]:
        c = OBJECT_COLORS[(o.number - 1) % len(OBJECT_COLORS)]
        x0, y0, x1, y1 = o.bbox
        d.rectangle((x0 * scale - 2, y0 * scale - 2, (x1 + 1) * scale + 1, (y1 + 1) * scale + 1), outline=c, width=2)
        _text(d, (x0 * scale + 2, max(0, y0 * scale - 22)), tag(o), size=18, fill=(0, 0, 0), bg=c)
    x = frame_img.width + 14
    _text(d, (x, 10), title, size=15)
    for n, line in enumerate(note):
        _text(d, (x, 34 + 18 * n), line, size=13, fill=TEXT_DIM)
    y = 44 + 18 * len(note)
    for o in items[:24]:
        c = OBJECT_COLORS[(o.number - 1) % len(OBJECT_COLORS)]
        d.rectangle((x, y + 2, x + 16, y + 18), fill=c)
        _text(d, (x + 24, y + 1), describe_target(o), size=13)
        y += 26
    if len(items) > 24:
        _text(d, (x, y), f"… e mais {len(items) - 24} pequenos (ver report.md)", size=13, fill=TEXT_DIM)
    return out


def _crop_box(o, shape, margin: int = 4) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = o.bbox
    return max(0, x0 - margin), max(0, y0 - margin), min(shape[1], x1 + margin + 1), min(shape[0], y1 + margin + 1)


def _fit_scale(h: int, w: int, target: int = 420, max_k: int = 10) -> int:
    return max(1, min(max_k, target // max(h, w // 2, 1)))


def object_sheet(fd: FrameData, o, title: str) -> Image.Image:
    """Alvo (sprite ou BG): recorte real | mapa de índices (cores categóricas) | legenda com cor real, hex e contagem."""
    colors = fd.colors
    cx0, cy0, cx1, cy1 = _crop_box(o, fd.real.shape)
    real = fd.real[cy0:cy1, cx0:cx1]
    k = _fit_scale(real.shape[0], real.shape[1])
    gray = (real.mean(axis=2, keepdims=True) * 0.35).astype(np.uint8).repeat(3, axis=2)
    idxmap = gray.copy()
    col = color_index_map(fd, o)[cy0:cy1, cx0:cx1]
    for i in range(1, 16):
        idxmap[col == i] = INDEX_COLORS[i]
    a, b = _scale(real, k), _scale(idxmap, k)
    used = sorted(o.counts)
    leg_w = 360
    W = a.width + b.width + leg_w + 50
    H = max(a.height + 30, 70 + 24 * len(used)) + 40
    out = Image.new("RGB", (W, H), BG_DARK)
    d = ImageDraw.Draw(out)
    _text(d, (10, 8), title, size=15)
    out.paste(a, (10, 34))
    out.paste(b, (20 + a.width, 34))
    _text(d, (10, 34 + a.height + 6), "real", size=12, fill=TEXT_DIM)
    _text(d, (20 + a.width, 34 + b.height + 6), "mapa de índices", size=12, fill=TEXT_DIM)
    x = 40 + a.width + b.width
    base = 16 * o.cgram_palette
    _text(d, (x, 34), "índice · cor real · valor · píxeis", size=13, fill=TEXT_DIM)
    y = 58
    total = max(o.pixels, 1)
    for i in used:
        v = int(colors[base + i])
        d.rectangle((x, y, x + 18, y + 18), fill=INDEX_COLORS[i], outline=(0, 0, 0))
        d.rectangle((x + 24, y, x + 54, y + 18), fill=swatch_rgb(v), outline=(90, 90, 90))
        _text(d, (x + 62, y + 1), f"{i:>2}  {ppu.fmt_color(v)}  {o.counts[i]:>5} px ({100 * o.counts[i] / total:.0f}%)", size=13)
        y += 24
    return out


def index_panels(fd: FrameData, o, title: str, cols: int = 4) -> Image.Image:
    """Um painel por índice usado: o alvo em cinza e os píxeis daquele índice em magenta.
    É a imagem para responder "que índices são a roupa/o cabelo/a luva?"."""
    colors = fd.colors
    cx0, cy0, cx1, cy1 = _crop_box(o, fd.real.shape, 2)
    real = fd.real[cy0:cy1, cx0:cx1]
    k = max(2, min(6, 300 // max(real.shape[0], 1)))
    m = o.mask[cy0:cy1, cx0:cx1]
    col = color_index_map(fd, o)[cy0:cy1, cx0:cx1]
    lum = real.mean(axis=2, keepdims=True)
    gray = np.where(m[..., None], lum * 0.45 + 70, lum * 0.18).astype(np.uint8).repeat(3, axis=2)
    used = sorted(o.counts)
    pw, ph = max(real.shape[1] * k, 150), real.shape[0] * k
    if pw > 700:                                   # área de BG larga: reduz
        k = max(1, 700 // max(real.shape[1], 1))
        pw, ph = max(real.shape[1] * k, 150), real.shape[0] * k
    cols = max(1, min(cols if cols else 5, 1500 // (pw + 12)))
    head = 44
    rows = math.ceil(len(used) / cols)
    W = max(cols * (pw + 12) + 12, 600)
    H = 40 + rows * (ph + head + 12)
    out = Image.new("RGB", (W, H), BG_DARK)
    d = ImageDraw.Draw(out)
    _text(d, (12, 8), title, size=15)
    base = 16 * o.cgram_palette
    for n, i in enumerate(used):
        r, c = divmod(n, cols)
        x, y = 12 + c * (pw + 12), 40 + r * (ph + head + 12)
        panel = gray.copy()
        panel[col == i] = HIGHLIGHT
        out.paste(_scale(panel, k), (x, y + head))
        v = int(colors[base + i])
        d.rectangle((x, y + 2, x + 34, y + 36), fill=swatch_rgb(v), outline=(150, 150, 150))
        _text(d, (x + 42, y), f"índice {i}", size=17)
        _text(d, (x + 42, y + 22), f"{ppu.fmt_color(v)} · {o.counts[i]} px", size=12, fill=TEXT_DIM)
    return out


def palettes_image(colors: np.ndarray, used: dict[int, list[str]], title: str) -> Image.Image:
    """As 16 paletas da CGRAM (linhas) × 16 cores; cada linha diz quem a usa no frame."""
    sw, sh, left = 46, 30, 230
    out = Image.new("RGB", (left + 16 * sw + 20, 50 + 16 * (sh + 4)), BG_DARK)
    d = ImageDraw.Draw(out)
    _text(d, (10, 8), title, size=15)
    for i in range(16):
        _text(d, (left + i * sw + 14, 32), f"{i}", size=11, fill=TEXT_DIM)
    for p in range(16):
        y = 50 + p * (sh + 4)
        lab = f"CGRAM {p:>2}" + (f" = OAM {p - 8}" if p >= 8 else "")
        if used.get(p):
            lab += "  ← " + ",".join(used[p][:4])
        _text(d, (8, y + 7), lab, size=12, fill=TEXT if used.get(p) else TEXT_DIM)
        for i in range(16):
            v = int(colors[16 * p + i])
            x = left + i * sw
            d.rectangle((x, y, x + sw - 3, y + sh), fill=swatch_rgb(v), outline=(70, 70, 70))
            lum = sum(swatch_rgb(v)) / 3
            _text(d, (x + 3, y + 9), f"{v:04X}", size=10, fill=(0, 0, 0) if lum > 110 else (230, 230, 230))
    return out


# ── relatório do snapshot ────────────────────────────────────────────────────────

def snap_report(cap: Capture, frame: int | None = None, out_dir: Path | None = None, rom_data: bytes | None = None,
                max_objects: int = 6, max_bg: int = 4) -> dict:
    """Para um frame da captura: overview.png (sprites numerados), bg.png (áreas de BG B1, B2…), objN/bgN.png
    (mapa de índices + legenda), objN/bgN-indices.png (um painel por índice), palettes.png, report.md e snap.json
    (cores por alvo, origem de cada paleta na ROM/WRAM, concordância render × falsa cor)."""
    fd = cap.frame(frame)
    out_dir = Path(out_dir or cap.dir / f"f{fd.frame:05d}")
    out_dir.mkdir(parents=True, exist_ok=True)
    objs = find_objects(fd) if fd.snap is not None else []
    areas = find_bg_areas(fd)
    colors = fd.colors
    game = cap.meta.get("game", "?")
    title = f"{game} · {Path(cap.meta.get('state') or 'power-on').stem} · frame {fd.frame}"
    files = {}
    overview_image(fd, objs, title + " · SPRITES").save(out_dir / "overview.png")
    files["overview"] = rel(out_dir / "overview.png")
    overview_image(fd, areas, title + " · BG", note=("Áreas de BG (fundo, retratos, HUD) por linha de",
                                                      "paleta da CGRAM. Use --bg N nos comandos.")).save(out_dir / "bg.png")
    files["bg"] = rel(out_dir / "bg.png")
    used: dict[int, list[str]] = {}
    for o in objs:
        used.setdefault(o.cgram_palette, []).append(f"sprite {o.number}")
    for a in areas:
        used.setdefault(a.cgram_palette, []).append(f"BG B{a.number}")
    palettes_image(colors, used, f"CGRAM no frame {fd.frame} (linha = paleta, coluna = índice)").save(out_dir / "palettes.png")
    files["palettes"] = rel(out_dir / "palettes.png")
    mapping = cap.meta.get("mapping", "lorom")

    def detail(t, stem: str, head: str) -> dict:
        object_sheet(fd, t, head).save(out_dir / f"{stem}.png")
        index_panels(fd, t, head + " · um painel por índice (magenta = onde ele aparece)").save(out_dir / f"{stem}-indices.png")
        desc = t.describe(colors)
        desc["imagens"] = [rel(out_dir / f"{stem}.png"), rel(out_dir / f"{stem}-indices.png")]
        if rom_data is not None:
            pal16 = [int(colors[16 * t.cgram_palette + i]) for i in range(16)]
            desc["origem"] = find_palette_sources(pal16, rom_data, mapping, fd.wram)
        return desc

    described = [detail(o, f"obj{o.number}", f"sprite {o.number} · paleta OAM {o.palette} = CGRAM {o.cgram_palette} · "
                                                 f"frame {fd.frame}") for o in objs[:max_objects]]
    bgs = [detail(a, f"bg{a.number}", f"BG B{a.number} · paleta CGRAM {a.cgram_palette} · frame {fd.frame}")
           for a in areas[:max_bg]]
    small = [{"objeto": o.number, "paleta_oam": o.palette, "pixeis": o.pixels, "caixa": list(o.bbox)} for o in objs[max_objects:]]
    small_bg = [{"area_bg": a.number, "paleta_cgram": a.cgram_palette, "pixeis": a.pixels, "caixa": list(a.bbox)}
                for a in areas[max_bg:]]
    report = {"frame": fd.frame, "captura": rel(cap.dir), "concordancia": fd.agreement() if fd.snap is not None else None,
              "objetos": described, "objetos_pequenos": small, "areas_bg": bgs, "areas_bg_pequenas": small_bg,
              "arquivos": files, "regra": "paleta p do OAM = paleta p+8 da CGRAM (cores 128+16p…)"}
    write_json(out_dir / "snap.json", report)
    (out_dir / "report.md").write_text(_report_md(cap, fd, report), encoding="utf-8", newline="\n")
    report["report"] = rel(out_dir / "report.md")
    return report


def _origin_lines(src: dict | None) -> list[str]:
    if not src:
        return []
    L = ["", "De onde vem esta paleta:"]
    for w in src["wram"]:
        L.append(f"- WRAM `{w['addr']}` ({w['como']}) — buffer que o jogo copia para a CGRAM; "
                 f"`fab probe writes <jogo> {w['addr']}` mostra quem o enche e `fab ppu dma` quem o copia")
    for r in src["rom"]:
        extra = f" (janela HiROM `{r['janela_hirom']}`)" if r.get("janela_hirom") else ""
        L.append(f"- ROM PC `{r['pc']}` = `{r['snes']}`{extra}: índices {r['indice_inicial']}-"
                 f"{r['indice_inicial'] + r['cores'] - 1}")
    if src["como"]:
        L.append(f"  - como foi achada: {src['como']}")
    if not src["rom"]:
        L.append("- ROM: não achada como dado cru (comprimida ou calculada) → siga o buffer da WRAM com `fab probe writes`")
    return L


def _report_md(cap: Capture, fd: FrameData, rep: dict) -> str:
    ag = rep["concordancia"]
    L = [f"# Pintura — {cap.meta.get('game')} · frame {fd.frame}", "",
         f"Captura: `{rel(cap.dir)}` · state `{cap.meta.get('state')}` · ROM `{cap.meta.get('rom')}`", "",
         "Olhe primeiro `overview.png` (SPRITES numerados) e `bg.png` (áreas de BG: B1, B2…). Depois, para o",
         "alvo que interessa, `objN-indices.png` / `bgN-indices.png`: um painel por índice de cor — diga quais",
         "painéis são a parte a pintar.", "",
         "## Regras de hardware (não esqueça)",
         "- Sprites usam as paletas **8-15** da CGRAM: paleta `p` do OAM = paleta `p+8` da CGRAM",
         "  (cores `128+16p` a `143+16p`). Em Mode 1 os BGs de 4bpp usam 0-127 (BG3, 2bpp: grupos de 4 cores).",
         "- Índice 0 de cada paleta é transparente; a cor 0 da CGRAM é o fundo (backdrop).", ""]
    if ag:
        L += [f"Conferência render × falsa cor: {ag['concordam']}/{ag['obj_px_falsa_cor']} píxeis de sprite "
              f"({ag['fracao']:.1%})" + (" — OK" if ag["fracao"] >= 0.98 else " — ⚠ BAIXA: o snapshot pode não ser o do desenho"), ""]
    L += ["## Sprites (objetos)", "", "| obj | paleta OAM | CGRAM | cores | píxeis | sprites | caixa (x0,y0,x1,y1) |",
          "|---|---|---|---|---|---|---|"]
    for o in rep["objetos"]:
        L.append(f"| {o['objeto']} | {o['paleta_oam']} | {o['paleta_cgram']} | {o['cores_cgram']} | {o['pixeis']} | "
                 f"{o['sprites']} | {o['caixa']} |")
    for o in rep["objetos_pequenos"]:
        L.append(f"| {o['objeto']} | {o['paleta_oam']} | {o['paleta_oam'] + 8} | — | {o['pixeis']} | — | {o['caixa']} |")
    L += ["", "## Áreas de BG", "", "| área | paleta CGRAM | cores | píxeis | caixa (x0,y0,x1,y1) |", "|---|---|---|---|---|"]
    for a in rep["areas_bg"]:
        L.append(f"| B{a['area_bg']} | {a['paleta_cgram']} | {a['cores_cgram']} | {a['pixeis']} | {a['caixa']} |")
    for a in rep["areas_bg_pequenas"]:
        L.append(f"| B{a['area_bg']} | {a['paleta_cgram']} | — | {a['pixeis']} | {a['caixa']} |")
    for o in rep["objetos"]:
        L += ["", f"## Sprite {o['objeto']} — índices de cor usados", "", "| índice | cor (BGR555) | píxeis |", "|---|---|---|"]
        L += [f"| {i} | `{v['cor']}` | {v['pixeis']} |" for i, v in o["indices"].items()]
        L += _origin_lines(o.get("origem"))
    for a in rep["areas_bg"]:
        L += ["", f"## BG B{a['area_bg']} — índices de cor usados", "", "| índice | cor (BGR555) | píxeis |", "|---|---|---|"]
        L += [f"| {i} | `{v['cor']}` | {v['pixeis']} |" for i, v in a["indices"].items()]
        L += _origin_lines(a.get("origem"))
    L += ["", "## Próximos passos", "",
          "1. Recolorir índices inteiros (tudo o que usa o índice muda): `fab palette ramp <captura> --object N` (ou "
          "`--bg N`, ou `--cgram-palette P`) `--indices a-b --to <cor>` → escolher na imagem → `fab paint set …`.",
          "2. Se a peça partilha índice com outra (ex.: luva × cabelo): `fab sprite regions <captura> --object N --indices a,b`.",
          "3. De onde vêm paleta/OAM/gráficos e onde pôr um hook: `fab ppu dma <jogo> --state <state>`.", ""]
    return "\n".join(L)


def object_tiles(fd: FrameData, target, indices: list[int] | None = None) -> list[dict]:
    """Tiles 8x8 (VRAM) que desenham píxeis visíveis do alvo-sprite: endereço, hash do conteúdo, os 32 bytes e
    quantos píxeis (dos `indices`, se dados) cada um põe na tela."""
    lay = fd.layer()
    m = target.mask & (lay.tile_addr >= 0)
    if indices:
        m &= np.isin(lay.color, indices)
    out: dict[int, dict] = {}
    for a in lay.tile_addr[m]:
        a = int(a)
        if a not in out:
            raw = bytes(fd.snap.vram[a:a + 32])
            out[a] = {"vram": a, "hash": tile_hash(fd.snap.vram, a), "bytes": raw, "pixeis": 0}
        out[a]["pixeis"] += 1
    return sorted(out.values(), key=lambda t: -t["pixeis"])


def find_raw_tile(rom_data: bytes, tile: bytes, limit: int = 8) -> list[int]:
    """Onde os 32 bytes do tile aparecem crus na ROM (gráfico não comprimido → editável direto)."""
    if tile == bytes(32):
        return []
    hits, pos = [], rom_data.find(tile)
    while pos != -1 and len(hits) < limit:
        hits.append(pos)
        pos = rom_data.find(tile, pos + 1)
    return hits


def tiles_sheet(tiles: list[dict], colors16: list[int], title: str, highlight: dict[str, set[int]] | None = None,
                cols: int = 8, k: int = 10) -> Image.Image:
    """Tiles ampliados (cada píxel um bloco, cor real da paleta) com o nº, o endereço na VRAM e a origem na ROM.
    `highlight` = {hash: {píxeis 0-63}} contorna em magenta os píxeis de uma peça (rótulos)."""
    cell = 8 * k
    rows = max(1, math.ceil(len(tiles) / cols))
    out = Image.new("RGB", (cols * (cell + 14) + 14, 40 + rows * (cell + 46)), BG_DARK)
    d = ImageDraw.Draw(out)
    _text(d, (12, 8), title, size=15)
    for n, t in enumerate(tiles):
        r, c = divmod(n, cols)
        x, y = 14 + c * (cell + 14), 40 + r * (cell + 46)
        px = ppu.decode_4bpp(t["bytes"])
        img = np.zeros((8, 8, 3), np.uint8)
        for i in range(16):
            img[px == i] = swatch_rgb(colors16[i]) if i else (40, 40, 48)
        out.paste(_scale(img, k), (x, y + 30))
        hl = (highlight or {}).get(t["hash"], set())
        for p in hl:
            py, pxx = divmod(int(p), 8)
            d.rectangle((x + pxx * k, y + 30 + py * k, x + (pxx + 1) * k - 1, y + 30 + (py + 1) * k - 1), outline=(255, 0, 255))
        src = t.get("rom")
        _text(d, (x, y), f"T{n + 1}  VRAM ${t['vram']:04X}", size=12)
        _text(d, (x, y + 15), (f"ROM 0x{src[0]:06X}" + (f" (+{len(src) - 1})" if len(src) > 1 else "")) if src else "não crua na ROM",
              size=11, fill=TEXT_DIM if src else (255, 170, 120))
    return out


def tile_hash(vram: bytes, addr: int) -> str:
    """Hash do CONTEÚDO de um tile 4bpp (32 bytes): o mesmo desenho tem o mesmo hash em qualquer slot da VRAM."""
    return hashlib.sha1(bytes(vram[addr:addr + 32])).hexdigest()[:12]

