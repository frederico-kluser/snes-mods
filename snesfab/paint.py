"""Pintura declarativa: rampas com pré-visualização exata e `paint.json` → `paint.asm` + `data[]`.

O agente decide CORES (olhando imagens), nunca endereços de `org`: o `paint.json` guarda
offsets de arquivo (PC) da paleta e os índices; daqui sai o `.asm` com o `org` certo para o mapa
(`rom.asar_org` — no S-DD1 o `org` do Asar não é o endereço que a CPU vê) e as regiões `data[]` com
evidência para o `fab build` conferir.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import ppu
from .game import clean_rom, load_game
from .mods import load_mod
from .ramp import Ramp
from .rom import ASAR_DIRECTIVE, asar_org, fmt_addr, load_rom, pc_to_snes
from .sprites import BG_DARK, TEXT, TEXT_DIM, FrameData, _crop_box, _scale, _text, swatch_rgb
from .util import FabError, now_iso, rel, write_json

PAINT_JSON = "paint.json"
PAINT_ASM = "paint.asm"


# ── pré-visualização ────────────────────────────────────────────────────────────

def recolor(fd: FrameData, o, indices: list[int], colors: list[int]) -> np.ndarray:
    """O frame com os píxeis do alvo (sprite ou BG) nesses índices trocados pelas cores novas (exato: sem color
    math, a tela mostra exatamente a cor da CGRAM — conferido pela falsa cor)."""
    from .sprites import color_index_map
    img = fd.real.copy()
    col = color_index_map(fd, o)
    for i, c in zip(indices, colors):
        img[col == i] = swatch_rgb(c)
    return img


def ramp_sheet(fd: FrameData, o, indices: list[int], orig: list[int], ramps: list[Ramp],
               title: str) -> Image.Image:
    """Uma linha por candidata: nome + conferências | tons (antes em cima, depois em baixo) | o objeto pintado."""
    cx0, cy0, cx1, cy1 = _crop_box(o, fd.real.shape, 3)
    h = cy1 - cy0
    k = max(2, min(5, 260 // max(h, 1)))
    rows = [("original", orig, ["(como está no jogo)"], True)] + [(r.name, r.colors, r.checks, r.ok) for r in ramps]
    import textwrap
    sw = 34
    left = 400
    crop_w = (cx1 - cx0) * k
    row_h = max(h * k, 170) + 16
    W = max(left + len(indices) * sw + 30 + crop_w + 20 + (cx1 - cx0) + 20, 1000)
    H = 40 + len(rows) * row_h + 24
    out = Image.new("RGB", (W, H), BG_DARK)
    d = ImageDraw.Draw(out)
    _text(d, (12, 8), title, size=15)
    for r_i, (name, cols, checks, ok) in enumerate(rows):
        y = 40 + r_i * row_h
        if r_i:
            d.line((0, y - 6, W, y - 6), fill=(60, 60, 70))
        _text(d, (12, y), name, size=18, fill=TEXT if ok else (255, 120, 120))
        yy = y + 28
        for msg in checks[:5]:
            for part in textwrap.wrap(msg, 50, subsequent_indent="   "):
                _text(d, (12, yy), part, size=12, fill=TEXT_DIM if msg.startswith("✓") else (255, 200, 120))
                yy += 18
        x = left
        for n, (i, c) in enumerate(zip(indices, cols)):
            d.rectangle((x + n * sw, y + 4, x + n * sw + sw - 4, y + 30), fill=swatch_rgb(orig[n]), outline=(80, 80, 80))
            d.rectangle((x + n * sw, y + 34, x + n * sw + sw - 4, y + 74), fill=swatch_rgb(c), outline=(160, 160, 160))
            _text(d, (x + n * sw + 2, y + 78), f"{i}", size=11, fill=TEXT_DIM)
            _text(d, (x + n * sw + 1, y + 94), f"{c:04X}", size=9, fill=TEXT_DIM)
        img = recolor(fd, o, indices, cols)
        crop = img[cy0:cy1, cx0:cx1]
        px = left + len(indices) * sw + 30
        out.paste(_scale(crop, k), (px, y))
        out.paste(Image.fromarray(crop), (px + crop_w + 20, y))          # 1x: o que o jogador vê
    _text(d, (left, H - 22), "em cima: tom original · embaixo: tom novo · à direita: ampliado e em tamanho real (1x)",
          size=12, fill=TEXT_DIM)
    return out


def outline_colors(fd: FrameData, o, indices: list[int]) -> list[int]:
    """O tom mais escuro do objeto fora dos índices a pintar (em sprite costuma ser o contorno)."""
    from .ramp import lch
    base = 16 * o.cgram_palette
    others = [int(fd.colors[base + i]) for i in o.counts if i not in indices]
    if not others:
        return []
    return [min(others, key=lambda c: lch(c)[0])]


# ── paint.json → paint.asm + data[] ────────────────────────────────────────────

def _load_spec(mod_dir: Path) -> dict:
    p = mod_dir / PAINT_JSON
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"_doc": "editado por `fab paint set`; `fab paint apply` gera paint.asm e as regiões data[] do mod.json",
            "palettes": []}


def _runs(indices: list[int]) -> list[list[int]]:
    runs = []
    for i in sorted(indices):
        if runs and i == runs[-1][-1] + 1:
            runs[-1].append(i)
        else:
            runs.append([i])
    return runs


def set_palette(mod_dir: Path, pc: int, indices: list[int], colors: list[int], name: str, evidence: str) -> dict:
    """Grava/atualiza uma troca de cores no paint.json (com os tons originais lidos da base limpa)."""
    mod = load_mod(mod_dir)
    mod_dir = Path(mod["_dir"])
    if len(indices) != len(colors):
        raise FabError(f"{len(indices)} índices e {len(colors)} cores", "passe uma cor por índice, na mesma ordem")
    if not evidence.strip():
        raise FabError("falta a evidência", 'ex.: --evidence "fab sprite snap: obj 2 = o personagem, paleta 7E:xxxx ← ROM 0x…"')
    if any(not 0 <= i <= 15 for i in indices):
        raise FabError("índice de cor fora de 0-15")
    img = load_rom(clean_rom(mod["game"]))
    if pc < 0 or pc + 32 > len(img.data):
        raise FabError(f"pc 0x{pc:X} fora da ROM")
    orig = {str(i): ppu.fmt_color(img.data[pc + 2 * i] | (img.data[pc + 2 * i + 1] << 8)) for i in indices}
    spec = _load_spec(mod_dir)
    entry = {"name": name, "pc": f"0x{pc:06X}", "set": {str(i): ppu.fmt_color(c) for i, c in zip(indices, colors)},
             "original": orig, "evidence": evidence.strip(), "updated": now_iso()}
    spec["palettes"] = [p for p in spec["palettes"] if p["name"] != name]
    spec["palettes"].append(entry)
    write_json(mod_dir / PAINT_JSON, spec)
    return entry


def remap_tiles(mod_dir: Path, fd: FrameData, target, mapping: dict[int, int], name: str, evidence: str,
                only: dict[str, set[int]] | None = None) -> dict:
    """Troca ÍNDICES dentro do desenho dos tiles do alvo: ex.: {14: 9, 15: 12} pinta a luva com tons da roupa.
    `only` = {hash: píxeis 0-63} restringe aos píxeis de uma peça (rótulos) — é o que separa luva e cabelo DENTRO do
    mesmo tile (nível 4). Desenho cru na ROM → paint.json "tiles" (patch de dados, um registro por cópia); desenho
    comprimido/montado na RAM → "vram_tiles" (servido pelo `fab gfx override`, sem codec)."""
    from .ppu import decode_4bpp, encode_4bpp
    from .sprites import find_raw_tile, object_tiles
    mod = load_mod(mod_dir)
    mod_dir = Path(mod["_dir"])
    if not evidence.strip():
        raise FabError("falta a evidência", "diga de onde vêm os tiles e o mapa de índices")
    rom = load_rom(clean_rom(mod["game"]))
    spec = _load_spec(mod_dir)
    spec.setdefault("tiles", [])
    done, via = [], []
    for t in object_tiles(fd, target, sorted(mapping)):
        px = decode_4bpp(t["bytes"])
        new = px.copy()
        allowed = only.get(t["hash"]) if only is not None else None
        if only is not None and not allowed:
            continue
        for p in range(64):
            if allowed is not None and p not in allowed:
                continue
            y, x = divmod(p, 8)
            if int(px[y, x]) in mapping:
                new[y, x] = mapping[int(px[y, x])]
        if (new == px).all():
            continue
        hits = find_raw_tile(rom.data, t["bytes"])
        new_bytes = encode_4bpp(new)
        if not hits:
            spec.setdefault("vram_tiles", [])
            spec["vram_tiles"] = [e for e in spec["vram_tiles"] if e["hash"] != t["hash"]]
            spec["vram_tiles"].append({"name": name, "hash": t["hash"], "bpp": 4, "original": t["bytes"].hex(),
                                       "new": new_bytes.hex(), "map": {str(k): v for k, v in mapping.items()},
                                       "evidence": evidence.strip(), "updated": now_iso()})
            via.append({"vram": f"${t['vram']:04X}", "hash": t["hash"], "pixeis_trocados": int((new != px).sum())})
            continue
        for h in hits:
            spec["tiles"] = [e for e in spec["tiles"] if int(e["pc"], 0) != h]
            spec["tiles"].append({"name": name, "pc": f"0x{h:06X}", "hash": t["hash"], "original": t["bytes"].hex(),
                                  "new": new_bytes.hex(), "map": {str(k): v for k, v in mapping.items()},
                                  "evidence": evidence.strip(), "updated": now_iso()})
        done.append({"vram": f"${t['vram']:04X}", "hash": t["hash"], "rom": [f"0x{h:06X}" for h in hits],
                     "pixeis_trocados": int((new != px).sum())})
    write_json(mod_dir / PAINT_JSON, spec)
    return {"tiles_trocados": done, "tiles_via_override": via,
            "aviso": "o mesmo desenho achado em mais de um lugar foi trocado em todos" if any(len(d["rom"]) > 1 for d in done) else None,
            "proximo": ("desenho comprimido/montado na RAM: `fab gfx dump <jogo> --state … --frames …` (cenário em que o "
                        "gráfico é CARREGADO) e `fab gfx override <mod> --dump <dir>`") if via else None}


def _merge_regions(data: list[dict], gap: int = 2) -> list[dict]:
    """Regiões data[] vizinhas (até `gap` bytes) viram uma só: o build junta diferenças próximas numa região e
    exige que UMA declaração a cubra inteira."""
    out: list[dict] = []
    for d in sorted(data, key=lambda d: int(d["pc"], 0)):
        start = int(d["pc"], 0)
        if out and start <= int(out[-1]["pc"], 0) + out[-1]["length"] + gap:
            last = out[-1]
            end = max(int(last["pc"], 0) + last["length"], start + d["length"])
            last["length"] = end - int(last["pc"], 0)
            if d["evidence"] not in last["evidence"]:
                last["evidence"] += " | " + d["evidence"]
        else:
            out.append(dict(d))
    return out


def apply_paint(mod_dir: Path) -> dict:
    """paint.json → paint.asm (org pelo mapa do jogo) + mod.json (patches e data[] com source=paint)."""
    mod = load_mod(mod_dir)
    mod_dir = Path(mod["_dir"])
    spec = _load_spec(mod_dir)
    if not spec["palettes"] and not spec.get("tiles"):
        if spec.get("vram_tiles"):
            return {"paint_asm": None, "regioes": 0, "trocas": [], "patches": load_mod(mod_dir).get("patches", []),
                    "proximo": f"só desenho comprimido: `fab gfx override {rel(mod_dir)} --dump <dir do fab gfx dump>`"}
        raise FabError(f"{rel(mod_dir / PAINT_JSON)} sem trocas", "use `fab paint set` (cores) ou `fab paint remap` (desenho)")
    game = load_game(mod["game"])
    img = load_rom(clean_rom(mod["game"]))
    mapping = img.mapping
    lines = [f"; GERADO por `fab paint apply` a partir de {PAINT_JSON} — NÃO edite à mão (edite o {PAINT_JSON}).",
             f"; jogo: {game.get('title', mod['game'])} · mapa: {mapping}"
             + (" (o org do Asar é LoROM; a CPU vê os 2 MiB de cima por $E0-$FF)" if mapping == "sdd1" else ""),
             ASAR_DIRECTIVE[mapping], ""]
    data = []
    table = []
    for p in spec["palettes"]:
        base = int(p["pc"], 0)
        idx = sorted(int(i) for i in p["set"])
        lines.append(f"; {p['name']}: {p['evidence']}")
        for run in _runs(idx):
            pc = base + 2 * run[0]
            org = asar_org(pc, mapping)
            before = " ".join(p["original"].get(str(i), "?") for i in run)
            after = ", ".join(p["set"][str(i)] for i in run)
            lines.append(f"org ${org:06X}   ; PC 0x{pc:06X} = {fmt_addr(pc_to_snes(pc, mapping))} · índices "
                         f"{run[0]}-{run[-1]} da paleta 0x{base:06X} (antes: {before})")
            lines.append(f"    dw {after}")
            data.append({"pc": f"0x{pc:06X}", "length": 2 * len(run), "evidence": f"{p['name']}: {p['evidence']}",
                         "source": "paint"})
            table.append({"paleta": p["name"], "pc": f"0x{pc:06X}", "indices": f"{run[0]}-{run[-1]}",
                          "antes": before, "depois": after.replace(",", "")})
        lines.append("")
    for t in sorted(spec.get("tiles", []), key=lambda t: int(t["pc"], 0)):
        pc = int(t["pc"], 0)
        new = bytes.fromhex(t["new"])
        lines.append(f"; tile {t['hash']} ({t['name']}: mapa {t['map']}): {t['evidence']}")
        lines.append(f"org ${asar_org(pc, mapping):06X}   ; PC 0x{pc:06X} = {fmt_addr(pc_to_snes(pc, mapping))}")
        lines += ["    db " + ",".join(f"${b:02X}" for b in new[i:i + 16]) for i in range(0, len(new), 16)]
        data.append({"pc": f"0x{pc:06X}", "length": len(new), "evidence": f"tile {t['hash']} ({t['name']}): {t['evidence']}",
                     "source": "paint"})
        table.append({"tile": t["hash"], "pc": f"0x{pc:06X}", "mapa": t["map"]})
    (mod_dir / PAINT_ASM).write_text("\n".join(lines), encoding="utf-8", newline="\n")
    mj = mod_dir / "mod.json"
    raw = json.loads(mj.read_text(encoding="utf-8"))
    patches = raw.get("patches") or (["patch.asm"] if (mod_dir / "patch.asm").exists() else [])
    if PAINT_ASM not in patches:
        patches.append(PAINT_ASM)
    raw["patches"] = patches
    raw["data"] = [d for d in raw.get("data", []) if d.get("source") != "paint"] + _merge_regions(data)
    write_json(mj, raw)
    return {"paint_asm": rel(mod_dir / PAINT_ASM), "regioes": len(data), "trocas": table, "patches": patches,
            "proximo": f"fab build {rel(mod_dir)}  →  fab paint check {rel(mod_dir)} --state <state> --frames N"}


# ── verificação por EFEITO: mod × base, mesmo state/frames ─────────────────────────

GREEN, RED, YELLOW, ORANGE = (40, 230, 90), (255, 40, 40), (255, 220, 0), (255, 140, 0)


def expected_changes(spec: dict, colors_base: np.ndarray) -> dict[int, int]:
    """CGRAM índice → cor nova, para cada paleta da CGRAM que (no frame da base) tem os tons ORIGINAIS de uma
    troca do paint.json nesses índices. Assim não é preciso saber em que paleta da CGRAM o jogo pôs a da ROM."""
    out: dict[int, int] = {}
    for p in spec.get("palettes", []):
        idx = sorted(int(i) for i in p["set"])
        orig = [ppu.parse_color(p["original"][str(i)]) for i in idx]
        new = [ppu.parse_color(p["set"][str(i)]) for i in idx]
        for P in range(16):
            if all(int(colors_base[16 * P + i]) == o for i, o in zip(idx, orig)):
                for i, n in zip(idx, new):
                    out[16 * P + i] = n
    return out


def expected_pixels(spec: dict, base: FrameData, expected: dict[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Alvo e cor esperada por píxel: trocas de PALETA (pelo índice da CGRAM na falsa cor) e de DESENHO (tiles
    remapeados, pelo hash do conteúdo + píxel dentro do tile no render da camada de sprites)."""
    idx = base.index
    target = np.zeros(idx.shape, bool)
    want = np.zeros(idx.shape + (3,), np.uint8)
    for ci, newc in expected.items():
        m = idx == ci
        target |= m
        want[m] = swatch_rgb(newc)
    om = spec.get("oam_mirror")
    if om and base.snap is not None:          # paleta-espelho por tabela de tiles (fab paint oam-mirror)
        lay = base.layer()
        vis = base.visible_obj()
        tset = set(int(t) for t in om["tiles"])
        cols = {int(k): ppu.parse_color(v) for k, v in om["colors"].items()}
        for y, x in zip(*np.nonzero(vis & (lay.palette == int(om["src"])))):
            if lay.entries[int(lay.oam[y, x])].tile not in tset:
                continue
            c = int(lay.color[y, x])
            if c in cols:
                target[y, x] = True
                want[y, x] = swatch_rgb(cols[c])
    tiles = [t for t in (spec.get("tiles") or []) + (spec.get("vram_tiles") or []) if int(t.get("bpp", 4)) == 4]
    if tiles and base.snap is not None:
        from .ppu import decode_4bpp
        from .sprites import tile_hash
        remap = {t["hash"]: decode_4bpp(bytes.fromhex(t["new"])) for t in tiles}
        lay = base.layer()
        vis = base.visible_obj()
        cache: dict[int, str] = {}
        for y, x in zip(*np.nonzero(vis)):
            a = int(lay.tile_addr[y, x])
            h = cache.get(a) or cache.setdefault(a, tile_hash(base.snap.vram, a))
            grid = remap.get(h)
            if grid is None:
                continue
            p = int(lay.tile_px[y, x])
            new_i = int(grid[p // 8, p % 8])
            if new_i == int(lay.color[y, x]):
                continue
            ci = 128 + 16 * int(lay.palette[y, x]) + new_i
            target[y, x] = True
            want[y, x] = swatch_rgb(expected.get(ci, int(base.colors[ci])))
    return target, want


def classify_frame(base: FrameData, mod_img: np.ndarray, expected: dict[int, int], spec: dict | None = None) -> dict:
    """Píxel a píxel: esperado (mudou para a cor certa), cor errada, colateral (mudou fora do alvo) e faltou."""
    changed = np.any(base.real != mod_img, axis=-1)
    target, want = expected_pixels(spec or {}, base, expected)
    right = np.all(mod_img == want, axis=-1)
    ok = changed & target & right
    wrong = changed & target & ~right
    collateral = changed & ~target
    missed = target & ~changed & ~right          # devia mudar e ficou igual (paleta ainda não recarregada?)
    return {"masks": {"ok": ok, "wrong": wrong, "collateral": collateral, "missed": missed},
            "counts": {"esperado": int(ok.sum()), "cor_errada": int(wrong.sum()), "colateral": int(collateral.sum()),
                       "faltou": int(missed.sum()), "alvo": int(target.sum()), "mudou": int(changed.sum())}}


def check_sheet(base: FrameData, mod_img: np.ndarray, res: dict, title: str, scale: int = 2) -> Image.Image:
    a, b = _scale(base.real, scale), _scale(mod_img, scale)
    ov = (base.real.mean(axis=2, keepdims=True) * 0.35).astype(np.uint8).repeat(3, axis=2)
    m = res["masks"]
    for key, col in (("ok", GREEN), ("missed", YELLOW), ("wrong", ORANGE), ("collateral", RED)):
        ov[m[key]] = col
    c = _scale(ov, scale)
    W = a.width * 3 + 40
    H = a.height + 120
    out = Image.new("RGB", (W, H), BG_DARK)
    d = ImageDraw.Draw(out)
    _text(d, (10, 8), title, size=15)
    for i, im in enumerate((a, b, c)):
        out.paste(im, (10 + i * (a.width + 10), 34))
    labels = ("base (antes)", "mod (depois)", "diferença")
    for i, lab in enumerate(labels):
        _text(d, (10 + i * (a.width + 10), 38 + a.height), lab, size=13, fill=TEXT_DIM)
    k = res["counts"]
    y = 62 + a.height
    items = [(GREEN, f"esperado {k['esperado']}"), (YELLOW, f"faltou {k['faltou']}"),
             (ORANGE, f"cor errada {k['cor_errada']}"), (RED, f"colateral {k['colateral']}")]
    x = 10
    for col, txt in items:
        d.rectangle((x, y + 2, x + 16, y + 18), fill=col)
        _text(d, (x + 22, y + 1), txt, size=14)
        x += 220
    verdict = res["veredito"]
    _text(d, (10, y + 28), verdict, size=14, fill=(140, 255, 160) if verdict.startswith("OK") else (255, 160, 120))
    return out


def find_reload_frame(rom_mod: Path, rom_base: Path, game: str, spec: dict, *, state: Path | None, macro: list,
                      warmup: int, max_frames: int, work: Path) -> dict:
    """O savestate traz a paleta já carregada pela ROM limpa: a pintura só aparece quando o jogo RECARREGA a
    paleta da ROM. Acha o 1.º frame em que a CGRAM do mod tem as cores novas (sem adivinhar warmup)."""
    from .emu import Job, Watch, read_trace, run_job
    from .sprites import capture
    probe = capture(game, work / "alvo", rom=rom_base, state=state, macro=macro, frames=[warmup], warmup=warmup,
                    label="alvo")
    exp = expected_changes(spec, probe.frame(warmup).colors)
    if not exp:
        return {"frame": None, "motivo": f"no frame {warmup} da base nenhuma paleta da CGRAM tem os tons originais "
                                         "do paint.json (a peça não está na tela? outra tela?)"}
    watches = [Watch.from_spec(f"c{ci}=cgram:{2 * ci:04X}:2") for ci in sorted(exp)]
    run_dir = work / "recarga"
    run_job(rom_mod, Job(frames=max_frames, state=state, macro=macro, watches=watches, capture_every=0), run_dir)
    tr = read_trace(run_dir)
    for n, f in enumerate(tr["frame"]):
        if all(tr[f"c{ci}"][n] == c for ci, c in exp.items()):
            return {"frame": int(f), "cgram": sorted(exp), "motivo": "1.º frame com as cores novas na CGRAM do mod"}
    return {"frame": None, "cgram": sorted(exp),
            "motivo": f"em {max_frames} frames o jogo não recarregou a paleta: crie o state antes do carregamento "
                      "(ex.: na seleção) ou ande/ataque no macro para forçar a recarga"}


def check_paint(mod_dir: Path, out_dir: Path, *, state: Path | None, macro: list, frames: list[int] | None,
                warmup: int = 0, baseline_rom: Path | None = None, max_frames: int = 600) -> dict:
    """Roda base e mod nos mesmos frames, decodifica a base em falsa cor e classifica cada píxel alterado.
    frames=None → automático: 3 frames logo depois de o jogo carregar as cores novas."""
    from .paths import BUILD
    from .sprites import capture
    mod = load_mod(mod_dir)
    mod_dir = Path(mod["_dir"])
    spec = _load_spec(mod_dir)
    rom_mod = BUILD / mod["id"] / f"{mod['id']}.sfc"
    if not rom_mod.exists():
        raise FabError(f"ROM do mod ainda não montada: {rel(rom_mod)}", f"rode `fab build {rel(mod_dir)}`")
    rom_base = baseline_rom or clean_rom(mod["game"])
    auto = None
    if not frames:
        auto = find_reload_frame(rom_mod, rom_base, mod["game"], spec, state=state, macro=macro, warmup=warmup,
                                 max_frames=max_frames, work=out_dir / "auto")
        if auto["frame"] is None:
            raise FabError(f"não deu para escolher os frames: {auto['motivo']}", "passe --frames à mão ou mude o state")
        f0 = max(auto["frame"], warmup)
        frames = sorted({min(f0 + d, max_frames - 1) for d in (2, 30, 90)})
    base = capture(mod["game"], out_dir / "base", rom=rom_base, state=state, macro=macro, frames=frames, warmup=warmup,
                   label="base")
    modc = capture(mod["game"], out_dir / "mod", rom=rom_mod, state=state, macro=macro, frames=frames, warmup=warmup,
                   label="mod")
    results = []
    total = {"esperado": 0, "cor_errada": 0, "colateral": 0, "faltou": 0}
    for f in sorted(base.frames):
        bf, mf = base.frames[f], modc.frames.get(f)
        if mf is None:
            continue
        exp = expected_changes(spec, bf.colors)
        res = classify_frame(bf, mf.real, exp, spec)
        k = res["counts"]
        for key in total:
            total[key] += k[key]
        in_cgram = all(int(mf.colors[ci]) == c for ci, c in exp.items()) if exp else bool(spec.get("tiles") or spec.get("vram_tiles"))
        if not exp and not res["counts"]["alvo"]:
            verdict = "SEM ALVO: nenhuma paleta da CGRAM tem os tons originais neste frame (outra tela? já recolorida?)"
        elif k["colateral"] or k["cor_errada"]:
            verdict = f"ERRO: {k['colateral']} px mudaram FORA do alvo e {k['cor_errada']} com cor errada"
        elif k["faltou"]:
            verdict = (f"PARCIAL: {k['faltou']} px do alvo ainda com a cor antiga "
                       f"({'a CGRAM do mod já tem as cores novas' if in_cgram else 'a CGRAM do mod ainda NÃO tem as cores novas: o jogo não recarregou a paleta — use warmup ou outro frame'})")
        else:
            verdict = f"OK: {k['esperado']} px mudaram, todos no alvo e com a cor certa; 0 colaterais"
        res["veredito"] = verdict
        img = out_dir / f"check-f{f:05d}.png"
        check_sheet(bf, mf.real, res, f"{mod['id']} · frame {f} · paletas-alvo na CGRAM: "
                    f"{sorted({ci // 16 for ci in exp}) or '—'}").save(img)
        results.append({"frame": f, "imagem": rel(img), "contagens": k, "cgram_do_mod_tem_as_cores_novas": in_cgram,
                        "veredito": verdict})
    budget = vblank_check(rom_base, rom_mod, state=state, macro=macro, frames=max(frames) + 1, work=out_dir / "vblank")
    ok = bool(results) and all(r["veredito"].startswith("OK") for r in results) and budget["ok"]
    summary = {"mod": mod["id"], "ok": ok, "total": total, "frames": results, "vblank": budget, "base": rel(rom_base),
               "dir": rel(out_dir)}
    if auto:
        summary["recarga_da_paleta"] = auto
    write_json(out_dir / "check.json", summary)
    return summary


def vblank_check(rom_base: Path, rom_mod: Path, *, state: Path | None, macro: list, frames: int, work: Path) -> dict:
    """Roda base e mod com o log de DMA e acusa DMA que passou a cair com a imagem sendo desenhada (estouro de
    VBlank) — vale para qualquer mod com código, inclusive os de paleta-espelho."""
    from .dma import read_dma, vblank_budget
    from .emu import Job, run_job
    ev = []
    for name, rom in (("base", rom_base), ("mod", rom_mod)):
        d = work / name
        run_job(rom, Job(frames=min(frames, 600), state=state, macro=macro, capture_every=0, dma_log=True), d)
        ev.append(read_dma(d))
    return vblank_budget(ev[0], ev[1])
