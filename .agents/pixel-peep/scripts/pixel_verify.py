#!/usr/bin/env python3
"""pixel_verify — verificação ANTES × DEPOIS pixel-perfect de uma recoloração/varinha.

Compara duas imagens do mesmo recorte contra a MÁSCARA pretendida (X/. do pixel_grid ou a
família da varinha recalculada) e diz exactamente o que saiu do âmbito:
  · falsos positivos — pintados mas NÃO pretendidos (saem no --fix, restaurados do ANTES)
  · falhados         — pretendidos mas NÃO pintados
O alvo é 0+0; o processo pode correr várias vezes (aplicar → verificar → corrigir → re-verificar).

Exemplos:
  python pixel_verify.py --before b.png --after a.png --mask work/wand.mask.txt --out work/ver.png
  python pixel_verify.py --before b.png --after a.png --palette "bgr555 rom:off:16" \\
      --wand 15 --tolerance 60 --out work/ver.png --fix work/a_corrigida.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pixel_grid import bgr555_rgb, dist, load_palette  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--mask", help="máscara X/. do pixel_grid (senão usa --wand)")
    ap.add_argument("--palette", help="'bgr555 arq:off:count' ou 'hex ...' (para --wand)")
    ap.add_argument("--wand", help="família pretendida: índice (dec/hex) ou #RRGGBB")
    ap.add_argument("--tolerance", type=float, default=48.0)
    ap.add_argument("--out", required=True, help="folha antes|depois|mudados|falsos (ampliada)")
    ap.add_argument("--fit", type=int, default=640)
    ap.add_argument("--fix", help="grava o DEPOIS com os falsos positivos restaurados do ANTES")
    args = ap.parse_args()

    b = np.array(Image.open(args.before).convert("RGB"))
    a = np.array(Image.open(args.after).convert("RGB"))
    if b.shape != a.shape:
        raise SystemExit(f"formas diferentes: antes {b.shape} depois {a.shape}")
    H, W = b.shape[:2]

    if args.mask:
        rows = Path(args.mask).read_text(encoding="utf-8").splitlines()
        intended = np.array([[c == "X" for c in r.split()] for r in rows], dtype=bool)
        if intended.shape != (H, W):
            raise SystemExit(f"máscara {intended.shape} não casa com as imagens {(H, W)}")
    elif args.wand:
        palette = load_palette(args.palette) if args.palette else None
        if palette and any(ch in args.wand.lower() for ch in "abcdef") is False and args.wand.isdigit():
            target = palette[int(args.wand, 10)]
        elif palette:
            target = palette[int(args.wand.lower().replace("0x", ""), 16)]
        else:
            c = args.wand.lstrip("#")
            target = (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
        family = {tuple(c) for c in (palette or []) if dist(tuple(c), target) <= args.tolerance}
        if not palette:
            family = {tuple(c) for j in range(H) for i in range(W)
                      if dist(tuple(int(v) for v in b[j, i]), target) <= args.tolerance}
        intended = np.array([[tuple(int(v) for v in b[j, i]) in family for i in range(W)] for j in range(H)])
    else:
        raise SystemExit("precisa de --mask ou --wand para definir o que era pretendido")

    changed = np.any(a != b, axis=2)
    false_pos = changed & ~intended
    missed = intended & ~changed
    n_c, n_i = int(changed.sum()), int(intended.sum())
    n_f, n_m = int(false_pos.sum()), int(missed.sum())
    print(f"mudados={n_c} pretendidos={n_i} falsos-positivos={n_f} falhados={n_m}")
    if n_f:
        ys, xs = np.nonzero(false_pos)
        print("falsos (x,y antes->depois):")
        for j, i in list(zip(ys, xs))[:24]:
            print(f"  ({i},{j}) {tuple(int(v) for v in b[j, i])} -> {tuple(int(v) for v in a[j, i])}")
    if n_m:
        ys, xs = np.nonzero(missed)
        print("falhados (x,y):", ", ".join(f"({i},{j})" for j, i in list(zip(ys, xs))[:24]))
    print("PIXEL-PERFECT ✅" if (n_f == 0 and n_m == 0) else "NÃO é pixel-perfect ✗ (corrigir e re-verificar)")

    # folha: antes | depois | mudados | falsos positivos (células ampliadas, grelha fina)
    k = max(2, round(args.fit / (2 * max(W, H))))
    panels = [Image.fromarray(b), Image.fromarray(a)]
    marks = np.zeros_like(b)
    marks[intended] = (60, 60, 90)
    marks[changed] = (0, 255, 255)
    marks[false_pos] = (255, 0, 255)
    panels.append(Image.fromarray(marks))
    fpm = np.zeros_like(b)
    fpm[false_pos] = (255, 0, 255)
    panels.append(Image.fromarray(fpm))
    gap = 10
    Wp = (W * k) * 4 + gap * 3
    Hp = H * k + 16
    canvas = Image.new("RGB", (Wp, Hp), (28, 28, 28))
    dr = ImageDraw.Draw(canvas)
    for n, p in enumerate(panels):
        canvas.paste(p.resize((W * k, H * k), Image.NEAREST), (n * (W * k + gap), 14))
        dr.text((n * (W * k + gap), 2), ["antes", "depois", "mudados (amarelo=falso)", "falsos"][n], fill=(220, 220, 120))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    print(f"{out} ({Wp}x{Hp})")

    if args.fix:
        fixed = a.copy()
        fixed[false_pos] = b[false_pos]
        Path(args.fix).parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(fixed).save(args.fix)
        print(f"fix: {args.fix} ({n_f} píxeis restaurados) — re-verifique com --before --after")
    return 0 if (n_f == 0 and n_m == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
