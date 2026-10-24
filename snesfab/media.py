"""Frames, vídeo e folhas de contato.

- Runs do emulador: frames.rgb (RGB24 cru, 256x239 no MesenCE) → PNGs 256x224 (corte de overscan
  igual ao do Mesen: 7 linhas em cima, 8 em baixo), MP4 (ffmpeg, 2x nearest) e folhas de contato.
- Mídia gravada pelo usuário (mp4/mkv/webm/mov/gif ou pasta de imagens): ffprobe, extração
  uniforme + por mudança de cena, curva de movimento e folhas de contato com timestamps.
O agente analisa as folhas (imagens) com a ferramenta de leitura de imagens.
"""

from __future__ import annotations

import csv
import functools
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .paths import toolchain
from .util import FabError, rel, run, write_json

VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".gif", ".m4v", ".wmv", ".flv", ".ts"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


@functools.lru_cache(maxsize=8)
def _font(size: int = 13):
    """DejaVu Sans (vem com o matplotlib) — tem os acentos e travessões que a fonte bitmap do Pillow não tem."""
    try:
        from matplotlib import font_manager
        return ImageFont.truetype(font_manager.findfont("DejaVu Sans"), size)
    except Exception:  # noqa: BLE001
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()


def crop_overscan(img: np.ndarray) -> np.ndarray:
    h = img.shape[0]
    if h == 239:
        return img[7:231]
    if h == 478:
        return img[14:462]
    return img


@dataclass
class RunFrames:
    frames: list[int]           # nº do frame do cenário de cada captura
    images: list[np.ndarray]    # HxWx3 uint8 (já cortadas)
    every: int

    def __len__(self):
        return len(self.frames)

    def by_frame(self) -> dict[int, np.ndarray]:
        return dict(zip(self.frames, self.images))


def load_run_frames(run_dir: Path, crop: bool = True) -> RunFrames:
    run_dir = Path(run_dir)
    idx_path, raw_path = run_dir / "frames_index.csv", run_dir / "frames.rgb"
    if not idx_path.exists() or not raw_path.exists():
        # run já pós-processado: lê os PNGs
        pngs = sorted((run_dir / "frames").glob("f*.png"))
        if not pngs:
            raise FabError(f"sem frames capturados em {run_dir}", "rode o cenário com captura (capture.every > 0)")
        frames = [int(p.stem[1:]) for p in pngs]
        imgs = [np.asarray(Image.open(p).convert("RGB")) for p in pngs]
        every = frames[1] - frames[0] if len(frames) > 1 else 1
        return RunFrames(frames, imgs, every)
    raw = np.fromfile(raw_path, dtype=np.uint8)
    frames, images = [], []
    with open(idx_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            w, h, off = int(row["width"]), int(row["height"]), int(row["offset"])
            img = raw[off:off + w * h * 3].reshape(h, w, 3)
            frames.append(int(row["frame"]))
            images.append(crop_overscan(img) if crop else img)
    every = frames[1] - frames[0] if len(frames) > 1 else 1
    return RunFrames(frames, images, every)


def _normalize_sizes(images: list[np.ndarray]) -> list[np.ndarray]:
    """Iguala tamanhos (ex.: modo hi-res 512 px) por nearest-neighbour para o maior."""
    if not images:
        return images
    H = max(i.shape[0] for i in images)
    W = max(i.shape[1] for i in images)
    out = []
    for i in images:
        if i.shape[:2] != (H, W):
            i = np.asarray(Image.fromarray(i).resize((W, H), Image.NEAREST))
        out.append(i)
    return out


def write_pngs(rf: RunFrames, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for fno, img in zip(rf.frames, rf.images):
        p = out_dir / f"f{fno:05d}.png"
        Image.fromarray(img).save(p, optimize=False, compress_level=6)
        paths.append(p)
    return paths


def write_video(images: list[np.ndarray], out_path: Path, fps: float, scale: int = 2) -> Path:
    tc = toolchain()
    tc.require("ffmpeg")
    images = _normalize_sizes(images)
    if not images:
        raise FabError("sem frames para o vídeo")
    h, w = images[0].shape[:2]
    data = b"".join(np.ascontiguousarray(i).tobytes() for i in images)
    vf = f"scale={w * scale}:{h * scale}:flags=neighbor"
    cmd = [tc.ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
           "-r", f"{fps:g}", "-i", "-", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]
    proc = run(cmd, input_bytes=data, timeout=300)
    if proc.returncode != 0:
        raise FabError(f"ffmpeg falhou a gerar {out_path.name}: {proc.stderr[-800:]}")
    return out_path


def pick_indices(n: int, k: int) -> list[int]:
    if n <= k:
        return list(range(n))
    return sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})


def contact_sheet(images: list[np.ndarray], labels: list[str], cols: int = 4, scale: int = 1,
                  title: str | None = None, max_width: int = 1100) -> Image.Image:
    images = _normalize_sizes(images)
    if not images:
        raise FabError("sem imagens para a folha de contato")
    h, w = images[0].shape[:2]
    cols = max(1, min(cols, len(images)))
    tw, th = w * scale, h * scale
    if tw * cols > max_width:          # fotos grandes (vídeos do usuário): reduz
        f = max_width / (tw * cols)
        tw, th = int(tw * f), int(th * f)
    font = _font(13)
    label_h = 18
    title_h = 24 if title else 0
    rows = math.ceil(len(images) / cols)
    sheet = Image.new("RGB", (cols * tw + (cols - 1) * 4, title_h + rows * (th + label_h) + (rows - 1) * 4), (24, 24, 28))
    draw = ImageDraw.Draw(sheet)
    if title:
        draw.text((6, 4), title, fill=(240, 240, 240), font=_font(15))
    for i, (img, lab) in enumerate(zip(images, labels)):
        r, c = divmod(i, cols)
        x = c * (tw + 4)
        y = title_h + r * (th + label_h + 4)
        tile = Image.fromarray(img).resize((tw, th), Image.NEAREST if scale >= 1 and tw >= w else Image.BILINEAR)
        sheet.paste(tile, (x, y + label_h))
        draw.text((x + 3, y + 2), lab, fill=(255, 230, 120), font=font)
    return sheet


def run_sheets(rf: RunFrames, out_dir: Path, title: str, per_sheet: int = 16, fps: float = 60.0) -> list[Path]:
    """Folha geral (frames espaçados) — devolve os caminhos."""
    idx = pick_indices(len(rf), per_sheet)
    imgs = [rf.images[i] for i in idx]
    labels = [f"f{rf.frames[i]}  {rf.frames[i] / fps:.2f}s" for i in idx]
    p = out_dir / "sheet.png"
    contact_sheet(imgs, labels, cols=4, title=title).save(p)
    return [p]


def postprocess_run(run_dir: Path, title: str = "", keep_raw: bool = False, video: bool = True) -> dict:
    """frames.rgb → frames/*.png + video.mp4 + sheet.png. Devolve um resumo com os caminhos."""
    run_dir = Path(run_dir)
    if not (run_dir / "frames_index.csv").exists():
        return {"frames": 0}
    rf = load_run_frames(run_dir)
    if len(rf) == 0:
        return {"frames": 0}
    write_pngs(rf, run_dir / "frames")
    out = {"frames": len(rf), "every": rf.every, "size": f"{rf.images[0].shape[1]}x{rf.images[0].shape[0]}",
           "frames_dir": rel(run_dir / "frames")}
    if video:
        fps = 60.0 / max(rf.every, 1)
        out["video"] = rel(write_video(rf.images, run_dir / "video.mp4", fps))
    out["sheets"] = [rel(p) for p in run_sheets(rf, run_dir, title or run_dir.name)]
    if not keep_raw:
        (run_dir / "frames.rgb").unlink(missing_ok=True)
        (run_dir / "frames_index.csv").unlink(missing_ok=True)
    write_json(run_dir / "media.json", out)
    return out


# ── gráficos de traços de RAM ─────────────────────────────────────────────────

def trace_plot(series: dict[str, list[int]], out_path: Path, title: str,
               baseline: dict[str, list[int]] | None = None, names: list[str] | None = None) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = names or [k for k in series if k not in ("frame", "input")]
    if not names:
        names = []
    n = len(names) + 1
    fig, axes = plt.subplots(n, 1, figsize=(10, 1.9 * n + 0.6), sharex=True, squeeze=False)
    frames = series.get("frame", list(range(len(next(iter(series.values()), [])))))
    for ax, name in zip(axes[:, 0], names):
        if baseline and name in baseline:
            ax.plot(baseline.get("frame", frames), baseline[name], color="#9aa0a6", lw=1.4, label="baseline")
        ax.plot(frames, series[name], color="#d93025", lw=1.4, label="mod" if baseline else name)
        ax.set_ylabel(name, rotation=0, ha="right", va="center")
        ax.grid(alpha=0.3)
        if baseline:
            ax.legend(loc="upper right", fontsize=7)
    ax = axes[-1, 0]
    inp = series.get("input", [0] * len(frames))
    bits = [("B", 0x8000), ("Y", 0x4000), ("Sel", 0x2000), ("St", 0x1000), ("U", 0x0800), ("D", 0x0400),
            ("L", 0x0200), ("R", 0x0100), ("A", 0x0080), ("X", 0x0040), ("Lt", 0x0020), ("Rt", 0x0010)]
    for row, (bn, bit) in enumerate(bits):
        xs = [f for f, m in zip(frames, inp) if m & bit]
        if xs:
            ax.scatter(xs, [row] * len(xs), s=6, marker="s", color="#1a73e8")
    ax.set_yticks(range(len(bits)))
    ax.set_yticklabels([b[0] for b in bits], fontsize=6)
    ax.set_ylabel("input", rotation=0, ha="right", va="center")
    ax.set_xlabel("frame")
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path, dpi=90)
    plt.close(fig)
    return out_path


# ── mídia do usuário (vídeo ou imagens) ────────────────────────────────────

def ffprobe(path: Path) -> dict:
    tc = toolchain()
    tc.require("ffprobe")
    proc = run([tc.ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path], timeout=60)
    if proc.returncode != 0:
        raise FabError(f"ffprobe não conseguiu ler {path.name}: {proc.stderr[-400:]}")
    data = json.loads(proc.stdout or "{}")
    vs = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not vs:
        raise FabError(f"{path.name} não tem stream de vídeo")
    num, _, den = (vs.get("avg_frame_rate") or vs.get("r_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    duration = float(data.get("format", {}).get("duration") or vs.get("duration") or 0)
    return {"width": int(vs["width"]), "height": int(vs["height"]), "fps": round(fps, 3),
            "duration": round(duration, 3), "codec": vs.get("codec_name"),
            "frames": int(vs.get("nb_frames") or round(duration * fps))}


def _grab_frame_png(path: Path, t: float, dest: Path, max_w: int = 640) -> bool:
    tc = toolchain()
    proc = run([tc.ffmpeg, "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
                "-vf", f"scale='min({max_w},iw)':-2", dest], timeout=60)
    return proc.returncode == 0 and dest.exists()


def scene_times(path: Path, threshold: float = 0.25, limit: int = 64) -> list[float]:
    tc = toolchain()
    proc = run([tc.ffmpeg, "-hide_banner", "-i", path, "-vf", f"select='gt(scene,{threshold})',showinfo",
                "-f", "null", "-"], timeout=600)
    times = [float(m.group(1)) for m in re.finditer(r"pts_time:([0-9.]+)", proc.stderr or "")]
    return times[:limit]


def motion_curve(path: Path, sample_fps: float = 6.0) -> tuple[list[float], list[float]]:
    """Diferença média entre amostras consecutivas (0..255) — picos = ação/cortes."""
    tc = toolchain()
    w, h = 96, 72
    import subprocess
    proc = subprocess.run([str(tc.ffmpeg), "-loglevel", "error", "-i", str(path), "-vf",
                           f"fps={sample_fps},scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
    buf = np.frombuffer(proc.stdout, dtype=np.uint8)
    n = buf.size // (w * h)
    if n < 2:
        return [], []
    fr = buf[: n * w * h].reshape(n, h, w).astype(np.int16)
    diffs = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    times = [(i + 1) / sample_fps for i in range(len(diffs))]
    return times, [float(d) for d in diffs]


def analyze_media(path: Path, out_dir: Path, n_uniform: int = 16, scene_threshold: float = 0.25,
                  at: list[float] | None = None) -> dict:
    """Prepara um vídeo/imagem/pasta de imagens para análise visual pelo agente."""
    path = Path(path)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    summary: dict = {"source": str(path), "out_dir": rel(out_dir)}

    if path.is_dir() or path.suffix.lower() in IMAGE_EXT:
        files = sorted([p for p in path.iterdir() if p.suffix.lower() in IMAGE_EXT]) if path.is_dir() else [path]
        if not files:
            raise FabError(f"sem imagens em {path}")
        imgs = [np.asarray(Image.open(p).convert("RGB")) for p in files]
        labels = [p.name[:28] for p in files]
        sheets = []
        for k in range(0, len(imgs), 16):
            sp = out_dir / f"sheet_{k // 16 + 1:02d}.png"
            contact_sheet(imgs[k:k + 16], labels[k:k + 16], cols=4, title=f"{path.name} ({k + 1}-{min(k + 16, len(imgs))}/{len(imgs)})").save(sp)
            sheets.append(rel(sp))
        summary.update({"kind": "images", "count": len(files), "sheets": sheets,
                        "sizes": sorted({f"{i.shape[1]}x{i.shape[0]}" for i in imgs})})
        write_json(out_dir / "summary.json", summary)
        return summary

    if path.suffix.lower() not in VIDEO_EXT:
        raise FabError(f"formato não suportado: {path.suffix}", f"use um de {sorted(VIDEO_EXT | IMAGE_EXT)}")
    meta = ffprobe(path)
    summary.update({"kind": "video", **meta})
    dur = max(meta["duration"], 0.04)
    uniform = [round(dur * (i + 0.5) / n_uniform, 3) for i in range(n_uniform)]
    scenes = [t for t in scene_times(path, scene_threshold) if t < dur]
    picked = sorted(set(uniform) | set(round(t, 3) for t in scenes) | set(at or []))
    extracted: list[tuple[float, Path]] = []
    for t in picked:
        dest = frames_dir / f"t{int(t * 1000):08d}ms.png"
        if _grab_frame_png(path, t, dest):
            extracted.append((t, dest))
    if not extracted:
        raise FabError(f"não consegui extrair frames de {path.name}")

    def sheet_for(items, name, title):
        imgs = [np.asarray(Image.open(p).convert("RGB")) for _, p in items]
        labels = [f"{t:7.2f}s" + ("  ✂" if any(abs(t - s) < 1e-3 for s in scenes) else "") for t, _ in items]
        sp = out_dir / name
        contact_sheet(imgs, labels, cols=4, title=title).save(sp)
        return rel(sp)

    sheets = [sheet_for([e for e in extracted if e[0] in uniform][:16], "sheet_uniform.png",
                        f"{path.name} — {n_uniform} frames uniformes ({dur:.1f}s)")]
    scene_items = [e for e in extracted if any(abs(e[0] - s) < 1e-3 for s in scenes)]
    for k in range(0, len(scene_items), 16):
        sheets.append(sheet_for(scene_items[k:k + 16], f"sheet_scenes_{k // 16 + 1:02d}.png",
                                f"{path.name} — mudanças de cena (limiar {scene_threshold})"))
    times, diffs = motion_curve(path)
    if diffs:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 2.4))
        ax.plot(times, diffs, color="#d93025", lw=1)
        for s in scenes:
            ax.axvline(s, color="#1a73e8", alpha=0.35, lw=0.8)
        ax.set_xlabel("s")
        ax.set_ylabel("movimento")
        ax.set_title(f"{path.name} — curva de movimento (azul = cortes de cena)", fontsize=9)
        fig.tight_layout()
        fig.savefig(out_dir / "motion.png", dpi=90)
        plt.close(fig)
        peaks = sorted(range(len(diffs)), key=lambda i: diffs[i], reverse=True)[:8]
        summary["motion_peaks_s"] = sorted(round(times[i], 2) for i in peaks)
        summary["motion_png"] = rel(out_dir / "motion.png")
    summary["scene_changes_s"] = [round(s, 3) for s in scenes]
    summary["frames"] = [{"t": t, "png": rel(p)} for t, p in extracted]
    summary["sheets"] = sheets
    write_json(out_dir / "summary.json", summary)
    return summary
