"""Comparação baseline × mod: divergência por frame, folhas lado a lado com mapa de diferenças
e sobreposição dos traços de RAM."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .media import _font, load_run_frames, pick_indices, trace_plot
from .util import rel, write_json

DIFF_THRESHOLD = 24


def _diff_overlay(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, float]:
    if a.shape != b.shape:
        b = np.asarray(Image.fromarray(b).resize((a.shape[1], a.shape[0]), Image.NEAREST))
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2) > DIFF_THRESHOLD
    out = (a.astype(np.float32) * 0.35).astype(np.uint8)
    out[d] = (255, 0, 200)
    return out, float(d.mean() * 100)


def compare_runs(base_dir: Path, mod_dir: Path, out_dir: Path, title: str,
                 base_trace: dict | None = None, mod_trace: dict | None = None, rows: int = 8) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict = {"baseline_run": rel(base_dir), "mod_run": rel(mod_dir)}
    try:
        fa, fb = load_run_frames(base_dir), load_run_frames(mod_dir)
    except Exception as e:  # sem frames: compara só os traços
        fa = fb = None
        result["frames_note"] = str(e)
    if fa is not None and fb is not None:
        A, B = fa.by_frame(), fb.by_frame()
        common = sorted(set(A) & set(B))
        pct, overlays = [], {}
        for f in common:
            ov, p = _diff_overlay(A[f], B[f])
            pct.append(p)
            overlays[f] = ov
        arr = np.asarray(pct) if pct else np.zeros(0)
        div = [f for f, p in zip(common, pct) if p > 0.05]
        result.update({
            "frames_compared": len(common),
            "first_divergence_frame": div[0] if div else None,
            "frames_divergent": len(div),
            "mean_changed_pct": round(float(arr.mean()), 3) if arr.size else 0.0,
            "max_changed_pct": round(float(arr.max()), 3) if arr.size else 0.0,
            "max_changed_frame": common[int(arr.argmax())] if arr.size else None,
        })
        # seleção: primeira divergência, picos e frames espaçados
        chosen = set()
        if div:
            chosen.add(div[0])
        for i in np.argsort(-arr)[: 3]:
            chosen.add(common[int(i)])
        for i in pick_indices(len(common), rows):
            if len(chosen) >= rows:
                break
            chosen.add(common[i])
        chosen = sorted(chosen)[:rows]
        font = _font(13)
        h, w = A[common[0]].shape[:2]
        lab = 18
        sheet = Image.new("RGB", (3 * w + 8, 26 + len(chosen) * (h + lab + 4)), (24, 24, 28))
        d = ImageDraw.Draw(sheet)
        d.text((6, 5), f"{title} — esquerda: baseline · meio: mod · direita: diferença (magenta)", fill=(240, 240, 240), font=_font(14))
        for r, f in enumerate(chosen):
            y = 26 + r * (h + lab + 4)
            p = pct[common.index(f)]
            for c, (img, txt) in enumerate(((A[f], f"f{f} baseline"), (B[f], f"f{f} mod"), (overlays[f], f"diff {p:.1f}%"))):
                x = c * (w + 4)
                sheet.paste(Image.fromarray(img), (x, y + lab))
                d.text((x + 3, y + 2), txt, fill=(255, 230, 120), font=font)
        sp = out_dir / "compare.png"
        sheet.save(sp)
        result["compare_sheet"] = rel(sp)
        # curva de divergência
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 2.2))
        ax.plot(common, pct, color="#a142f4", lw=1.2)
        ax.set_xlabel("frame")
        ax.set_ylabel("% px ≠")
        ax.set_title(f"{title} — divergência visual por frame", fontsize=9)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        dp = out_dir / "divergence.png"
        fig.savefig(dp, dpi=90)
        plt.close(fig)
        result["divergence_plot"] = rel(dp)
    if mod_trace:
        tp = trace_plot(mod_trace, out_dir / "trace_compare.png", f"{title} — RAM: mod (vermelho) × baseline (cinza)",
                        baseline=base_trace)
        result["trace_plot"] = rel(tp)
        stats = {}
        for k, v in mod_trace.items():
            if k in ("frame", "input"):
                continue
            mv = np.asarray(v)
            entry = {"mod": {"min": int(mv.min()), "max": int(mv.max()), "first": int(mv[0]), "last": int(mv[-1])}}
            if base_trace and k in base_trace:
                bv = np.asarray(base_trace[k])
                entry["baseline"] = {"min": int(bv.min()), "max": int(bv.max()), "first": int(bv[0]), "last": int(bv[-1])}
                n = min(len(bv), len(mv))
                diff = np.nonzero(bv[:n] != mv[:n])[0]
                entry["first_diff_frame"] = int(diff[0]) if diff.size else None
            stats[k] = entry
        result["trace_stats"] = stats
    write_json(out_dir / "compare.json", result)
    return result
