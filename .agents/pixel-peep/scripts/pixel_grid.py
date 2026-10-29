#!/usr/bin/env python3
"""pixel_grid — lê pixel-art minúscula ampliando as CÉLULAS de píxel (NEAREST) mantendo a
grelha e os rótulos à escala normal. O produto principal é o MAPA: a matriz de valores
(índice da paleta ou hex) por célula — é ela que diz ONDE alterar; nunca é preciso converter
de volta para ver "normal".

A varinha mágica (--wand) funde análise RGB: dada uma cor/índice, lista a FAMÍLIA de cores
próximas (--tolerance) e marca tudo o que mudaria (máscara X/.).

Exemplos:
  python pixel_grid.py frame.png --crop 12,10,24,12 --out work/grid.png
  python pixel_grid.py frame.png --crop 12,10,8,8 --indices \\
      --palette bgr555 roms/sfa2/sfa2.sfc:0x1F0260:16 --out work/tile.png
  python pixel_grid.py frame.png --crop 12,10,8,8 --palette ... --wand 15 --tolerance 30 \\
      --out work/wand.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def bgr555_rgb(t: int) -> tuple[int, int, int]:
    """Cor SNES (BGR555) -> RGB888 por replicação de bits: (v << 3) | (v >> 2)."""
    return tuple(((v << 3) | (v >> 2)) for v in ((t & 31), ((t >> 5) & 31), ((t >> 10) & 31)))


def load_palette(spec: str) -> list[tuple[int, int, int]]:
    """--palette bgr555 <arquivo>:<offset>:<contagem> | --palette hex #RRGGBB,#RRGGBB,..."""
    if spec.startswith("bgr555 "):
        path, off, count = spec.split()[1].rsplit(":", 2)
        data = Path(path).read_bytes()
        off_i, n = int(off, 0), int(count, 0)
        return [bgr555_rgb(data[off_i + i * 2] | (data[off_i + i * 2 + 1] << 8)) for i in range(n)]
    if spec.startswith("hex "):
        out = []
        for c in spec.split()[1].split(","):
            c = c.strip().lstrip("#")
            out.append((int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)))
        return out
    raise SystemExit(f"paleta desconhecida: {spec!r} (use 'bgr555 arq:off:n' ou 'hex #aabbcc,...')")


def dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--crop", help="x,y,w,h em píxeis da origem (senão usa a imagem toda)")
    ap.add_argument("--scale", type=int, default=0, help="fator por píxel (0 = automático via --fit)")
    ap.add_argument("--fit", type=int, default=640, help="tamanho alvo da área de células (px finais)")
    ap.add_argument("--palette", help="'bgr555 arq:off:count' ou 'hex #aabbcc,...' → valores = índices")
    ap.add_argument("--indices", action="store_true", help="escrever o valor em cada célula (scale>=4)")
    ap.add_argument("--grid", type=int, default=1, help="espessura da grelha em px finais (0 = sem)")
    ap.add_argument("--labels", action="store_true", default=True)
    ap.add_argument("--no-labels", dest="labels", action="store_false")
    ap.add_argument("--border", type=int, default=1, help="borda exterior em px finais (não ampliada)")
    ap.add_argument("--wand", help="varinha mágica: índice (com --palette) ou #RRGGBB → marca a família")
    ap.add_argument("--tolerance", type=float, default=48.0, help="distância RGB da família (padrão 48)")
    ap.add_argument("--out", required=True, help="PNG de saída (o mapa ampliado)")
    ap.add_argument("--text", help="matriz de valores (padrão: <out>.txt)")
    ap.add_argument("--mask", help="máscara da varinha X/. (padrão: <out>.mask.txt; só com --wand)")
    args = ap.parse_args()

    img = Image.open(args.image).convert("RGB")
    if args.crop:
        x, y, w, h = (int(v) for v in args.crop.split(","))
        img = img.crop((x, y, x + w, y + h))
    a = np.array(img)
    H, W = a.shape[:2]
    if W * H > 4096:
        print(f"aviso: {W}x{H} = {W*H} células — recorte com --crop", file=sys.stderr)

    palette = load_palette(args.palette) if args.palette else None
    idx_of: dict[tuple[int, int, int], int] = {}
    if palette:
        for i, c in enumerate(palette):
            idx_of.setdefault(tuple(c), i)

    # ── a varinha mágica: família de cores próximas ───────────────────────────
    family: set[tuple[int, int, int]] = set()
    wand_idx: set[int] = set()
    if args.wand:
        if palette and args.wand.strip().replace("0x", "").isalnum() and len(args.wand.strip()) <= 4:
            w = args.wand.strip()
            n = int(w, 16) if w.lower().startswith("0x") else (int(w, 16) if any(ch in w.lower() for ch in "abcdef") else int(w, 10))
            if not 0 <= n < len(palette):
                raise SystemExit(f"índice {n} fora da paleta (0..{len(palette)-1})")
            target = palette[n]
        else:
            c = args.wand.strip().lstrip("#")
            target = (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
        universe = palette or sorted({tuple(int(v) for v in a[j, i]) for j in range(H) for i in range(W)})
        print(f"varinha: alvo {target} tolerância {args.tolerance:g}")
        for c in universe:
            d = dist(c, target)
            if d <= args.tolerance:
                family.add(tuple(c))
                if palette and tuple(c) in idx_of:
                    wand_idx.add(idx_of[tuple(c)])
                print(f"  família  {c}  dist={d:5.1f}" + (f"  idx {idx_of[tuple(c)]:02X}" if palette and tuple(c) in idx_of else ""))

    k = args.scale or max(2, round(args.fit / max(W, H)))
    if not args.scale and k * max(W, H) > 1600:
        k = max(2, 1600 // max(W, H))
    lab = 14 if args.labels else 0
    cell, gw = k, args.grid
    Wp = W * cell + (W + 1) * gw + args.border * 2 + lab
    Hp = H * cell + (H + 1) * gw + args.border * 2 + lab
    canvas = Image.new("RGB", (Wp, Hp), (28, 28, 28))
    dr = ImageDraw.Draw(canvas)
    ox = args.border + gw + lab
    oy = args.border + gw + lab

    # células ampliadas + grelha fina por cima (nunca ampliada)
    for j in range(H):
        for i in range(W):
            cx = ox + i * (cell + gw)
            cy = oy + j * (cell + gw)
            canvas.paste(img.crop((i, j, i + 1, j + 1)).resize((cell, cell), Image.NEAREST), (cx, cy))
            if gw:
                dr.rectangle([cx, cy, cx + cell + gw - 1, cy + cell + gw - 1], outline=(255, 255, 255))
    rows, masks = [], []
    for j in range(H):
        row, mrow = [], []
        for i in range(W):
            c = tuple(int(v) for v in a[j, i])
            inidx = idx_of.get(c)
            val = f"{inidx:02X}" if (palette and inidx is not None) else f"{c[0]:02X}{c[1]:02X}{c[2]:02X}"
            row.append(val)
            hit = args.wand and c in family
            mrow.append("X" if hit else ".")
            cx = ox + i * (cell + gw)
            cy = oy + j * (cell + gw)
            if args.indices and k >= 4:
                dark = sum(c) < 380
                dr.text((cx + max(1, cell // 8), cy + max(1, cell // 6)), val[:2],
                        fill=(255, 255, 255) if dark else (20, 20, 20))
            if hit:
                dr.rectangle([cx + 1, cy + 1, cx + cell - 2, cy + cell - 2], outline=(255, 0, 255), width=max(1, k // 8))
        rows.append(" ".join(row))
        masks.append(" ".join(mrow))
        if args.labels:
            dr.text((2, oy + j * (cell + gw) + cell // 2 - 4), str(j), fill=(200, 200, 120))
    if args.labels:
        for i in range(W):
            dr.text((ox + i * (cell + gw) + cell // 2 - 3, 2), str(i), fill=(200, 200, 120))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    txt = Path(args.text) if args.text else out.with_suffix(".txt")
    txt.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"{out} ({Wp}x{Hp}, células {W}x{H} a {k}x) · mapa de valores: {txt}")
    if args.wand:
        mpath = Path(args.mask) if args.mask else out.with_suffix(".mask.txt")
        mpath.write_text("\n".join(masks) + "\n", encoding="utf-8")
        n = sum(m.count("X") for m in masks)
        print(f"máscara da varinha: {mpath} · {n} píxeis na família")
    return 0


if __name__ == "__main__":
    sys.exit(main())
