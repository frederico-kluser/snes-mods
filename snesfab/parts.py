"""Peças de sprite que partilham índices de cor (ex.: luvas × cabelo no mesmo ouro).

Quando a mesma cor pinta duas peças, recolorir o índice muda as duas. Para separar:
1. `regions`: as regiões conexas desses índices num frame, numeradas numa imagem → o agente diz quais
   números são a peça ("2,3 = luva").
2. `label`: os píxeis dessas regiões viram rótulos POR CONTEÚDO DE TILE: (hash dos 32 bytes do tile,
   píxel 0-63 dentro do tile) → peça. O número do tile (slot da VRAM) muda de pose para pose e é ambíguo
   (o mesmo slot é luva numa pose e cabelo noutra); o CONTEÚDO não.
3. `census`: em muitos frames, quanto do alvo está rotulado; regiões novas viram uma folha de pendentes
   numerada (o agente rotula por número); e a SEPARABILIDADE por sprite: quantos sprites (entradas do OAM)
   têm só a peça, só a outra, ou as duas misturadas (estes não se separam trocando a paleta do sprite).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .sprites import (BG_DARK, TEXT_DIM, FrameData, SpriteObject, _crop_box, _scale, _text, components,
                      find_objects, tile_hash)
from .util import now_iso, write_json

PART_COLORS = [(255, 70, 70), (70, 170, 255), (255, 215, 0), (90, 230, 110), (255, 110, 230), (255, 150, 50),
               (170, 130, 255), (0, 220, 200)]


# ── regiões de um frame ───────────────────────────────────────────────────────────

def target_mask(fd: FrameData, palette: int, indices: list[int], obj: SpriteObject | None = None) -> np.ndarray:
    lay = fd.layer()
    m = fd.visible_obj() & (lay.palette == palette) & np.isin(lay.color, indices)
    if obj is not None:
        m &= obj.mask
    return m


def regions(fd: FrameData, palette: int, indices: list[int], obj: SpriteObject | None = None,
            min_px: int = 2) -> list[np.ndarray]:
    return components(target_mask(fd, palette, indices, obj), 8, min_px)


def regions_image(fd: FrameData, regs: list[np.ndarray], box: tuple[int, int, int, int], title: str,
                  labels: dict[int, str] | None = None) -> Image.Image:
    """Recorte ampliado com cada região contornada numa cor e o NÚMERO grande ao lado; à direita, o real."""
    x0, y0, x1, y1 = box
    crop = fd.real[y0:y1, x0:x1]
    k = max(3, min(8, 420 // max(crop.shape[0], 1)))
    base = (crop.mean(axis=2, keepdims=True) * 0.5 + 30).astype(np.uint8).repeat(3, axis=2)
    for n, r in enumerate(regs, 1):
        c = PART_COLORS[(n - 1) % len(PART_COLORS)]
        yy, xx = r[:, 0] - y0, r[:, 1] - x0
        ok = (yy >= 0) & (yy < base.shape[0]) & (xx >= 0) & (xx < base.shape[1])
        base[yy[ok], xx[ok]] = c
    big = _scale(base, k)
    real = _scale(crop, max(2, k // 2))
    W = big.width + real.width + 300
    H = max(big.height, real.height) + 60
    out = Image.new("RGB", (W, H), BG_DARK)
    out.paste(big, (10, 40))
    out.paste(real, (20 + big.width, 40))
    d = ImageDraw.Draw(out)
    _text(d, (10, 8), title, size=15)
    for n, r in enumerate(regs, 1):
        c = PART_COLORS[(n - 1) % len(PART_COLORS)]
        cy, cx = r[:, 0].mean() - y0, r[:, 1].mean() - x0
        tx, ty = 10 + int(cx * k) + 8, 40 + int(cy * k) - 12
        _text(d, (tx, ty), str(n), size=20, fill=(0, 0, 0), bg=c)
    x = 30 + big.width + real.width
    y = 40
    _text(d, (x, y), "região · píxeis · caixa", size=13, fill=TEXT_DIM)
    for n, r in enumerate(regs, 1):
        c = PART_COLORS[(n - 1) % len(PART_COLORS)]
        y += 24
        d.rectangle((x, y + 2, x + 16, y + 18), fill=c)
        lab = f"  [{labels[n]}]" if labels and n in labels else ""
        _text(d, (x + 24, y + 1), f"{n} · {len(r)} px · ({r[:, 1].min()},{r[:, 0].min()})-({r[:, 1].max()},{r[:, 0].max()}){lab}",
              size=13)
    return out


# ── rótulos por conteúdo de tile ───────────────────────────────────────────────────

class PartStore:
    """parts.json: {"indices": [...], "palette": p, "parts": {"luva": {hash: [px,…]}, "cabelo": {…}}, "history": […]}"""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else \
            {"_doc": "rótulos de peça por CONTEÚDO de tile (hash dos 32 bytes → píxeis 0-63); gerado por `fab sprite label`",
             "parts": {}, "history": []}
        self._index: dict[tuple[str, int], str] | None = None

    def lookup(self, h: str, px: int) -> str | None:
        if self._index is None:
            self._index = {}
            for part, tiles in self.data["parts"].items():
                for hh, pxs in tiles.items():
                    for p in pxs:
                        self._index[(hh, int(p))] = part
        return self._index.get((h, int(px)))

    def add(self, part: str, pairs: list[tuple[str, int]]) -> tuple[int, int]:
        """Grava (hash, px) → peça. Devolve (novos, conflitos com outra peça — estes NÃO são sobrescritos)."""
        tiles = self.data["parts"].setdefault(part, {})
        new = conflict = 0
        for h, px in pairs:
            cur = self.lookup(h, px)
            if cur == part:
                continue
            if cur is not None:
                conflict += 1
                continue
            tiles.setdefault(h, [])
            tiles[h].append(int(px))
            self._index[(h, int(px))] = part
            new += 1
        for h in tiles:
            tiles[h] = sorted(set(tiles[h]))
        return new, conflict

    def save(self, note: str = "") -> None:
        if note:
            self.data["history"].append({"time": now_iso(), "note": note})
        write_json(self.path, self.data)

    def stats(self) -> dict:
        return {p: {"tiles": len(t), "pixeis": sum(len(v) for v in t.values())} for p, t in self.data["parts"].items()}


def pixel_keys(fd: FrameData, pts: np.ndarray) -> list[tuple[str, int]]:
    lay = fd.layer()
    vram = fd.snap.vram
    cache: dict[int, str] = {}
    out = []
    for y, x in pts:
        a = int(lay.tile_addr[y, x])
        if a < 0:
            continue
        h = cache.get(a)
        if h is None:
            h = cache[a] = tile_hash(vram, a)
        out.append((h, int(lay.tile_px[y, x])))
    return out


def classify(fd: FrameData, store: PartStore, mask: np.ndarray, grow: bool = True) -> tuple[np.ndarray, list[str]]:
    """Rótulo por píxel (−1 = sem rótulo; senão o índice na lista de peças). Com `grow`, uma região conexa
    cujos píxeis rotulados são TODOS da mesma peça é completada com essa peça."""
    parts = sorted(store.data["parts"])
    lab = np.full(mask.shape, -1, np.int16)
    lay = fd.layer()
    vram = fd.snap.vram
    cache: dict[int, str] = {}
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys, xs):
        a = int(lay.tile_addr[y, x])
        h = cache.get(a)
        if h is None:
            h = cache[a] = tile_hash(vram, a)
        p = store.lookup(h, int(lay.tile_px[y, x]))
        if p is not None:
            lab[y, x] = parts.index(p)
    if grow:
        for comp in components(mask, 8):
            vals = lab[comp[:, 0], comp[:, 1]]
            known = set(int(v) for v in vals if v >= 0)
            if len(known) == 1 and (vals >= 0).sum() >= max(3, len(comp) // 5):
                lab[comp[:, 0], comp[:, 1]] = known.pop()
    return lab, parts


# ── censo: cobertura, pendentes e separabilidade por sprite ────────────────────────────

def census(frames: list[FrameData], store: PartStore, palette: int, indices: list[int], target: str) -> dict:
    """Pendentes deduplicados por CONTEÚDO: a mesma região (mesmos tiles/píxeis) em vários frames aparece uma
    vez só, com a contagem — rotular uma cobre todas as repetições."""
    import hashlib
    from collections import Counter, defaultdict
    parts = sorted(store.data["parts"])
    per_frame = []
    uniq: dict[str, dict] = {}
    sep = {"so_alvo": 0, "so_outras": 0, "misturados": 0}
    tiles: dict[int, Counter] = defaultdict(Counter)       # nº do tile no OAM → alvo/outra/misto
    mixed_examples = []
    for fd in frames:
        m = target_mask(fd, palette, indices)
        if not m.any():
            continue
        lab, _ = classify(fd, store, m)
        n_t = int(m.sum())
        n_lab = int((lab >= 0).sum())
        un = m & (lab < 0)
        for comp in components(un, 8, 3):
            sig = hashlib.sha1(repr(sorted(pixel_keys(fd, comp))).encode()).hexdigest()
            if sig in uniq:
                uniq[sig]["vezes"] += 1
            else:
                lay = fd.layer()
                ys, xs = np.nonzero(fd.visible_obj() & (lay.palette == palette))
                box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
                uniq[sig] = {"fd": fd, "comp": comp, "vezes": 1, "lab": lab, "parts": parts, "target": target,
                             "box": box}
        lay = fd.layer()
        mixed_here = []
        for e in np.unique(lay.oam[m]):
            em = m & (lay.oam == e)
            ls = set(int(v) for v in lab[em] if v >= 0)
            has_t = target in parts and parts.index(target) in ls
            has_o = any(parts[v] != target for v in ls)
            tile = lay.entries[int(e)].tile
            if has_t and has_o:
                sep["misturados"] += 1
                mixed_here.append(int(e))
                tiles[tile]["misto"] += 1
            elif has_t:
                sep["so_alvo"] += 1
                tiles[tile]["alvo"] += 1
            elif has_o:
                sep["so_outras"] += 1
                tiles[tile]["outra"] += 1
        if mixed_here and len(mixed_examples) < 24:
            mixed_examples.append((fd, mixed_here))
        per_frame.append({"frame": fd.frame, "alvo_px": n_t, "rotulados": n_lab,
                          "cobertura": round(n_lab / n_t, 3) if n_t else 1.0, "sprites_misturados": mixed_here})
    covered = sum(1 for f in per_frame if f["cobertura"] >= 0.999)
    pending = sorted(uniq.values(), key=lambda p: (p["fd"].frame, -len(p["comp"])))
    return {"frames": per_frame, "frames_100": covered, "frames_total": len(per_frame), "pendentes": pending,
            "separabilidade": sep, "misturados": mixed_examples, "pecas": parts,
            "niveis": separability_levels(sep, tiles)}


def separability_levels(sep: dict, tiles: dict) -> dict:
    """Em que nível a peça-alvo se separa das outras que usam os MESMOS índices — e o mecanismo que basta:
    1. índice: nenhuma outra peça usa esses índices → troca de paleta (só dados);
    2. tile: cada número de tile do OAM é sempre só alvo ou sempre só outra → hook no OAM por tabela de tiles;
    3. sprite: há tiles ambíguos (o mesmo nº é alvo numa pose e outra noutra) mas nenhum sprite mistura → é
       preciso marcar por pose/cel (adaptador do motor, ex.: `fab sprite marks`);
    4. píxel: há sprites com as duas peças → só editando o desenho (tile) separa; pela paleta sobra resíduo."""
    seguros = sorted(f"${t:03X}" for t, c in tiles.items() if c["alvo"] and not c["outra"] and not c["misto"])
    ambiguos = sorted(f"${t:03X}" for t, c in tiles.items() if c["alvo"] and (c["outra"] or c["misto"]))
    if sep["so_outras"] == 0 and sep["misturados"] == 0:
        nivel, mec = 1, ("nenhuma outra peça usa esses índices: troque as cores da paleta (fab palette ramp → "
                         "fab paint set) — só dados, sem código")
    elif not ambiguos:
        nivel, mec = 2, ("cada número de tile é sempre da mesma peça: um hook antes do DMA do OAM (fab ppu dma mostra "
                         "onde) troca a paleta dos sprites com esses tiles para uma paleta-espelho")
    elif sep["misturados"] == 0:
        nivel, mec = 3, ("o mesmo número de tile é a peça-alvo numa pose e outra peça noutra: a decisão tem de ser "
                         "por pose/cel (adaptador do motor de sprites; para listas de cels: fab sprite marks)")
    else:
        nivel, mec = 4, (f"{sep['misturados']} sprite(s) têm as DUAS peças: pela paleta, esses píxeis ficam com resíduo; "
                         "separar 100% exige editar o desenho do tile (gráfico cru: fab sprite tiles; comprimido: "
                         "precisa do codec)")
    return {"nivel": nivel, "mecanismo": mec, "tiles_seguros": len(seguros), "tiles_ambiguos": len(ambiguos),
            "tiles_seguros_lista": seguros,
            "exemplos_ambiguos": ambiguos[:12], "sprites_misturados": sep["misturados"]}


LABELED_TARGET, LABELED_OTHER, PENDING = (255, 90, 90), (90, 160, 255), (255, 0, 255)


def pending_sheet(pending: list[dict], title: str, start: int = 1, per_sheet: int = 12, cols: int = 4) -> Image.Image:
    """Cada região sem rótulo num quadro: o sprite em cinza, a região em MAGENTA e, para dar contexto, o que já
    está rotulado no mesmo frame (vermelho = a peça-alvo, azul = outra peça)."""
    items = pending[:per_sheet]
    cw, ch = 300, 260
    rows = math.ceil(len(items) / cols)
    out = Image.new("RGB", (cols * (cw + 10) + 10, 64 + rows * (ch + 10)), BG_DARK)
    d = ImageDraw.Draw(out)
    _text(d, (10, 8), title, size=15)
    _text(d, (10, 30), "magenta = região a decidir · vermelho = já rotulado como a peça · azul = já rotulado como outra",
          size=12, fill=TEXT_DIM)
    for n, it in enumerate(items):
        fd, comp, lab, parts, target = it["fd"], it["comp"], it["lab"], it["parts"], it["target"]
        r, c = divmod(n, cols)
        x, y = 10 + c * (cw + 10), 64 + r * (ch + 10)
        bx0, by0, bx1, by1 = it.get("box") or (int(comp[:, 1].min()) - 30, int(comp[:, 0].min()) - 30,
                                               int(comp[:, 1].max()) + 30, int(comp[:, 0].max()) + 30)
        y0, y1 = max(0, by0 - 3), min(fd.real.shape[0], by1 + 3)       # o personagem INTEIRO dá o contexto
        x0, x1 = max(0, bx0 - 3), min(fd.real.shape[1], bx1 + 3)
        crop = fd.real[y0:y1, x0:x1]
        g = (crop.mean(axis=2, keepdims=True) * 0.55 + 30).astype(np.uint8).repeat(3, axis=2)
        sub = lab[y0:y1, x0:x1]
        for pi, p in enumerate(parts):
            g[sub == pi] = LABELED_TARGET if p == target else LABELED_OTHER
        yy, xx = comp[:, 0] - y0, comp[:, 1] - x0
        ok = (yy >= 0) & (yy < g.shape[0]) & (xx >= 0) & (xx < g.shape[1])
        g[yy[ok], xx[ok]] = PENDING
        body_w = cw - 130
        k = max(1, min(body_w // max(g.shape[1], 1), (ch - 30) // max(g.shape[0], 1)))
        body = _scale(g, k)
        out.paste(body, (x, y + 28))
        # zoom da região (com 6 px de margem), à direita do corpo
        ry0, ry1 = max(0, int(yy.min()) - 6), min(g.shape[0], int(yy.max()) + 7)
        rx0, rx1 = max(0, int(xx.min()) - 6), min(g.shape[1], int(xx.max()) + 7)
        zz = g[ry0:ry1, rx0:rx1]
        real_z = crop[ry0:ry1, rx0:rx1]
        pend_z = np.all(zz == PENDING, axis=-1)
        mix = real_z.copy()
        mix[pend_z] = (mix[pend_z] * 0.4 + np.array(PENDING) * 0.6).astype(np.uint8)
        kz = max(2, min(120 // max(mix.shape[1], 1), 120 // max(mix.shape[0], 1)))
        out.paste(_scale(mix, kz), (x + body.width + 8, y + 28))
        d.rectangle((x + k * rx0, y + 28 + k * ry0, x + k * rx1, y + 28 + k * ry1), outline=(255, 255, 255))
        _text(d, (x, y), f"{start + n}", size=20, fill=(0, 0, 0), bg=PENDING)
        _text(d, (x + 40, y + 4), f"f{fd.frame} · {len(comp)} px · ×{it['vezes']}", size=12, fill=TEXT_DIM)
    return out


def mixed_sheet(examples: list[tuple[FrameData, list[int]]], store: PartStore, palette: int, indices: list[int],
                target: str, title: str, cols: int = 4) -> Image.Image:
    """Sprites que têm a peça-alvo E outra peça com os mesmos índices: cada um ampliado, peças coloridas."""
    parts = sorted(store.data["parts"])
    tiles = []
    for fd, ents in examples:
        lay = fd.layer()
        m = target_mask(fd, palette, indices)
        lab, _ = classify(fd, store, m)
        ys, xs = np.nonzero(fd.visible_obj() & (lay.palette == palette))
        bx0, by0, bx1, by1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
        body = (fd.real[by0:by1, bx0:bx1].mean(axis=2, keepdims=True) * 0.5 + 30).astype(np.uint8).repeat(3, axis=2)
        sub = lab[by0:by1, bx0:bx1]
        for pi, p in enumerate(parts):
            body[(sub == pi) & m[by0:by1, bx0:bx1]] = PART_COLORS[0] if p == target else PART_COLORS[1]
        for e in ents:
            ent = lay.entries[e]
            sx0, sy0 = max(ent.x, bx0) - bx0, max(ent.y, by0) - by0
            sx1, sy1 = min(ent.x + ent.width, bx1) - bx0, min(ent.y + ent.height, by1) - by0
            tiles.append((fd.frame, e, body, (sx0, sy0, sx1, sy1)))
    tiles = tiles[:24]
    cw, ch = 300, 260
    rows = max(1, math.ceil(len(tiles) / cols))
    out = Image.new("RGB", (cols * (cw + 10) + 10, 64 + rows * (ch + 10)), BG_DARK)
    d = ImageDraw.Draw(out)
    _text(d, (10, 8), title, size=15)
    _text(d, (10, 30), f"vermelho = {target} · azul = outra peça com os mesmos índices · caixa branca = o sprite (16x16…)",
          size=12, fill=TEXT_DIM)
    for n, (f, e, body, (sx0, sy0, sx1, sy1)) in enumerate(tiles):
        r, c = divmod(n, cols)
        x, y = 10 + c * (cw + 10), 64 + r * (ch + 10)
        k = max(1, min((cw - 130) // max(body.shape[1], 1), (ch - 30) // max(body.shape[0], 1)))
        big = _scale(body, k)
        out.paste(big, (x, y + 24))
        d.rectangle((x + k * sx0, y + 24 + k * sy0, x + k * sx1, y + 24 + k * sy1), outline=(255, 255, 255))
        zoom = body[max(0, sy0):sy1, max(0, sx0):sx1]
        if zoom.size:
            kz = max(2, min(120 // max(zoom.shape[1], 1), 120 // max(zoom.shape[0], 1)))
            out.paste(_scale(zoom, kz), (x + big.width + 8, y + 24))
        _text(d, (x, y + 2), f"f{f} · sprite OAM {e}", size=12)
    return out


def object_box(fd: FrameData, palette: int) -> tuple[int, int, int, int] | None:
    objs = [o for o in find_objects(fd) if o.palette == palette]
    if not objs:
        return None
    return _crop_box(objs[0], fd.real.shape, 6)


def summarize(c: dict) -> dict:
    return {"frames": c["frames_total"], "frames_com_100%": c["frames_100"],
            "cobertura_media": round(float(np.mean([f["cobertura"] for f in c["frames"]])), 3) if c["frames"] else 0,
            "regioes_pendentes": len(c["pendentes"]), "sprites": c["separabilidade"],
            "frames_com_sprite_misturado": sum(1 for f in c["frames"] if f["sprites_misturados"]),
            "separabilidade": c["niveis"]}

