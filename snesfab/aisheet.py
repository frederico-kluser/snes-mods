"""Sheets de sprites para edição por IA (Nano Banana / Gemini image editing) — round-trip.

O modelo de imagem não trabalha a 1 px: por isso o EXPORTO expande cada píxel num bloco N×N de cor
sólida ("quadrados de cor"), grava o mapa JSON de coordenadas (onde está cada pose e cada tile na
imagem gerada) e gera o prompt. O IMPORTO recebe a imagem devolvida (mesmo aspect ratio, tamanho
livre), re-quantiza cada bloco para os índices da paleta original — voto maioritário ponderado pelo
centro do bloco — limpa os "quadrados que não ficaram corretos" (blocos sujos: voto contestado) e gera
o plano de tiles pronto para o pipeline `fab paint` / `fab gfx override` transpor para o jogo.

Decisões de design (evidência em pesquisas/2026-10-28-…-snes-16-cores-4b.md):
- bloco N×N por nearest-neighbor, 8–16×, folha ≤ 1024 px para caber no bucket 1K do Gemini [S14][S16][S17];
- fundo = cor FORA da paleta (transparência do índice 0); o modelo tende a destruir alfa [S16][S22];
- re-quantização por voto maioritário por bloco + snap à paleta (pixfix) [S30]; pureza do voto decide
  se o bloco está "sujo" (nenhum limiar ΔE publicado — usa-se fração de voto) [S30][S35];
- amostrar o CENTRO do bloco tolera deslocamentos/deformações suaves do modelo [S42];
- mapa por coordenadas: rect (x,y,w,h) em píxeis + id estável + célula (grelha) — interseção dos
  formatos Aseprite/TexturePacker/Tiled/Godot [S59][S61][S63][S67];
- edição de píxeis que eram transparentes só é transponível onde há um tile dono sem ambiguidade
  (senão seria preciso tiles/OAM novos: reportado como `fora_do_alvo`).
"""

from __future__ import annotations

import base64
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import ppu
from .media import _font
from .util import FabError, now_iso, rel, write_json

# folhas expandidas grandes são normais aqui (o dono prefere quadrados maiores): sem teto de "decompression bomb"
Image.MAX_IMAGE_PIXELS = max(Image.MAX_IMAGE_PIXELS or 0, 2_000_000_000)

BG_DARK = (18, 18, 24)
TEXT = (235, 235, 235)
TEXT_DIM = (160, 160, 170)
FUNDO_PADRAO = "#FF00FF"
DIRTY_THRESHOLD = 0.70          # fração mínima de voto para o bloco não ser "sujo"
NEAR_FUNDO = 40                 # distância RGB máxima ao fundo para contar como transparente


# ── estruturas ────────────────────────────────────────────────────────────────

@dataclass
class TileInstance:
    """Bloco 8×8 de um tile dentro de uma pose: rect no canvas + flips (como o OAM desenha)."""
    hash: str
    x: int
    y: int
    hflip: bool = False
    vflip: bool = False
    vram: int = -1
    oam: int = 999
    raw: bytes = b""

    def px_map(self, x: int, y: int) -> int:
        """Píxel dentro do tile (0-63, já com o espelhamento) para um píxel do canvas."""
        dx, dy = x - self.x, y - self.y
        tx = 7 - dx if self.hflip else dx
        ty = 7 - dy if self.vflip else dy
        return ty * 8 + tx

    def covers(self, x: int, y: int) -> bool:
        return self.x <= x < self.x + 8 and self.y <= y < self.y + 8

    def to_dict(self) -> dict:
        return {"hash": self.hash, "caixa": [self.x, self.y, 8, 8], "hflip": self.hflip, "vflip": self.vflip,
                "vram": f"${self.vram:04X}" if self.vram >= 0 else None, "oam": self.oam}

    @staticmethod
    def from_dict(d: dict) -> "TileInstance":
        vram = d.get("vram")
        return TileInstance(d["hash"], int(d["caixa"][0]), int(d["caixa"][1]), bool(d.get("hflip")),
                            bool(d.get("vflip")), int(vram.lstrip("$"), 16) if isinstance(vram, str) else -1,
                            int(d.get("oam", 999)))


@dataclass
class Pose:
    """Uma pose do personagem: canvas de píxeis (índices 0-15, 0 = transparente) + tiles que a desenham."""
    id: str
    frame: int
    capture: str
    indices: np.ndarray                      # h×w uint8
    tiles: list[TileInstance]
    origem_ecra: tuple[int, int] = (0, 0)    # onde o canvas está na tela (para referência)
    vezes: int = 1

    @property
    def w(self) -> int:
        return int(self.indices.shape[1])

    @property
    def h(self) -> int:
        return int(self.indices.shape[0])

    def key(self) -> bytes:
        parts = tuple(sorted((t.hash, t.x, t.y, t.hflip, t.vflip) for t in self.tiles))
        return self.indices.tobytes() + repr(parts).encode()


# ── RLE para os índices das poses no map.json ─────────────────────────────────

def rle_encode(arr: np.ndarray) -> list[list[int]]:
    flat = np.asarray(arr, dtype=np.uint8).ravel()
    out: list[list[int]] = []
    if not len(flat):
        return out
    start = 0
    for i in range(1, len(flat) + 1):
        if i == len(flat) or flat[i] != flat[start]:
            out.append([int(flat[start]), i - start])
            start = i
    return out


def rle_decode(runs: list[list[int]], w: int, h: int) -> np.ndarray:
    flat = np.empty(w * h, np.uint8)
    pos = 0
    for v, n in runs:
        flat[pos:pos + n] = v
        pos += n
    if pos != w * h:
        raise FabError(f"RLE cobre {pos} píxeis mas o canvas tem {w * h}", "map.json corrompido")
    return flat.reshape(h, w)


# ── recolha de poses a partir de capturas ─────────────────────────────────────

def _entry_instances(e, vram: bytes, base_words: int, offset_words: int) -> list[TileInstance]:
    """Sub-tiles 8×8 de uma entrada do OAM, como o render do PPU os desenha (flips aplicados)."""
    out = []
    for cy in range(e.height // 8):
        trow = (e.height // 8 - 1 - cy) if e.vflip else cy
        for cx in range(e.width // 8):
            tcol = (e.width // 8 - 1 - cx) if e.hflip else cx
            t_low = (((e.tile >> 4) + trow) & 0x0F) << 4 | (((e.tile & 0x0F) + tcol) & 0x0F)
            from .ppu import tile_word_address
            waddr = tile_word_address(base_words, offset_words, (e.tile & 0x100) | t_low)
            raw = bytes(vram[waddr * 2:waddr * 2 + 32])
            out.append(TileInstance(_hash_tile(raw), e.x + cx * 8, e.y + cy * 8, e.hflip, e.vflip, waddr * 2, e.index,
                                    raw))
    return out


def _hash_tile(raw: bytes) -> str:
    import hashlib
    return hashlib.sha1(bytes(raw)).hexdigest()[:12]


def entry_runs(ois: list[int], entries: dict) -> list[list[int]]:
    """Corridas contíguas de índice do OAM — o motor de sprites escreve cada objeto numa corrida só,
    então a corrida que contém o alvo separa-o de efeitos/parques de outras corridas."""
    idxs = sorted(int(i) for i in ois)
    runs: list[list[int]] = []
    cur: list[int] = []
    for i in idxs:
        if cur and i != cur[-1] + 1:
            runs.append(cur)
            cur = []
        cur.append(i)
    if cur:
        runs.append(cur)
    return runs


def _lcs_pairs(a: list[int], b: list[int]) -> list[tuple[int, int]]:  # pragma: no cover - utilitário de depuração
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = 1 + dp[i + 1][j + 1] if a[i] == b[j] else max(dp[i + 1][j], dp[i][j + 1])
    out: list[tuple[int, int]] = []
    i = j = 0
    while i < n and j < m:
        if a[i] == b[j]:
            out.append((i, j))
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return out


def filter_entries_by_cels(ois: list[int], entries: dict, lists) -> tuple[list[int], int]:
    """Restringe as entradas às que a LISTA DE CELS do motor desenha (o personagem dono da pose). A lista
    certa escolhe-se pelo MULTISET dos tiles 8-bit contra TODAS as listas da captura (o motor segura a
    pose e pode não reler a lista no frame capturado), com bónus para correspondência exata; entradas
    que não consomem uma cel da lista são EFEITO/lixo com a mesma paleta e caem. Sem lista minimamente
    batida, devolve tudo (sem filtro)."""
    from collections import Counter
    if not lists or not ois:
        return ois, 0
    ents = sorted((entries[int(i)] for i in ois), key=lambda e: e.index)
    ent_t8 = Counter(e.tile & 0xFF for e in ents)
    best_cl, best_score = None, -1
    for cl in lists:
        cl_t8 = Counter(c[2] & 0xFF for c in cl.cels)
        inter = sum((ent_t8 & cl_t8).values())
        score = inter + (1000 if inter == len(ents) == len(cl.cels)
                         else 500 if inter == len(ents) else 0)
        if score > best_score:
            best_cl, best_score = cl, score
    if best_cl is None or best_score < max(2, len(ents) // 2):
        return ois, 0
    want = Counter(c[2] & 0xFF for c in best_cl.cels)
    keep: list[int] = []
    for e in ents:
        t8 = e.tile & 0xFF
        if want[t8] > 0:
            want[t8] -= 1
            keep.append(e.index)
    return (keep or ois), len(ois) - len(keep)


def collect_pose(fd, target, label: str = "", lists=None) -> tuple[Pose | None, dict]:
    """Uma pose do alvo (SpriteObject) num frame: canvas + índices + tiles donos. None se o alvo não aparecer.

    O desenho vem dos TILES das entradas do OAM da paleta do alvo (não só dos píxeis visíveis): o que
    outro sprite cobriu — ou a perna que ficou desligada do corpo na tela — continua completo aqui."""
    from .sprites import color_index_map
    snap = fd.snap
    if snap is None:
        return None, {"frame": fd.frame, "erro": "frame sem snapshot do PPU"}
    lay = fd.layer()
    m = snap.meta
    base_words = int(m.get("oamBaseAddress") or 0)
    offset_words = int(m.get("oamAddressOffset") or 0x1000)
    first = ((int(m.get("internalOamAddress") or 0) >> 2) & 0x7F) if m.get("enableOamPriority") else 0
    entries = {e.index: e for e in lay.entries}
    # entradas do alvo: a CORRIDA contígua de entradas da paleta do alvo que contém as suas (o motor
    # escreve cada objeto numa corrida só — fica de fora o lixo PARCADO fora do ecrã e efeitos de
    # outras corridas). Depois, filtro pela lista de cels do motor.
    H, W = fd.real.shape[0], ppu.SCREEN_W
    pal = [e for e in lay.entries if e.palette == target.palette
           and not (e.x + e.width <= 0 or e.x >= W or e.y + e.height <= 0 or e.y >= H)]
    alvo = set(int(i) for i in target.oam)
    runs = entry_runs([e.index for e in pal], entries)
    ois = sorted({i for r in runs if alvo & set(r) for i in r}) or sorted(alvo)
    ois, excl = filter_entries_by_cels(ois, entries, lists)
    instances: list[TileInstance] = []
    for oi in ois:
        e = entries.get(int(oi))
        if e is not None:
            instances += _entry_instances(e, snap.vram, base_words, offset_words)
    if not instances:
        return None, {"frame": fd.frame, "erro": "sem tiles donos"}
    x0 = min(i.x for i in instances)
    y0 = min(i.y for i in instances)
    x1 = max(i.x + 8 for i in instances)
    y1 = max(i.y + 8 for i in instances)
    w, h = x1 - x0, y1 - y0
    if w * h > 40000:
        return None, {"frame": fd.frame, "erro": f"canvas gigante {w}x{h} (sprites dispersos?)"}
    for i in instances:
        i.x -= x0
        i.y -= y0
    # composição do desenho completo: de trás para a frente (o OAM de menor índice fica por cima)
    canvas = np.zeros((h, w), np.uint8)
    for inst in sorted(instances, key=lambda i: -((i.oam - first) & 0x7F)):
        arr = ppu.decode_4bpp(inst.raw)
        for yy in range(inst.y, inst.y + 8):
            for xx in range(inst.x, inst.x + 8):
                if 0 <= xx < w and 0 <= yy < h:
                    tpx = inst.px_map(xx, yy)
                    v = int(arr[tpx // 8, tpx % 8])
                    if v:
                        canvas[yy, xx] = v
    # validação: onde uma entrada MANTIDA desenha píxeis visíveis, o composto tem de dar o mesmo índice.
    # (píxeis de entradas descartadas são efeitos encostados ao corpo — não pertencem à pose)
    col = color_index_map(fd, target)
    mism = 0
    efeitos = 0
    mantidos = {int(i) for i in ois}
    sy, sx = np.nonzero(col >= 0)
    for yy, xx in zip(sy, sx):
        if int(lay.oam[yy, xx]) not in mantidos:
            efeitos += 1
            continue
        cy, cx = int(yy) - y0, int(xx) - x0
        if 0 <= cy < h and 0 <= cx < w and int(canvas[cy, cx]) != int(col[yy, xx]):
            mism += 1
    pose = Pose(f"f{fd.frame:05d}", fd.frame, label, canvas, sorted(instances, key=lambda i: i.oam), (x0, y0))
    return pose, {"frame": fd.frame, "canvas": [w, h], "pixeis": int((canvas > 0).sum()),
                  "tiles": len(instances), "entradas": len(ois), "excluidas_pela_lista": excl,
                  "pixeis_de_efeitos_fora_da_pose": efeitos, "mismatch_dono": mism}


def collect_poses(captures: list[Path], palette: int | None = None, object_no: int | None = None,
                  frames: list[int] | None = None, engine=None, rom=None) -> tuple[list[Pose], list[dict], dict]:
    """Varre capturas e junta poses únicas do alvo (maior objeto com a paleta OAM dada, ou nº de objeto).
    Com `engine` (CelEngine) + `rom`, cada frame é filtrado pela lista de cels do motor (só o personagem —
    efeitos com a mesma paleta ficam de fora)."""
    from .cels import lists_by_frame
    from .sprites import find_objects, load_capture
    poses: list[Pose] = []
    seen: dict[bytes, int] = {}
    notes: list[dict] = []
    palette_info: dict = {}
    for cap_dir in captures:
        cap = load_capture(Path(cap_dir))
        label = rel(Path(cap_dir))
        by_frame = lists_by_frame(Path(cap_dir), rom, engine) if (engine and rom) else {}
        todas: dict[int, object] = {}
        for ls in by_frame.values():
            for cl in ls:
                todas.setdefault(cl.pc, cl)
        all_lists = list(todas.values())          # o motor segura a pose: comparar contra TODAS as listas
        for f in sorted(cap.frames):
            if frames and f not in frames:
                continue
            fd = cap.frames[f]
            objs = find_objects(fd)
            cand = [o for o in objs if (palette is None or o.palette == palette)
                    and (object_no is None or o.number == object_no)]
            if not cand:
                notes.append({"frame": f, "erro": "alvo ausente"})
                continue
            target = cand[0]
            if palette_info.get("cgram") is None:
                colors = fd.colors
                base = 16 * target.cgram_palette
                palette_info = {"cgram": target.cgram_palette, "oam": target.palette,
                                "cores": [int(colors[base + i]) for i in range(16)]}
            pose, note = collect_pose(fd, target, label, all_lists)
            note["captura"] = label
            if pose is None:
                notes.append(note)
                continue
            k = pose.key()
            if k in seen:
                poses[seen[k]].vezes += 1
                note["duplicada_de"] = poses[seen[k]].id
            else:
                seen[k] = len(poses)
                pose.id = f"p{len(poses) + 1:02d}-f{f:05d}"
                poses.append(pose)
            notes.append(note)
    return poses, notes, palette_info


# ── export ────────────────────────────────────────────────────────────────────

def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def fundo_ideal(cores_bgr: list[int]) -> str:
    """Cor de fundo (chroma) CALCULADA: maximiza a distância mínima às 15 cores da paleta — assim o fundo
    contrasta com o personagem (o modelo não confunde; o keying do índice 0 é robusto)."""
    pal = np.array([ppu.bgr555_to_rgb(v) for v in cores_bgr[1:16]], dtype=np.int32)
    g = np.stack(np.mgrid[0:256:8, 0:256:8, 0:256:8], axis=-1).reshape(-1, 3)   # 32768 candidatos
    d = np.sqrt(((g[:, None, :].astype(np.int32) - pal[None, :, :]) ** 2).sum(axis=2))
    best = g[int(d.min(axis=1).argmax())]
    return _hex((int(best[0]), int(best[1]), int(best[2])))


def export_sheet(poses: list[Pose], cores_bgr: list[int], out_dir: Path, name: str, *, bloco: int | None = None,
                 max_px: int = 1024, cols: int | None = None, gap: int = 1, fundo: str = "auto",
                 jogo: str = "", mudanca: str = "") -> dict:
    """Gera sheet.png (expandida), map.json (mapa de coordenadas), prompt.md e report.md.
    `fundo="auto"` (padrão) CALCULA a cor de fundo com máximo contraste à paleta."""
    if not poses:
        raise FabError("nenhuma pose recolhida", "confira --palette/--object e as capturas")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if fundo == "auto":
        fundo = fundo_ideal(cores_bgr)
    cw = max(p.w for p in poses)
    ch = max(p.h for p in poses)
    n = len(poses)
    cols = cols or max(1, math.ceil(math.sqrt(n * ch / max(cw, 1))))
    rows = math.ceil(n / cols)
    W1, H1 = gap + cols * (cw + gap), gap + rows * (ch + gap)      # folha a 1 px por píxel
    if bloco is None:
        bloco = min(max_px // W1, max_px // H1, 16)
    if bloco < 3:
        raise FabError(f"folha {W1}x{H1} não cabe em {max_px}px nem com bloco 3",
                       "reduza poses (--frames), --cols maior, ou --max 2048 (Nano Banana Pro)")
    # folha 1 px por píxel (referência) e folha expandida (para o modelo)
    ref = np.zeros((H1, W1, 3), np.uint8)
    fundo_rgb = tuple(int(fundo.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    ref[:, :] = fundo_rgb
    cores_rgb = [ppu.bgr555_to_rgb(v) for v in cores_bgr]
    colisao = [i for i in range(1, 16) if tuple(cores_rgb[i]) == fundo_rgb]
    if colisao:
        raise FabError(f"o fundo {fundo} coincide com os índices {colisao} da paleta",
                       "escolha --fundo fora da paleta (ex.: #FF00FF) ou mude a paleta do jogo")
    cells = []
    for idx, p in enumerate(poses):
        r, c = divmod(idx, cols)
        x0, y0 = gap + c * (cw + gap), gap + r * (ch + gap)
        sub = np.zeros((p.h, p.w, 3), np.uint8)
        sub[:, :] = fundo_rgb
        for i in range(1, 16):
            sub[p.indices == i] = cores_rgb[i]
        ref[y0:y0 + p.h, x0:x0 + p.w] = sub
        cells.append({"pose": p, "x0": x0, "y0": y0})
    big = Image.fromarray(ref).resize((W1 * bloco, H1 * bloco), Image.NEAREST)
    big.save(out_dir / "sheet.png")
    Image.fromarray(ref).save(out_dir / "sheet-1px.png")
    # mapa JSON — o "mapa na memória" para transpor a imagem devolvida
    mapa = {
        "versao": 1, "ferramenta": "fab ai export", "gerado": now_iso(), "jogo": jogo, "nome": name,
        "imagem": {"arquivo": "sheet.png", "largura": W1 * bloco, "altura": H1 * bloco, "bloco": bloco,
                   "gap_px": gap, "fundo": fundo, "referencia_1px": "sheet-1px.png"},
        "paleta": {"cores": [{"indice": i, "cor": _hex(cores_rgb[i]), "bgr555": f"${cores_bgr[i] & 0x7FFF:04X}"}
                             for i in range(1, 16)], "indice_0": "fundo (transparente)"},
        "grelha": {"colunas": cols, "linhas": rows, "celula": [cw, ch], "total_poses": n},
        "poses": [], "tiles": {},
    }
    for cell in cells:
        p: Pose = cell["pose"]
        mapa["poses"].append({
            "id": p.id, "rotulo": p.id, "frame": p.frame, "captura": p.capture, "vezes": p.vezes,
            "celula": [ (cell["x0"] - gap) // (cw + gap), (cell["y0"] - gap) // (ch + gap) ],
            "caixa_celula_px": [cell["x0"], cell["y0"], cw, ch],
            "caixa_expandida": [cell["x0"] * bloco, cell["y0"] * bloco, cw * bloco, ch * bloco],
            "caixa_conteudo_px": [cell["x0"], cell["y0"], p.w, p.h],
            "canvas": [p.w, p.h], "origem_ecra": list(p.origem_ecra),
            "indices_rle": rle_encode(p.indices),
            "tiles": [t.to_dict() for t in p.tiles],
        })
        for t in p.tiles:
            e = mapa["tiles"].setdefault(t.hash, {"vram": []})
            if t.vram >= 0 and f"${t.vram:04X}" not in e["vram"]:
                e["vram"].append(f"${t.vram:04X}")
    # bytes dos tiles: viajam nas instâncias (o import precisa deles para reconstruir/validar)
    for cell in cells:
        for t in cell["pose"].tiles:
            e = mapa["tiles"].setdefault(t.hash, {"vram": []})
            if t.raw:
                e["bytes"] = bytes(t.raw).hex()
            e.setdefault("bytes", None)
    write_json(out_dir / "map.json", mapa)
    (out_dir / "prompt.md").write_text(_prompt(mapa, name, mudanca), encoding="utf-8", newline="\n")
    (out_dir / "report.md").write_text(_export_report(mapa, name, bloco), encoding="utf-8", newline="\n")
    res = {"dir": rel(out_dir), "sheet": rel(out_dir / "sheet.png"), "map": rel(out_dir / "map.json"),
           "prompt": rel(out_dir / "prompt.md"), "poses": n, "tiles_unicos": len(mapa["tiles"]),
           "folha_1px": [W1, H1], "folha_expandida": [W1 * bloco, H1 * bloco], "bloco": bloco,
           "colunas": cols, "linhas": rows,
           "proximo": ("mande sheet.png + prompt.md ao Nano Banana; quando a imagem voltar: "
                       f"fab ai import --map {rel(out_dir / 'map.json')} --image <nova.png> --out <dir>")}
    return res


def _prompt(mapa: dict, name: str, mudanca: str) -> str:
    im, pal, gr = mapa["imagem"], mapa["paleta"], mapa["grelha"]
    cores = " · ".join(f"#{c['indice']} {c['cor']}" for c in pal["cores"])
    mud = mudanca.strip() or "{{DESCREVA AQUI A MUDANÇA — ex.: redraw the outfit as a futuristic armor}}"
    return f"""# Prompt — edição da tilesheet `{name}` (Nano Banana / Gemini image)

> Envie **`sheet.png`** como imagem de entrada e cole o bloco EN abaixo como prompt.
> Estrutura Lock/Change/Constraints (fal.ai/S54); cláusulas de preservação do guia oficial Google (S51).
> PT logo a seguir, para referência. Depois do registo: `fab ai import --map map.json --image <devolvida>`.

## EN (cole este)

Using the provided image (a sprite sheet of pixel-art characters made of solid color squares), edit it as follows.

CHANGE: {mud}

LOCK (must not change):
- The overall image size ({im['largura']}x{im['altura']}), the aspect ratio and the exact block grid: every pixel of art is one solid {im['bloco']}x{im['bloco']} square block. Do not change the input aspect ratio.
- The layout: {gr['colunas']}x{gr['linhas']} sprite cells of {gr['celula'][0]}x{gr['celula'][1]} art-pixels each; every sprite stays in its own cell, same position and same size.
- The background: the flat {im['fundo']} color between and around cells stays exactly {im['fundo']} (it means transparency).
- The palette: use ONLY these {len(pal['cores'])} colors, as exact flat fills: {cores}. No other colors.

CONSTRAINTS:
- Flat solid colors only: no anti-aliasing, no gradients, no shading between colors, no outlines in new colors.
- Each grid block must end up as ONE uniform solid color from the palette above (or the {im['fundo']} background).
- Keep every unedited sprite pixel identical to the input.
- Return the result at the HIGHEST image size available (use image_size 4K/2K if the API offers it), same aspect ratio as the input.

## PT (referência)

Usando a imagem fornecida (folha de sprites em pixel art feita de quadrados de cor sólida), edite-a assim.

MUDANÇA: {mud}

FIXO (não pode mudar):
- O tamanho da imagem ({im['largura']}x{im['altura']}), o aspect ratio e a grelha exata de blocos: cada píxel de arte é um quadrado sólido de {im['bloco']}x{im['bloco']}. Não altere o aspect ratio da imagem de entrada.
- O layout: células de {gr['colunas']}x{gr['linhas']} de {gr['celula'][0]}x{gr['celula'][1]} píxeis de arte; cada sprite fica na sua célula, mesma posição e tamanho.
- O fundo: a cor chapada {im['fundo']} entre e à volta das células mantém-se exatamente {im['fundo']} (significa transparência).
- A paleta: use APENAS estas {len(pal['cores'])} cores, em pree chapado: {cores}. Nenhuma outra cor.

RETRIÇÕES:
- Cores chapadas só: sem anti-aliasing, sem gradientes, sem sombreado entre cores, sem contornos em cores novas.
- Cada bloco da grelha termina UMA cor sólida uniforme da paleta acima (ou o fundo {im['fundo']}).
- Mantenha idênticos todos os píxeis de sprites que não estão a editar.
- Devolva o resultado no MAIOR tamanho de imagem disponível (image_size 4K/2K se a API oferecer), com o mesmo aspect ratio da entrada.

## Depois (pipeline)

1. `fab ai import --map {mapa.get('nome', 'map.json')}/map.json --image <imagem-devolvida> --out <dir>` → `plan.json` + `check.png` + `report.md`.
2. Confira `check.png` (blocos sujos a vermelho) e o `report.md`.
3. `fab ai import … --mod mods/<id> --name <nome> --evidence "…"` grava o plano no paint.json → `fab build` → `fab paint check` / `fab gfx check`.
"""


def _export_report(mapa: dict, name: str, bloco: int) -> str:
    im, gr = mapa["imagem"], mapa["grelha"]
    L = [f"# Export IA — {name}", "",
         f"- folha expandida: `{im['arquivo']}` {im['largura']}x{im['altura']} (bloco {bloco}x{bloco} por píxel de arte)",
         f"- folha de referência 1 px: `{im['referencia_1px']}`",
         f"- mapa de coordenadas: `map.json` ({gr['total_poses']} poses, {len(mapa['tiles'])} tiles únicos)",
         f"- prompt: `prompt.md` (EN para colar no Nano Banana + PT)",
         f"- grelha: {gr['colunas']}x{gr['linhas']} células de {gr['celula'][0]}x{gr['celula'][1]} px de arte; "
         f"fundo {im['fundo']} = transparência (índice 0)", "",
         "## Poses", "", "| id | frame | célula | caixa expandida | píxeis | tiles | vezes |", "|---|---|---|---|---|---|---|"]
    for p in mapa["poses"]:
        px = sum(n for v, n in p["indices_rle"] if v > 0)
        L.append(f"| {p['id']} | {p['frame']} | {p['celula']} | {p['caixa_expandida']} | {px} | {len(p['tiles'])} | {p['vezes']} |")
    L += ["", "## Como usar", "",
          "1. Envie `sheet.png` + o prompt EN ao Nano Banana (ou Gemini app/API). A imagem devolvida deve ter o "
          "MESMO aspect ratio; o import aceita qualquer tamanho e realinha.",
          "2. `fab ai import --map map.json --image <devolvida> --out <dir>` re-quantiza por bloco (voto maioritário "
          "do centro), limpa os blocos sujos e gera o plano de tiles.",
          "3. Com o plano conferido, aplique num mod (`--mod`) e valide com `fab build` + `fab paint check`.", ""]
    return "\n".join(L)


# ── import ────────────────────────────────────────────────────────────────────

def load_map(path: Path) -> dict:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else json.loads((p / "map.json").read_text(encoding="utf-8"))
    if data.get("versao") != 1:
        raise FabError(f"map.json versao {data.get('versao')!r} não suportada", "gere de novo com `fab ai export`")
    data["_dir"] = str(p.parent if p.is_file() else p)
    return data


def _palette_rgb(mapa: dict) -> tuple[np.ndarray, np.ndarray, tuple[int, int, int]]:
    """(cores RGB 16x3 com linha 0 = fundo, índices 0-15, fundo_rgb)."""
    fundo = mapa["imagem"]["fundo"]
    fundo_rgb = tuple(int(fundo.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    cores = np.zeros((16, 3), np.int32)
    cores[0] = fundo_rgb
    for c in mapa["paleta"]["cores"]:
        cores[int(c["indice"])] = [int(c["cor"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return cores, np.arange(16), fundo_rgb


def _vote_block(block: np.ndarray, cores: np.ndarray, fundo_rgb, near_fundo: int) -> tuple[int, float, float]:
    """Voto maioritário ponderado pelo centro: → (índice, pureza, distância média do interior ao vencedor)."""
    h, w = block.shape[:2]
    pad_y, pad_x = max(1, h // 4), max(1, w // 4)
    inner = block[pad_y:h - pad_y or None, pad_x:w - pad_x or None]
    if inner.size == 0:                       # bloco minúsculo: usa o bloco todo
        inner = block
    inner = inner.reshape(-1, 3).astype(np.int32)
    d = ((inner[:, None, :] - cores[None, :, :]) ** 2).sum(axis=2)      # (n, 16)
    nearest = d.argmin(axis=1)
    # transparência: perto do fundo → índice 0 (a linha 0 da paleta já é o fundo)
    counts = np.bincount(nearest, minlength=16)
    winner = int(counts.argmax())
    purity = float(counts[winner]) / max(1, len(inner))
    dist = float(np.sqrt(d[nearest == winner][:, winner].mean())) if counts[winner] else 0.0
    return winner, purity, dist


def _estimate_offset(img: np.ndarray, mapa: dict, cores: np.ndarray, fundo_rgb, span: int) -> tuple[int, int, float]:
    """Offset global (em píxeis da imagem devolvida) que maximiza a CONCORDÂNCIA com os índices originais.
    (A pureza não serve: blocos de cor limpa têm pureza 1.0 em qualquer alinhamento.)"""
    im = mapa["imagem"]
    sx, sy = img.shape[1] / im["largura"], img.shape[0] / im["altura"]
    bloco = max(2, int(round(im["bloco"] * min(sx, sy))))
    cells = mapa["poses"][:: max(1, len(mapa["poses"]) // 24)]
    orig = {p["id"]: rle_decode(p["indices_rle"], p["canvas"][0], p["canvas"][1]) for p in cells}
    best = (0, 0, -1.0)
    step = max(1, span // 3)
    # ordem crescente de magnitude: em empate de concordância ganha a correção mais pequena
    cand = sorted(((dx, dy) for dy in range(-span, span + 1, step) for dx in range(-span, span + 1, step)),
                  key=lambda o: (abs(o[0]) + abs(o[1]), abs(o[0]), abs(o[1])))
    for dx, dy in cand:
            hits = total = 0
            for p in cells:
                old = orig[p["id"]]
                X0 = p["caixa_expandida"][0] * sx + dx
                Y0 = p["caixa_expandida"][1] * sy + dy
                for yy in range(1, p["canvas"][1] - 1):
                    for xx in range(1, p["canvas"][0] - 1):
                        bx, by = X0 + xx * im["bloco"] * sx, Y0 + yy * im["bloco"] * sy
                        if bx < 0 or by < 0 or bx + bloco > img.shape[1] or by + bloco > img.shape[0]:
                            continue
                        idx, _, _ = _vote_block(img[int(by):int(by) + bloco, int(bx):int(bx) + bloco], cores, fundo_rgb, 0)
                        hits += int(idx == int(old[yy, xx]))
                        total += 1
            if total:
                m = hits / total
                if m > best[2]:
                    best = (dx, dy, m)
    return best


def import_sheet(mapa: dict, image_path: Path, out_dir: Path, *, limpar: str = "auto", dirty: float = DIRTY_THRESHOLD,
                 near_fundo: int = NEAR_FUNDO, auto_align: bool = True) -> dict:
    """Re-quantiza a imagem devolvida para os índices do mapa e gera o plano de tiles."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    img = np.asarray(Image.open(image_path).convert("RGB"))
    cores, _, fundo_rgb = _palette_rgb(mapa)
    im = mapa["imagem"]
    sx, sy = img.shape[1] / im["largura"], img.shape[0] / im["altura"]
    if abs(sx - sy) > 0.02 * max(sx, sy):
        raise FabError(f"aspect ratio mudou: devolvida {img.shape[1]}x{img.shape[0]}, esperado {im['largura']}x{im['altura']}",
                       "peça ao modelo o mesmo aspect ratio; o import não adivinha o recorte")
    offset = (0, 0, 1.0)
    if auto_align:
        span = max(2, int(im["bloco"] * min(sx, sy) * 0.4))
        cand = _estimate_offset(img, mapa, cores, fundo_rgb, span)
        if cand[2] < 0.9:
            cand2 = _estimate_offset(img, mapa, cores, fundo_rgb, span * 2)
            cand = cand2 if cand2[2] > cand[2] else cand
        offset = cand
    dx, dy = int(offset[0]), int(offset[1])
    # re-quantização bloco a bloco
    dirty_blocks: list[dict] = []
    new_indices: dict[str, np.ndarray] = {}
    stats = {"blocos": 0, "sujos": 0, "pureza_media": 0.0}
    pur_sum = 0.0
    for p in mapa["poses"]:
        w, h = p["canvas"]
        arr = np.zeros((h, w), np.uint8)
        X0 = p["caixa_expandida"][0] * sx + dx
        Y0 = p["caixa_expandida"][1] * sy + dy
        bw, bh = im["bloco"] * sx, im["bloco"] * sy
        for yy in range(h):
            for xx in range(w):
                bx, by = X0 + xx * bw, Y0 + yy * bh
                x1, y1 = int(round(bx)), int(round(by))
                x2, y2 = int(round(bx + bw)), int(round(by + bh))
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(img.shape[1], max(x2, x1 + 1)), min(img.shape[0], max(y2, y1 + 1))
                idx, purity, dist = _vote_block(img[y1:y2, x1:x2], cores, fundo_rgb, near_fundo)
                arr[yy, xx] = idx
                stats["blocos"] += 1
                pur_sum += purity
                if purity < dirty:
                    stats["sujos"] += 1
                    dirty_blocks.append({"pose": p["id"], "px": [xx, yy], "pureza": round(purity, 3),
                                         "dist": round(dist, 1), "indice": int(idx)})
        new_indices[p["id"]] = arr
    stats["pureza_media"] = round(pur_sum / max(1, stats["blocos"]), 4)
    if limpar == "auto" and dirty_blocks:
        _limpar_sujos(mapa, new_indices, dirty_blocks, dirty)
    # comparação com o original → plano de tiles
    plano, conflitos, fora = _build_plan(mapa, new_indices)
    plano.update({"versao": 1, "ferramenta": "fab ai import", "gerado": now_iso(),
                  "map": mapa.get("nome", ""), "imagem": rel(Path(image_path)),
                  "alinhamento": {"offset_px": [dx, dy], "concordancia": round(float(offset[2]), 4),
                                  "escala": [round(sx, 4), round(sy, 4)]},
                  "estatisticas": stats, "blocos_sujos": dirty_blocks[:400],
                  "conflitos": conflitos, "fora_do_alvo": fora[:400]})
    write_json(out_dir / "plan.json", plano)
    _check_image(mapa, new_indices, dirty_blocks, out_dir)
    (out_dir / "report.md").write_text(_import_report(plano, mapa), encoding="utf-8", newline="\n")
    return {"dir": rel(out_dir), "plan": rel(out_dir / "plan.json"), "check": rel(out_dir / "check.png"),
            "report": rel(out_dir / "report.md"), "tiles_alterados": len(plano["tiles"]),
            "pixeis_alterados": plano["pixeis_alterados"], "blocos_sujos": stats["sujos"],
            "conflitos": len(conflitos), "fora_do_alvo": len(fora), "estatisticas": stats,
            "alinhamento": plano["alinhamento"],
            "proximo": (f"confira check.png/report.md; depois: fab ai import --map … --image … --mod mods/<id> "
                        "--name <nome> --evidence '…'  →  fab build  →  fab paint check")}


def _limpar_sujos(mapa: dict, new_indices: dict[str, np.ndarray], dirty_blocks: list[dict], dirty: float) -> None:
    """Limpeza dos quadrados que não ficaram corretos: bloco sujo herda a moda dos vizinhos limpos da mesma pose."""
    by_pose: dict[str, list[dict]] = {}
    for b in dirty_blocks:
        by_pose.setdefault(b["pose"], []).append(b)
    for pid, blocks in by_pose.items():
        arr = new_indices[pid]
        h, w = arr.shape
        for b in blocks:
            x, y = b["px"]
            votes: dict[int, int] = {}
            for ny in range(max(0, y - 1), min(h, y + 2)):
                for nx in range(max(0, x - 1), min(w, x + 2)):
                    if (nx, ny) == (x, y):
                        continue
                    if all(d["px"] != [nx, ny] for d in blocks):       # só vizinhos LIMPOS
                        v = int(arr[ny, nx])
                        votes[v] = votes.get(v, 0) + 1
            if votes:
                best = max(votes.values())
                winners = [v for v, n in votes.items() if n == best]
                if best >= 5 and len(winners) == 1:
                    arr[y, x] = winners[0]
                    b["limpo"] = True


def _tile_pixel(mapa: dict, inst: TileInstance, x: int, y: int) -> int:
    e = mapa["tiles"].get(inst.hash, {})
    raw = e.get("bytes")
    if not raw:
        return -1
    px = ppu.decode_4bpp(bytes.fromhex(raw))
    return int(px[inst.px_map(x, y) // 8, inst.px_map(x, y) % 8])


def _build_plan(mapa: dict, new_indices: dict[str, np.ndarray]) -> tuple[dict, list, list]:
    """Compara original × re-quantizado e resolve cada píxel alterado para (tile, píxel no tile)."""
    edits: dict[str, dict[int, int]] = {}
    origin: dict[str, dict[int, str]] = {}
    conflitos: list[dict] = []
    fora: list[dict] = []
    changed = 0
    for p in mapa["poses"]:
        old = rle_decode(p["indices_rle"], p["canvas"][0], p["canvas"][1])
        new = new_indices[p["id"]]
        insts = sorted((TileInstance.from_dict(t) for t in p["tiles"]), key=lambda i: i.oam)
        diff_y, diff_x = np.nonzero(old != new)
        for y, x in zip(diff_y, diff_x):
            changed += 1
            xi, yi = int(x), int(y)
            cand = [i for i in insts if i.covers(xi, yi)]
            drawn = [i for i in cand if _tile_pixel(mapa, i, xi, yi) > 0]
            owner = (drawn or cand or [None])[0]
            if owner is None:
                fora.append({"pose": p["id"], "px": [xi, yi], "novo": int(new[yi, xi])})
                continue
            tpx = owner.px_map(xi, yi)
            val = int(new[yi, xi])
            prev = edits.setdefault(owner.hash, {}).get(tpx)
            if prev is not None and prev != val:
                conflitos.append({"tile": owner.hash, "px": tpx, "valores": [prev, val],
                                  "origens": [origin[owner.hash][tpx], p["id"]]})
                continue
            if prev is None:
                origin.setdefault(owner.hash, {})[tpx] = p["id"]
            edits[owner.hash][tpx] = val
    tiles = []
    for h, pxmap in sorted(edits.items()):
        e = mapa["tiles"].get(h, {})
        raw = e.get("bytes")
        if not raw:
            conflitos.append({"tile": h, "erro": "bytes do tile ausentes no map.json"})
            continue
        arr = ppu.decode_4bpp(bytes.fromhex(raw))
        orig_arr = arr.copy()
        for tpx, val in pxmap.items():
            arr[tpx // 8, tpx % 8] = val
        tiles.append({"hash": h, "original": raw, "novo": ppu.encode_4bpp(arr).hex(),
                      "pixeis_alterados": len(pxmap), "vram": e.get("vram", []),
                      "mapa": {str(k): v for k, v in sorted(pxmap.items())}})
    return ({"tiles": tiles, "pixeis_alterados": changed}, conflitos, fora)


def _check_image(mapa: dict, new_indices: dict[str, np.ndarray], dirty_blocks: list[dict], out_dir: Path) -> None:
    """check.png: original (1 px) | re-quantizado | alterações (vermelho) | blocos sujos contornados."""
    cores, _, fundo_rgb = _palette_rgb(mapa)
    gr = mapa["grelha"]
    cw, ch = gr["celula"]
    gap = mapa["imagem"]["gap_px"]
    W1 = gap + gr["colunas"] * (cw + gap)
    H1 = gap + gr["linhas"] * (ch + gap)
    old_img = np.zeros((H1, W1, 3), np.uint8)
    new_img = np.zeros((H1, W1, 3), np.uint8)
    diff_img = np.zeros((H1, W1, 3), np.uint8)
    dirty_set = {(b["pose"], b["px"][0], b["px"][1]) for b in dirty_blocks}
    for p in mapa["poses"]:
        x0, y0 = p["caixa_celula_px"][0], p["caixa_celula_px"][1]
        old = rle_decode(p["indices_rle"], p["canvas"][0], p["canvas"][1])
        new = new_indices[p["id"]]
        for yy in range(p["canvas"][1]):
            for xx in range(p["canvas"][0]):
                o, n = int(old[yy, xx]), int(new[yy, xx])
                old_img[y0 + yy, x0 + xx] = cores[o]
                new_img[y0 + yy, x0 + xx] = cores[n]
                diff_img[y0 + yy, x0 + xx] = (220, 40, 40) if o != n else (30, 30, 36)
                if (p["id"], xx, yy) in dirty_set:
                    new_img[y0 + yy, x0 + xx] = (255, 0, 0)
    k = 3
    w, h = W1 * k, H1 * k
    out = Image.new("RGB", (w * 3 + 40, h + 40), BG_DARK)
    d = ImageDraw.Draw(out)
    for i, (arr, title) in enumerate(((old_img, "original"), (new_img, "re-quantizado (vermelho = bloco sujo)"),
                                      (diff_img, "alterações (vermelho = mudou)"))):
        out.paste(Image.fromarray(arr).resize((w, h), Image.NEAREST), (10 + i * (w + 10), 30))
        d.text((10 + i * (w + 10), 8), title, font=_font(13), fill=TEXT)
    out.save(out_dir / "check.png")


def _import_report(plano: dict, mapa: dict) -> str:
    st = plano["estatisticas"]
    L = [f"# Import IA — {plano.get('map') or mapa.get('nome')}", "",
         f"- imagem devolvida: `{plano['imagem']}` · alinhamento: offset {plano['alinhamento']['offset_px']} "
         f"(concordância {plano['alinhamento']['concordancia']})",
         f"- blocos: {st['blocos']} · pureza média {st['pureza_media']} · blocos sujos: {st['sujos']}",
         f"- píxeis alterados: {plano['pixeis_alterados']} · tiles alterados: {len(plano['tiles'])} · "
         f"conflitos: {len(plano['conflitos'])} · fora do alvo: {len(plano['fora_do_alvo'])}", ""]
    if plano["conflitos"]:
        L += ["## ⚠ Conflitos (o mesmo píxel de tile recebiu valores diferentes em poses diferentes)", ""]
        for c in plano["conflitos"][:20]:
            L.append(f"- tile `{c.get('tile', '?')}` px {c.get('px', '?')}: {c}")
        L.append("")
    if plano["fora_do_alvo"]:
        L += ["## ⚠ Píxeis novos sem tile dono (não transponíveis: exigiriam tiles/OAM novos)", ""]
        for f in plano["fora_do_alvo"][:20]:
            L.append(f"- {f['pose']} px {f['px']} → índice {f['novo']}")
        L.append("")
    if plano["blocos_sujos"]:
        L += ["## Blocos sujos (voto contestado — limpeza automática quando há maioria clara nos vizinhos)", "",
              "| pose | px | pureza | distância | limpo |", "|---|---|---|---|---|"]
        for b in plano["blocos_sujos"][:40]:
            L.append(f"| {b['pose']} | {b['px']} | {b['pureza']} | {b['dist']} | {'sim' if b.get('limpo') else 'NÃO'} |")
        L.append("")
    L += ["## Tiles alterados", "", "| hash | píxeis alterados | VRAM |", "|---|---|---|"]
    for t in plano["tiles"]:
        L.append(f"| {t['hash']} | {t['pixeis_alterados']} | {', '.join(t['vram']) or '—'} |")
    L += ["", "Próximo: `fab ai import --map map.json --image … --mod mods/<id> --name … --evidence …` grava o plano "
          "no paint.json (tiles crus = patch de dados; comprimidos = `fab gfx override`), depois `fab build` + "
          "`fab paint check` / `fab gfx check`.", ""]
    return "\n".join(L)


# ── aplicar o plano num mod ───────────────────────────────────────────────────

def apply_plan(mod_dir: Path, plano: dict, name: str, evidence: str) -> dict:
    """Escreve os tiles do plano no paint.json do mod (mesmo formato do `fab paint remap`):
    desenho cru na ROM → 'tiles' (patch de dados); comprimido/montado na RAM → 'vram_tiles' (gfx override)."""
    from .game import clean_rom
    from .mods import load_mod
    from .paint import PAINT_JSON, _load_spec
    from .rom import load_rom
    from .sprites import find_raw_tile
    if not evidence.strip():
        raise FabError("falta a evidência", 'ex.: --evidence "fab ai import: plan.json do export ken-moveset"')
    mod = load_mod(mod_dir)
    mod_dir = Path(mod["_dir"])
    rom = load_rom(clean_rom(mod["game"]))
    spec = _load_spec(mod_dir)
    spec.setdefault("tiles", [])
    spec.setdefault("vram_tiles", [])
    done, via = [], []
    for t in plano["tiles"]:
        orig = bytes.fromhex(t["original"])
        new = t["novo"]
        hits = find_raw_tile(rom.data, orig)
        entry = {"name": name, "hash": t["hash"], "bpp": 4, "original": t["original"], "new": new,
                 "map": t.get("map", {}), "evidence": evidence.strip(), "updated": now_iso()}
        if hits:
            for h in hits:
                spec["tiles"] = [e for e in spec["tiles"] if int(e["pc"], 0) != h]
                spec["tiles"].append({**entry, "pc": f"0x{h:06X}"})
            done.append({"hash": t["hash"], "rom": [f"0x{h:06X}" for h in hits], "pixeis": t["pixeis_alterados"]})
        else:
            spec["vram_tiles"] = [e for e in spec["vram_tiles"] if e["hash"] != t["hash"]]
            spec["vram_tiles"].append(entry)
            via.append({"hash": t["hash"], "pixeis": t["pixeis_alterados"]})
    write_json(mod_dir / PAINT_JSON, spec)
    return {"tiles_crus": done, "tiles_via_override": via,
            "proximo": (f"fab build {rel(mod_dir)}" + (f" && fab gfx override {rel(mod_dir)} --dump <dump do gfx dump>"
                        if via else "") + "  →  fab paint check / fab gfx check")}


# ── round-trip (verificação) ──────────────────────────────────────────────────

def roundtrip(mapa: dict, out_dir: Path) -> dict:
    """Prova o ciclo completo sem o modelo: (1) identidade — importar a folha original tem de dar 0 mudanças;
    (2) perturbação — deslocar/borrar/tingir devolve a imagem original salvo os píxeis realmente perturbados."""
    from PIL import ImageFilter
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sheet_path = Path(mapa["_dir"]) / mapa["imagem"]["arquivo"]
    base = Image.open(sheet_path).convert("RGB")
    # 1) identidade
    r1 = import_sheet(mapa, sheet_path, out_dir / "identidade", auto_align=False)
    ok_ident = r1["tiles_alterados"] == 0 and r1["pixeis_alterados"] == 0
    # 2) perturbação: offset 3px + blur leve (o import tem de re-alinhar e manter os píxeis)
    pert = base.copy()
    canvas = Image.new("RGB", base.size, tuple(int(mapa["imagem"]["fundo"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)))
    canvas.paste(pert, (3, 2))
    canvas = canvas.filter(ImageFilter.GaussianBlur(0.6))
    canvas.save(out_dir / "perturbada.png")
    r2 = import_sheet(mapa, out_dir / "perturbada.png", out_dir / "perturbado", auto_align=True)
    res = {"identidade": {"ok": ok_ident, "tiles_alterados": r1["tiles_alterados"],
                          "pixeis_alterados": r1["pixeis_alterados"], "pureza": r1["estatisticas"]["pureza_media"]},
           "perturbado": {"alinhamento": r2["alinhamento"], "blocos_sujos": r2["blocos_sujos"],
                          "pixeis_alterados": r2["pixeis_alterados"], "tiles_alterados": r2["tiles_alterados"],
                          "pureza": r2["estatisticas"]["pureza_media"]},
           "veredito": "PERFEITO" if ok_ident else "FALHA NA IDENTIDADE",
           "dirs": [rel(out_dir / "identidade"), rel(out_dir / "perturbado")]}
    write_json(out_dir / "roundtrip.json", res)
    return res
