"""CLI `fab` — fábrica de mods de SNES. `fab <comando> --help` para detalhes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .util import EXIT_FAIL, EXIT_OK, FabError, rel


def out(obj) -> None:
    if isinstance(obj, str):
        print(obj)
    else:
        print(json.dumps(obj, indent=1, ensure_ascii=False, default=str))


def _evidence(rec: dict) -> None:
    """Imprime um registro de evidência com o cabeçalho primeiro (id, perfil, limitações)."""
    print(f"evidence_id: {rec['evidence_id']}  ({rec['kind']})")
    print("analysis_profile: " + json.dumps(rec["analysis_profile"], ensure_ascii=False, default=str))
    res = rec["normalized_result"]
    lines_key = next((k for k in ("instructions", "matches") if isinstance(res, dict) and k in res), None)
    if rec["kind"] == "decompile":
        print("normalized_result:")
        for item in res:
            print(f"  // {item.get('entry')} {item.get('name')} (pedido {item.get('request')})")
            body = (item.get("c") or f"/* erro: {item.get('error')} */").replace("\r\n", "\n").strip("\n")
            print("\n".join("  " + line for line in body.splitlines()))
    elif lines_key:
        meta = {k: v for k, v in res.items() if k != lines_key}
        print("normalized_result: " + json.dumps(meta, ensure_ascii=False, default=str))
        for line in res[lines_key]:
            print("  " + line)
    else:
        print("normalized_result:")
        print(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    print("limitations:")
    for limit in rec["limitations"]:
        print("  - " + limit)


# ── comandos ──────────────────────────────────────────────────────────────────

def cmd_setup(a):
    from .setup_tools import setup
    out(setup(force=a.force, rea=not a.no_rea, testbed=not a.no_testbed))


def cmd_doctor(a):
    from .setup_tools import doctor
    r = doctor(quick=a.quick, rea=a.rea)
    for c in r["checks"]:
        print(f"{c['status']:<4} {c['check']:<34} {c['detail']}")
    print("RESULTADO: " + ("SAUDÁVEL" if r["ok"] else "COM FALHAS"))
    return EXIT_OK if r["ok"] else EXIT_FAIL


def cmd_rom_add(a):
    from .game import add_rom
    m = add_rom(Path(a.path), a.id, a.force, a.note or "")
    out({k: m[k] for k in ("id", "title", "mapping", "size", "smc_header", "checksum", "rom") if k in m}
        | {"header": m["header"], "next": [f"fab state boot {m['id']} <nome> --macro \"…\"  (ou fab play {m['id']} + fab state import)",
                                           f"fab re cdl {m['id']} --state <nome> --frames 3600", f"fab re analyze {m['id']}"]})


def cmd_rom_info(a):
    from .game import load_game
    g = load_game(a.game)
    g.pop("_dir", None)
    out(g)


def cmd_rom_list(a):
    from .game import list_games
    out(list_games())


def cmd_addr(a):
    from .game import clean_rom
    from .rom import fmt_addr, load_rom, parse_addr, wram_offset, is_mmio
    img = load_rom(Path(a.rom) if a.rom else clean_rom(a.game))
    if a.pc:
        pc = int(a.value, 16) if not a.value.startswith("0x") else int(a.value, 0)
        s = img.to_snes(pc)
        out({"pc": f"0x{pc:06X}", "snes": fmt_addr(s), "mapping": img.mapping})
        return
    addr = parse_addr(a.value)
    r = {"snes": fmt_addr(addr), "mapping": img.mapping}
    w = wram_offset(addr)
    if w is not None:
        r["wram"] = f"7E:{w:04X}" if w < 0x10000 else f"7F:{w - 0x10000:04X}"
        r["kind"] = "WRAM"
    elif is_mmio(addr):
        r["kind"] = "MMIO"
    else:
        try:
            pc = img.to_pc(addr)
            r.update({"kind": "ROM", "pc": f"0x{pc:06X}", "canonical": fmt_addr(img.to_snes(pc))})
        except FabError as e:
            r.update({"kind": "?", "note": e.what})
    out(r)


def cmd_disasm(a):
    from .disasm65816 import disassemble
    from .game import clean_rom
    from .rom import load_rom, parse_addr
    img = load_rom(Path(a.rom) if a.rom else clean_rom(a.game))
    addr = parse_addr(a.addr)
    m8, x8 = True, True
    if a.flags:
        f = a.flags.lower().replace(" ", "").split(",")
        m8 = "m16" not in f
        x8 = "x16" not in f
    pc = img.to_pc(addr)
    for ins in disassemble(img.data[pc:pc + a.count * 4 + 8], addr, count=a.count, m8=m8, x8=x8):
        print(ins.fmt())
    print("; flags iniciais assumidas: " + ("m8" if m8 else "m16") + "," + ("x8" if x8 else "x16")
          + " — confirme com `fab probe exec` (o '?' indica PLP/RTI/XCE: estado incerto)")


def cmd_play(a):
    from .game import play
    out(play(a.game, Path(a.rom) if a.rom else None))


def cmd_state_list(a):
    from .game import list_states
    out(list_states(a.game))


def cmd_state_import(a):
    from .game import import_state
    out(import_state(a.game, a.name, a.file, a.slot, a.note or ""))


def cmd_state_boot(a):
    from .emu import Job, run_job, new_run_dir
    from .game import clean_rom, state_path, states_dir
    from .investigate import _macro
    from .macro import total_frames
    from .media import postprocess_run
    from .rom import load_rom
    from .util import now_iso, slugify, write_json
    rom = clean_rom(a.game)
    steps = _macro(a.macro)
    frames = max(a.frames or 0, total_frames(steps), 1)
    start = state_path(a.game, a.from_state) if a.from_state else None
    dest = states_dir(a.game) / f"{slugify(a.name)}.mss"
    run_dir = new_run_dir("state", f"{a.game}-{a.name}")
    job = Job(frames=frames, state=start, macro=steps, capture_every=max(1, frames // 16), save_end=dest)
    r = run_job(rom, job, run_dir, rom_image=load_rom(rom))
    media = postprocess_run(run_dir, title=f"{a.game}: a caminho do state '{a.name}'", video=False)
    write_json(dest.with_suffix(".json"), {"created": now_iso(), "how": f"fab state boot (from={a.from_state or 'power-on'}, frames={frames})",
                                           "macro": a.macro, "note": a.note or "", "preview": media.get("sheets", [None])[0]})
    out({"state": rel(dest), "frames": r["frames_run"], "preview_sheet": media.get("sheets"),
         "check": "abra a folha de pré-visualização e confirme que o último frame mostra o momento certo"})


def _expand_pokes(specs, frames: int) -> list:
    """Aceita "60:…", "*:…" (todos os frames medidos) ou "10-20:…" (intervalo)."""
    from .emu import Poke
    out = []
    for spec in specs or []:
        head, sep, rest = spec.partition(":")
        if not sep:
            raise FabError(f"poke inválido: {spec!r}", "formato FRAME:ENDEREÇO=VALOR (FRAME pode ser * ou A-B)")
        if head == "*":
            quadros = range(frames)
        elif "-" in head:
            a, _, b = head.partition("-")
            try:
                quadros = range(int(a), int(b) + 1)
            except ValueError:
                raise FabError(f"poke inválido: {spec!r}", "intervalo A-B com inteiros")
        else:
            quadros = [int(head)]
        for f in quadros:
            out.append(Poke.from_spec(f"{f}:{rest}"))
    return out


def cmd_run(a):
    from .emu import Job, Probe, Watch, read_trace, run_job, new_run_dir
    from .game import clean_rom, state_path
    from .investigate import _macro
    from .macro import total_frames
    from .media import postprocess_run, trace_plot
    from .mods import load_mod
    from .paths import BUILD
    from .rom import load_rom, parse_addr
    if a.mod:
        mod = load_mod(a.mod)
        rom = BUILD / mod["id"] / f"{mod['id']}.sfc"
        if not rom.exists():
            raise FabError(f"ROM do mod ainda não montada: {rom}", f"rode `fab build mods/{mod['id']}`")
    else:
        rom = Path(a.rom) if a.rom else clean_rom(a.game)
    steps = _macro(a.macro)
    frames = max(a.frames or 0, total_frames(steps), 1)
    probes = []
    for p in a.probe or []:
        kind, _, addr = p.partition(":")
        probes.append(Probe(kind, parse_addr(addr), max_hits=a.probe_max or 500))
    job = Job(frames=frames, state=state_path(a.game, a.state) if a.state else None, macro=steps,
              watches=[Watch.from_spec(w) for w in a.watch or []], probes=probes,
              pokes=_expand_pokes(a.poke, frames),
              capture_every=a.every, warmup=a.warmup or 0, wram_every=a.wram_every or 0)
    run_dir = new_run_dir("run", a.label or a.game)
    r = run_job(rom, job, run_dir, rom_image=load_rom(rom))
    media = postprocess_run(run_dir, title=a.label or f"{a.game} run", video=not a.no_video)
    tr = read_trace(run_dir)
    res = {"run": rel(run_dir), "status": r["status"], "frames": r["frames_run"], "media": media}
    if a.watch:
        res["trace_plot"] = rel(trace_plot(tr, run_dir / "trace.png", a.label or a.game))
    if probes:
        res["probe_hits"] = r["probe_hits"]
        res["probes_file"] = rel(run_dir / "probes.jsonl")
    out(res)


def _rom_for(a):
    """ROM de trabalho de um comando: --mod (montada), --rom (arquivo) ou a base limpa do jogo."""
    from .game import clean_rom
    from .mods import load_mod
    from .paths import BUILD
    if getattr(a, "mod", None):
        mod = load_mod(a.mod)
        rom = BUILD / mod["id"] / f"{mod['id']}.sfc"
        if not rom.exists():
            raise FabError(f"ROM do mod ainda não montada: {rom}", f"rode `fab build mods/{mod['id']}`")
        return rom
    return Path(a.rom) if getattr(a, "rom", None) else clean_rom(a.game)


def _frames_arg(text: str | None, default: list[int]) -> list[int]:
    if not text:
        return default
    out = []
    for part in str(text).split(","):
        part = part.strip()
        if "-" in part:
            lo, _, hi = part.partition("-")
            step = 1
            if ":" in hi:
                hi, _, st = hi.partition(":")
                step = int(st)
            out.extend(range(int(lo), int(hi) + 1, step))
        elif part:
            out.append(int(part))
    return out


def cmd_sprite(a):
    from . import sprites
    from .game import state_path
    from .investigate import _macro
    from .paths import RUNS
    from .rom import load_rom
    from .util import slugify, stamp
    if a.sprite_cmd == "snap":
        rom = _rom_for(a)
        img = load_rom(rom)
        frames = _frames_arg(a.frames, [60])
        label = a.label or (a.state or "power-on")
        probes = []
        if getattr(a, "engine", False):
            from .cels import CelEngine
            from .game import load_game
            probes = [CelEngine.from_game(load_game(a.game)).probe_obj(max_hits=20 * len(frames) + 500)]
        out_dir = RUNS / f"{stamp()}-snap-{slugify(a.game)}-{slugify(label)}"
        cap = sprites.capture(a.game, out_dir, rom=rom, state=state_path(a.game, a.state) if a.state else None,
                              macro=_macro(a.macro), frames=frames, warmup=a.warmup or 0, label=label, rom_image=img,
                              probes=probes)
        res = {"captura": rel(cap.dir), "frames": []}
        for f in (frames if len(frames) <= a.reports else frames[:: max(1, len(frames) // a.reports)][:a.reports]):
            r = sprites.snap_report(cap, f, rom_data=img.data, max_objects=a.objects)
            res["frames"].append({
                "frame": f, "olhe": [r["arquivos"]["overview"], r["arquivos"]["bg"]] +
                                    [o["imagens"][1] for o in r["objetos"][:2]],
                "report": r["report"],
                "concordancia": r["concordancia"]["fracao"] if r["concordancia"] else None,
                "sprites": [f"{o['objeto']}: paleta OAM {o['paleta_oam']} = CGRAM {o['paleta_cgram']}, {o['pixeis']} px"
                            for o in r["objetos"]],
                "areas_bg": [f"B{a['area_bg']}: paleta CGRAM {a['paleta_cgram']}, {a['pixeis']} px" for a in r["areas_bg"]]})
        res["proximo"] = ("abra overview.png (sprites numerados) e bg.png (áreas de BG B1, B2…); depois objN-indices.png "
                          "ou bgN-indices.png (um painel por índice) e o report.md (de onde vem cada paleta). "
                          "Guia passo a passo: skill snes-sprite-paint")
        out(res)
    elif a.sprite_cmd in ("regions", "label", "census"):
        _sprite_parts(a)
    elif a.sprite_cmd == "marks":
        _sprite_marks(a)
    elif a.sprite_cmd == "tiles":
        from .util import write_json
        cap = sprites.load_capture(Path(a.capture))
        fd, o = _pick_object(cap, int(a.frame) if a.frame else None, a.object)
        img = load_rom(Path(cap.meta["rom"]))
        idx = _indices_arg(a.indices) if a.indices else None
        tiles = sprites.object_tiles(fd, o, idx)
        for t in tiles:
            t["rom"] = sprites.find_raw_tile(img.data, t["bytes"])
        highlight = None
        if a.part and a.store:
            from . import parts
            store = parts.PartStore(Path(a.store))
            highlight = {h: set(int(p) for p in pxs) for h, pxs in store.data["parts"].get(a.part, {}).items()}
        colors16 = [int(fd.colors[16 * o.cgram_palette + i]) for i in range(16)]
        out_dir = cap.dir / f"f{fd.frame:05d}"
        out_dir.mkdir(parents=True, exist_ok=True)
        png = out_dir / f"tiles-obj{o.number}.png"
        sprites.tiles_sheet(tiles, colors16, f"tiles do sprite {o.number} (frame {fd.frame}) · cor real · "
                            + ("magenta = píxeis da peça " + a.part if highlight else "origem na ROM se o desenho é cru"),
                            highlight).save(png)
        crus = sum(1 for t in tiles if t["rom"])
        res = {"imagem": rel(png), "tiles": len(tiles), "crus_na_rom": crus,
               "lista": [{"T": n + 1, "vram": f"${t['vram']:04X}", "hash": t["hash"], "pixeis": t["pixeis"],
                          "rom": [f"0x{h:06X}" for h in t["rom"]]} for n, t in enumerate(tiles)],
               "leitura": ("desenho CRU na ROM: dá para trocar índices dentro dos tiles com `fab paint remap`" if crus == len(tiles)
                           else "parte dos tiles não está crua na ROM (compressão): `fab ppu dma` mostra de onde vêm; "
                                "mudar o desenho deles exige o codec do jogo")}
        write_json(out_dir / f"tiles-obj{o.number}.json", res)
        out(res)
    elif a.sprite_cmd == "report":
        cap = sprites.load_capture(Path(a.capture))
        img = load_rom(Path(cap.meta["rom"]))
        frames = _frames_arg(a.frame, sorted(cap.frames)[:1])
        res = []
        for f in frames:
            r = sprites.snap_report(cap, f, rom_data=img.data, max_objects=a.objects)
            res.append({"frame": f, "report": r["report"], "overview": r["arquivos"]["overview"],
                        "objetos": [f"{o['objeto']}: paleta OAM {o['paleta_oam']}, {o['pixeis']} px" for o in r["objetos"]]})
        out(res)


def _sprite_parts(a):
    """fab sprite regions | label | census — peças que partilham índices de cor."""
    import numpy as np

    from . import parts, sprites
    from .util import write_json
    store = parts.PartStore(Path(a.store)) if getattr(a, "store", None) else None
    indices = _indices_arg(a.indices) if getattr(a, "indices", None) else None
    if a.sprite_cmd == "regions":
        cap = sprites.load_capture(Path(a.capture))
        fd, o = _pick_object(cap, int(a.frame) if a.frame else None, a.object)
        regs = parts.regions(fd, o.palette, indices, o)
        labels = None
        if store and store.data["parts"]:
            m = parts.target_mask(fd, o.palette, indices, o)
            lab, names = parts.classify(fd, store, m)
            labels = {}
            for n, r in enumerate(regs, 1):
                vals = {names[int(v)] for v in lab[r[:, 0], r[:, 1]] if v >= 0}
                labels[n] = "/".join(sorted(vals)) if vals else "?"
        box = sprites._crop_box(o, fd.real.shape, 4)
        out_dir = cap.dir / f"f{fd.frame:05d}"
        out_dir.mkdir(parents=True, exist_ok=True)
        name = f"regioes-obj{o.number}-{'-'.join(map(str, indices))}"
        parts.regions_image(fd, regs, box, f"objeto {o.number} · índices {a.indices} · frame {fd.frame} · "
                            f"diga quais NÚMEROS são a peça", labels).save(out_dir / f"{name}.png")
        info = {"frame": fd.frame, "objeto": o.number, "paleta_oam": o.palette, "indices": indices,
                "regioes": [{"n": n, "pixeis": len(r), "caixa": [int(r[:, 1].min()), int(r[:, 0].min()),
                                                                  int(r[:, 1].max()), int(r[:, 0].max())],
                             "rotulo": (labels or {}).get(n)} for n, r in enumerate(regs, 1)],
                "imagem": rel(out_dir / f"{name}.png"),
                "proximo": f"fab sprite label {rel(cap.dir)} --object {o.number} --indices {a.indices} --frame {fd.frame} "
                           f"--regions <números> --part <nome> [--rest <outra>] --store mods/<id>/parts.json"}
        write_json(out_dir / f"{name}.json", info)
        out(info)
    elif a.sprite_cmd == "label":
        if store is None:
            raise FabError("falta --store", "ex.: --store mods/<id>/parts.json")
        if a.pending:
            if a.rest:
                raise FabError("--rest não vale com --pending (rotularia pendentes que ninguém olhou)",
                               "rode o label uma vez por peça: --items 2,3 --part luva; depois --items 1,4 --part cabelo")
            cdir = Path(a.pending)
            cen = json.loads((cdir / "census.json").read_text(encoding="utf-8"))
            cap = sprites.load_capture(cdir)
            items = {it["n"]: it for it in cen["pendentes"]}
            chosen = _frames_arg(a.items, [])
            if not chosen or any(n not in items for n in chosen):
                raise FabError(f"itens {a.items!r} inválidos", f"os pendentes vão de 1 a {len(items)} (folhas do census)")
            done = {}
            for n in chosen:
                it = items[n]
                fd = cap.frame(it["frame"])
                new, conf = store.add(a.part, parts.pixel_keys(fd, np.array(it["pixeis"])))
                done[n] = {"peca": a.part, "novos": new, "conflitos": conf}
            store.save(f"pendentes de {rel(cdir)}: {a.items} = {a.part}")
            out({"rotulados": done, "loja": rel(store.path), "pecas": store.stats(),
                 "proximo": f"rotule as outras peças do mesmo jeito; depois refaça: fab sprite census {cap.meta['game']} "
                            f"--store {rel(store.path)} --target <peça> --capture {rel(cdir)}"})
            return
        cap = sprites.load_capture(Path(a.capture))
        fd, o = _pick_object(cap, int(a.frame) if a.frame else None, a.object)
        regs = parts.regions(fd, o.palette, indices, o)
        chosen = _frames_arg(a.regions, [])
        if any(not 1 <= n <= len(regs) for n in chosen):
            raise FabError(f"regiões {chosen} fora de 1-{len(regs)}", "veja a imagem do `fab sprite regions`")
        store.data.setdefault("indices", indices)
        store.data.setdefault("palette", o.palette)
        res = {}
        for n, r in enumerate(regs, 1):
            part = a.part if n in chosen else a.rest
            if not part:
                continue
            new, conf = store.add(part, parts.pixel_keys(fd, r))
            res[n] = {"peca": part, "pixeis": len(r), "novos": new, "conflitos": conf}
        store.save(f"{rel(cap.dir)} f{fd.frame} obj {o.number}: regiões {a.regions} = {a.part}"
                   + (f", resto = {a.rest}" if a.rest else ""))
        out({"rotulados": res, "loja": rel(store.path), "pecas": store.stats(),
             "proximo": "fab sprite census … (mede a cobertura em muitos frames e mostra as regiões pendentes)"})
    elif a.sprite_cmd == "census":
        from .game import state_path
        from .investigate import _macro
        from .paths import RUNS
        from .rom import load_rom
        from .util import slugify, stamp
        if store is None or not store.data["parts"]:
            raise FabError("a loja de rótulos está vazia", "rotule primeiro com `fab sprite regions` + `fab sprite label`")
        if a.target not in store.data["parts"]:
            raise FabError(f"peça {a.target!r} não existe na loja", f"peças: {sorted(store.data['parts'])}")
        palette = a.palette if a.palette is not None else store.data.get("palette")
        indices = indices or store.data.get("indices")
        if palette is None or not indices:
            raise FabError("diga --palette (paleta OAM do objeto) e --indices")
        rom = _rom_for(a)
        img = load_rom(rom)
        frames = _frames_arg(a.frames, list(range(0, 300, 3)))
        cdir = Path(a.capture) if a.capture else RUNS / f"{stamp()}-census-{slugify(a.game)}-{slugify(a.target)}"
        if a.capture and (cdir / "capture.json").exists():
            cap = sprites.load_capture(cdir)
        else:
            probes = []
            if a.engine:          # grava também a sonda do motor de cels (para `fab sprite marks`)
                from .cels import CelEngine
                from .game import load_game
                probes = [CelEngine.from_game(load_game(a.game)).probe_obj(max_hits=20 * len(frames) + 500)]
            cap = sprites.capture(a.game, cdir, rom=rom, state=state_path(a.game, a.state) if a.state else None,
                                  macro=_macro(a.macro), frames=frames, warmup=a.warmup or 0, label="census",
                                  rom_image=img, with_wram=False, probes=probes)
        fds = [cap.frames[f] for f in sorted(cap.frames)]
        c = parts.census(fds, store, int(palette), indices, a.target)
        pend = c["pendentes"]
        sheets = []
        for s0 in range(0, min(len(pend), 48), 12):
            pth = cdir / f"pendentes-{s0 // 12 + 1:02d}.png"
            parts.pending_sheet(pend[s0:s0 + 12], f"regiões SEM rótulo {s0 + 1}-{min(s0 + 12, len(pend))} de {len(pend)} · "
                                f"diga os NÚMEROS que são '{a.target}'", start=s0 + 1).save(pth)
            sheets.append(rel(pth))
        mixed_png = None
        if c["misturados"]:
            mixed_png = cdir / "sprites-misturados.png"
            parts.mixed_sheet(c["misturados"], store, int(palette), indices, a.target,
                              "sprites com as DUAS peças (não se separam trocando a paleta do sprite)").save(mixed_png)
        summary = parts.summarize(c)
        data = {"resumo": summary, "frames": c["frames"], "pecas": c["pecas"], "folhas_pendentes": sheets,
                "sprites_misturados": rel(mixed_png) if mixed_png else None,
                "pendentes": [{"n": n, "frame": it["fd"].frame, "vezes": it["vezes"], "pixeis": it["comp"].tolist()}
                              for n, it in enumerate(pend, 1)]}
        write_json(cdir / "census.json", data)
        res = {"captura": rel(cdir), "resumo": summary, "folhas_pendentes": sheets, "sprites_misturados": data["sprites_misturados"]}
        if pend:
            res["proximo"] = (f"olhe {sheets[0]} e rode, uma vez por peça: fab sprite label --pending {rel(cdir)} "
                              f"--items <números> --part <peça> --store {rel(store.path)}  (na dúvida, NÃO rotule: fica "
                              f"pendente); depois repita o census com --capture {rel(cdir)}")
        out(res)


def cmd_ai(a):
    """fab ai export|import|roundtrip — tilesheet EXPANDIDA para o Nano Banana editar + mapa JSON + re-importação."""
    from . import aisheet
    from .util import write_json
    if a.ai_cmd == "export":
        frames = _frames_arg(a.frames, None) if a.frames else None
        out_dir = Path(a.out)
        engine, rom = None, None
        if not getattr(a, "no_engine", False) and a.game:
            try:
                from .cels import CelEngine
                from .game import clean_rom, load_game
                from .rom import load_rom
                engine = CelEngine.from_game(load_game(a.game))
                rom = load_rom(clean_rom(a.game))
            except Exception:
                engine = None            # jogo sem motor de cels: exporta sem o filtro
        poses, notes, pal = aisheet.collect_poses([Path(c) for c in a.capture], palette=a.palette, object_no=a.object,
                                                  frames=frames, engine=engine, rom=rom)
        if not poses:
            raise FabError("nenhuma pose do alvo nas capturas",
                           "confira --palette (paleta OAM) / --object e --frames; veja overview.png do `fab sprite snap`")
        res = aisheet.export_sheet(poses, pal["cores"], out_dir, a.name, bloco=a.bloco, max_px=a.max, cols=a.cols,
                                   gap=a.gap, fundo=a.fundo, jogo=a.game or "", mudanca=a.mudanca or "")
        res["paleta_cgram"] = pal["cgram"]
        res["frames_varridos"] = len(notes)
        res["frames_sem_alvo"] = sum(1 for n in notes if "erro" in n)
        res["mismatch_dono"] = sum(int(n.get("mismatch_dono", 0)) for n in notes)
        res["entradas_excluidas_pela_lista_de_cels"] = sum(int(n.get("excluidas_pela_lista", 0)) for n in notes)
        res["filtro_de_cels"] = bool(engine)
        write_json(out_dir / "collect.json", {"notas": notes, "paleta": {"oam": pal["oam"], "cgram": pal["cgram"]}})
        out(res)
    elif a.ai_cmd == "import":
        mapa = aisheet.load_map(Path(a.map))
        res = aisheet.import_sheet(mapa, Path(a.image), Path(a.out), limpar=a.limpar)
        if a.mod:
            import json as _json
            plano = _json.loads((Path(a.out) / "plan.json").read_text(encoding="utf-8"))
            if not a.name or not a.evidence:
                raise FabError("--mod precisa de --name e --evidence", "ex.: --name gi-ia --evidence \"plan.json do export\"")
            res["aplicado"] = aisheet.apply_plan(Path(a.mod), plano, a.name, a.evidence)
        out(res)
    elif a.ai_cmd == "roundtrip":
        mapa = aisheet.load_map(Path(a.map))
        out_dir = Path(a.out) if a.out else Path(mapa["_dir"]) / "roundtrip"
        out(aisheet.roundtrip(mapa, out_dir))


def cmd_gfx(a):
    """fab gfx dump|override|check — tileset de qualquer jogo capturado na VRAM e override de gráfico comprimido."""
    if a.gfx_cmd == "override":
        return _gfx_override(a)
    if a.gfx_cmd == "check":
        return _gfx_check(a)
    from . import gfx
    from .emu import Job, new_run_dir, read_ppu, run_job
    from .game import state_path
    from .investigate import _macro
    from .macro import total_frames
    from .rom import load_rom
    from .util import write_json
    rom = _rom_for(a)
    img = load_rom(rom)
    steps = _macro(a.macro)
    frames = max(a.frames, total_frames(steps), 2)
    out_dir = new_run_dir("gfx", a.label or a.game)
    uploads, obj, finals = [], [], []
    for n, st in enumerate(a.state or [None]):
        d = out_dir / f"run-{n + 1}"
        run_job(rom, Job(frames=frames, state=state_path(a.game, st) if st else None, macro=steps, capture_every=0,
                         vram_uploads=True, ppu_frames=[frames - 1]), d, rom_image=img)
        ups = gfx.read_uploads(d)
        for u in ups:
            u["cenario"] = st or "power-on"
        uploads += ups
        snaps = read_ppu(d)
        if snaps:
            last = snaps[max(snaps)]
            obj = obj or gfx.obj_regions(last.meta)
            finals.append((last.frame, last.vram, gfx.tilemap_regions(last.meta)))
        (d / "ppu.bin").unlink(missing_ok=True)      # vram_uploads.bin fica: é a base do `fab gfx override`
    tiles = gfx.collect(uploads, img, a.bpp, obj)
    for fr, vram, maps in finals:                 # o que já estava na VRAM (carregado antes do state) também conta
        gfx.add_vram_snapshot(tiles, vram, fr, a.bpp, obj, maps)
    if not tiles:
        raise FabError("nenhum gráfico na VRAM nesses cenários", "confira o state/macro (tela preta?)")
    gfx.find_raw(tiles, img)
    title = f"{a.game} · {', '.join(a.state or ['power-on'])} · {frames} frames"
    summary = gfx.report(tiles, uploads, out_dir, a.bpp, title)
    summary.update({"game": a.game, "bpp": a.bpp,
                    "cenarios": {"states": a.state or [], "macro": a.macro, "frames": frames}})
    write_json(out_dir / "tileset.json", summary)
    summary["proximo"] = ("abra as folhas tiles-NN.png (verde = cru na ROM: `fab paint remap`/`fab gfx override` viram "
                          "patch de dados; laranja = comprimido por chip, azul = montado na WRAM: `fab gfx override "
                          f"<mod> --dump {rel(out_dir)} --tiles <nºs> --map a:b` serve o desenho editado sem codec)")
    out({"dir": rel(out_dir), **summary})


def _gfx_override(a):
    """fab gfx override — muda o desenho de gráfico comprimido (qualquer formato): hook no DMA serve a cópia editada."""
    from . import gfxoverride as go
    from .game import clean_rom
    from .mods import load_mod
    from .paint import apply_paint
    from .rom import load_rom
    mod = load_mod(Path(a.mod))
    mod_dir = Path(mod["_dir"])
    dump = go.load_dump(Path(a.dump))
    if dump["meta"].get("game") not in (None, mod["game"]):
        raise FabError(f"o dump é do jogo {dump['meta']['game']!r} e o mod é de {mod['game']!r}")
    rom = load_rom(clean_rom(mod["game"]))
    res = {}
    if a.tiles:
        if not a.map or not a.name:
            raise FabError("--tiles precisa de --map e --name", "ex.: --tiles 12,13 --map 14:9,15:12 --name luvas --evidence …")
        hashes = go.parse_selection(a.tiles, dump["index"])
        res["edicao"] = go.add_edits(mod_dir, dump, hashes, go.parse_map(a.map, dump["bpp"]), a.name, a.evidence or "", rom)
        if res["edicao"]["crus_na_rom"]:
            res["paint"] = apply_paint(mod_dir)          # desenho cru: patch de dados direto
    from .paint import _load_spec
    if _load_spec(mod_dir).get("vram_tiles"):
        res["override"] = go.override(mod_dir, dump, rom, chip_disarm=go.parse_disarm(a.chip_disarm),
                                      data_at=int(a.data_at, 0) if a.data_at else None,
                                      data_evidence=a.data_evidence or "", expand=a.expand)
    elif not a.tiles:
        raise FabError("nada a fazer: o paint.json não tem 'vram_tiles'", "passe --tiles/--map/--name")
    res["proximo"] = (f"fab build {rel(mod_dir)}  →  fab gfx check {rel(mod_dir)} --dump {rel(dump['dir'])}"
                      "  (sprite: também `fab paint check`)")
    out(res)


def _gfx_check(a):
    """fab gfx check — os cenários do dump na ROM do mod: o desenho editado chegou na VRAM e nada mais mudou."""
    from . import gfxoverride as go
    from .emu import new_run_dir
    from .mods import load_mod
    from .paths import BUILD
    mod = load_mod(Path(a.mod))
    rom_mod = BUILD / mod["id"] / f"{mod['id']}.sfc"
    if not rom_mod.exists():
        raise FabError(f"ROM do mod ainda não montada: {rel(rom_mod)}", f"rode `fab build {rel(Path(mod['_dir']))}`")
    dump = go.load_dump(Path(a.dump))
    out_dir = new_run_dir("gfxcheck", mod["id"])
    res = go.check(Path(mod["_dir"]), dump, rom_mod, out_dir)
    out({"dir": rel(out_dir), **res})


def cmd_ppu(a):
    """fab ppu dma — de onde vêm paleta, OAM e gráficos (qualquer ROM)."""
    from . import dma
    from .emu import Job, new_run_dir, read_ppu, run_job
    from .game import state_path
    from .investigate import _macro
    from .macro import total_frames
    from .rom import load_rom
    from .util import write_json
    rom = _rom_for(a)
    img = load_rom(rom)
    steps = _macro(a.macro)
    frames = max(a.frames, total_frames(steps), 2)
    out_dir = new_run_dir("dma", a.label or a.game)
    job = Job(frames=frames, state=state_path(a.game, a.state) if a.state else None, macro=steps, capture_every=0,
              dma_log=True, ppu_every=1 if a.vram_check else 0)
    run_job(rom, job, out_dir, rom_image=img)
    rep = dma.summarize(dma.read_dma(out_dir), img, read_ppu(out_dir) if a.vram_check else None)
    write_json(out_dir / "dma.json", rep)
    for big in ("ppu.bin",):
        (out_dir / big).unlink(missing_ok=True)
    rows = rep["transferencias"]
    out({"run": rel(out_dir), "resumo": rep["resumo"], "eventos": rep["eventos"],
         "transferencias": rows[:a.limit], "mais": max(0, len(rows) - a.limit)})


def _paint_oam_mirror(a):
    """fab paint oam-mirror — gera o mecanismo de nível 2 a partir do log de DMA e do censo (qualquer jogo)."""
    from . import oamhook
    from .game import clean_rom
    from .mods import load_mod
    from .paint import PAINT_JSON, _load_spec
    from .ppu import fmt_color, parse_color
    from .rom import load_rom, parse_addr
    from .util import write_json
    mod = load_mod(Path(a.mod))
    mod_dir = Path(mod["_dir"])
    rom = load_rom(clean_rom(mod["game"]))
    shadow = parse_addr(a.oam_shadow) if a.oam_shadow else None
    trigger = parse_addr(a.trigger) if a.trigger else None
    flags = a.flags
    buffer = None if a.buffer in (None, "none") else parse_addr(a.buffer)
    if a.from_dma:
        rep = json.loads((Path(a.from_dma) / "dma.json").read_text(encoding="utf-8"))
        oam = max((r for r in rep["transferencias"] if r["destino"] == "OAM" and r["tipo"] == "dma"),
                  key=lambda r: r["vezes"], default=None)
        if oam is None:
            raise FabError("o log de DMA não tem DMA para o OAM", "rode `fab ppu dma` num trecho com sprites")
        shadow = shadow or parse_addr(oam["fonte"])
        trigger = trigger or parse_addr(oam["dispara_pc_seguinte"])
        flags = flags or oam["m/x"]
        pal = [r for r in rep["transferencias"] if r["destino"] == "CGRAM" and r["tipo"] == "dma" and r["fonte_tipo"] == "WRAM"
               and r["bytes"] >= 256]
        if a.buffer is None and pal:
            buffer = parse_addr(max(pal, key=lambda r: r["vezes"])["fonte"])
    if shadow is None or trigger is None or not flags:
        raise FabError("faltam a sombra do OAM, a instrução do DMA ou o M/X", "passe --from-dma <run do fab ppu dma>")
    tiles = oamhook.parse_tiles(a.tiles) if a.tiles else []
    if a.from_census:
        cen = json.loads((Path(a.from_census) / "census.json").read_text(encoding="utf-8"))
        tiles += [int(t.lstrip("$"), 16) for t in cen["resumo"]["separabilidade"].get("tiles_seguros_lista", [])]
    colors = {}
    for pair in a.colors.split(","):
        i, _, c = pair.partition(":")
        colors[int(i)] = parse_color(c)
    m8, x8 = "m8" in flags, "x8" in flags
    asm, hijack = oamhook.generate(rom=rom, oam_shadow=shadow, trigger_next=trigger, m8=m8, x8=x8,
                                   src_palette=a.src_palette, mirror_palette=a.mirror_palette, tiles=sorted(set(tiles)),
                                   colors=colors, pal_buffer=buffer, evidence=a.evidence)
    res = oamhook.save(mod_dir, asm, hijack)
    spec = _load_spec(mod_dir)
    spec["oam_mirror"] = {"src": a.src_palette, "mirror": a.mirror_palette, "tiles": sorted(set(tiles)),
                          "colors": {str(k): fmt_color(v) for k, v in colors.items()}, "evidence": a.evidence}
    write_json(mod_dir / PAINT_JSON, spec)
    res["modo_paleta"] = f"buffer WRAM {buffer:06X}" if buffer is not None else "CGRAM direto (sem buffer de paletas)"
    res["tiles"] = len(set(tiles))
    res["proximo"] = (f"fab build {rel(mod_dir)} (confere hijack, M/X e o tamanho de cada instrução) → "
                      f"fab paint check {rel(mod_dir)} --state <state> --frames N")
    out(res)


def _sprite_marks(a):
    """fab sprite marks — marcas por cel (motor cel-list) a partir dos rótulos por conteúdo de um census."""
    from . import cels, parts, sprites
    from .game import load_game
    from .rom import load_rom
    from .util import write_json
    cap = sprites.load_capture(Path(a.capture))
    game = load_game(cap.meta["game"])
    engine = cels.CelEngine.from_game(game)
    rom = load_rom(Path(cap.meta["rom"]))
    store = parts.PartStore(Path(a.store))
    palette = a.palette if a.palette is not None else store.data.get("palette")
    indices = _indices_arg(a.indices) if a.indices else store.data.get("indices")
    if palette is None or not indices:
        raise FabError("diga --palette (paleta OAM do objeto) e --indices")
    res = cels.mark_votes(cap, store, int(palette), indices, a.target, engine, rom)
    if not res["votes"]:
        raise FabError("nenhum cel ligado aos sprites", "a captura tem a sonda do motor? refaça o census com --engine")
    marked, why = cels.decide(res["votes"], a.max_other_px)
    header = ["; GERADO por `fab sprite marks` — NÃO edite à mão (refaça o census/label e rode de novo).",
              f"; peça-alvo: {a.target} · paleta OAM {palette} · índices {indices}",
              *cels.report_lines(cap, res["votes"], marked, why, store)]
    text, region = cels.marks_asm(marked, rom, engine, header)
    out_path = Path(a.out)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    result = {"marks": rel(out_path), "cels_marcados": len(marked), "excluidos": dict(why),
              "listas": len({k[0] for k in marked}), "frames_sem_lista": res["frames_sem_lista"][:20],
              "data": region}
    if a.mod_json:
        mj = Path(a.mod_json)
        raw = json.loads(mj.read_text(encoding="utf-8"))
        keep = [d for d in raw.get("data", []) if d.get("source") != "marks" and "MARCAS" not in str(d.get("evidence", ""))]
        raw["data"] = keep + [region]
        write_json(mj, raw)
        result["mod_json"] = f"data[] atualizado em {rel(mj)} (a região antiga das marcas foi trocada)"
    out(result)


def _indices_arg(text: str) -> list[int]:
    idx = _frames_arg(text, [])
    if not idx or any(not 0 <= i <= 15 for i in idx):
        raise FabError(f"índices inválidos: {text!r}", "use 0-15, ex.: 9-13 ou 14,15")
    return idx


def _colors_arg(text: str) -> list[int]:
    from .ppu import parse_color
    try:
        return [parse_color(t) for t in str(text).replace(";", ",").replace(" ", ",").split(",") if t.strip()]
    except ValueError as e:
        raise FabError(f"cor inválida em {text!r}: {e}", 'use BGR555 ("$7E06,$7102") ou #rrggbb')


def _pick_object(cap, frame, number):
    from . import sprites
    fd = cap.frame(frame)
    objs = sprites.find_objects(fd)
    hit = next((o for o in objs if o.number == number), None)
    if hit is None:
        raise FabError(f"objeto {number} não existe no frame {fd.frame}",
                       f"objetos: {[o.number for o in objs]} (veja overview.png do `fab sprite snap`)")
    return fd, hit


def _pick_target(cap, frame, a):
    """O alvo da pintura: --object N (sprite), --bg N (área de BG) ou --cgram-palette P [--box x,y,w,h]."""
    from . import sprites
    chosen = [x for x in (a.object, a.bg, a.cgram_palette) if x is not None]
    if len(chosen) != 1:
        raise FabError("diga UM alvo", "--object N (sprite do overview.png) | --bg N (área B<N> do bg.png) | "
                                       "--cgram-palette P [--box x,y,w,h]")
    if a.object is not None:
        return _pick_object(cap, frame, a.object)
    fd = cap.frame(frame)
    if a.bg is not None:
        areas = sprites.find_bg_areas(fd)
        hit = next((t for t in areas if t.number == a.bg), None)
        if hit is None:
            raise FabError(f"área de BG B{a.bg} não existe no frame {fd.frame}",
                           f"áreas: {['B%d' % t.number for t in areas[:12]]} (veja bg.png do `fab sprite snap`)")
        return fd, hit
    box = tuple(int(v) for v in a.box.split(",")) if a.box else None
    return fd, sprites.palette_target(fd, a.cgram_palette, box)


def cmd_palette(a):
    from . import sprites
    from .paint import outline_colors, ramp_sheet
    from .ppu import fmt_color
    from .ramp import explicit_ramp, make_ramps, parse_target
    from .rom import asar_org, load_rom
    from .util import slugify, write_json
    if a.palette_cmd == "find":
        from .game import clean_rom
        img = load_rom(Path(a.rom) if a.rom else clean_rom(a.game))
        cols = _colors_arg(a.colors)
        hits = sprites._search_words(img.data, cols, limit=a.limit)
        out({"cores": [fmt_color(c) for c in cols], "achados": [
            {"pc": f"0x{h:06X}", "cpu": fmt_addr_safe(h, img.mapping), "org_asar": f"${asar_org(h, img.mapping):06X}"}
            for h in hits] or "nenhum (comprimida, calculada em código, ou os valores diferem)"})
        return
    cap = sprites.load_capture(Path(a.capture))
    frame = int(a.frame) if a.frame else None
    fd, o = _pick_target(cap, frame, a)
    indices = _indices_arg(a.indices)
    base = 16 * o.cgram_palette
    orig = [int(fd.colors[base + i]) for i in indices]
    outline = [] if a.outline == "none" else (
        [int(fd.colors[base + int(a.outline)])] if a.outline not in (None, "auto") else outline_colors(fd, o, indices))
    ramps = []
    if a.to:
        ramps += make_ramps(orig, parse_target(a.to), outline, [o.counts.get(i, 0) for i in indices])
    for spec in a.colors or []:
        cols = _colors_arg(spec)
        if len(cols) != len(indices):
            raise FabError(f"--colors tem {len(cols)} cores para {len(indices)} índices")
        ramps.append(explicit_ramp(orig, cols, f"manual {len(ramps) + 1}", "cores passadas à mão", outline))
    rom_img = load_rom(Path(cap.meta["rom"]))
    for spec in a.copy_from or []:
        src, _, rng = spec.partition(":")
        pc = int(src, 0)
        sidx = _indices_arg(rng) if rng else indices
        if len(sidx) != len(indices):
            raise FabError(f"--copy-from {spec}: {len(sidx)} cores para {len(indices)} índices")
        cols = [rom_img.data[pc + 2 * i] | (rom_img.data[pc + 2 * i + 1] << 8) for i in sidx]
        ramps.append(explicit_ramp(orig, [c & 0x7FFF for c in cols], f"cópia de 0x{pc:06X}",
                                   f"tons {sidx[0]}-{sidx[-1]} da paleta em 0x{pc:06X} (cópia fiel)", outline))
    if not ramps:
        raise FabError("diga a cor nova", '--to azul | --to "#3050ff" | --colors "$7E06,…" | --copy-from 0x1F1E40:9-13')
    slug = slugify(a.to or (a.copy_from or a.colors or ["manual"])[0])[:24]
    who = sprites.tag(o) if o.number else f"cgram{o.cgram_palette}"
    out_dir = cap.dir / f"f{fd.frame:05d}" / f"rampa-{who}-{slug}"
    out_dir.mkdir(parents=True, exist_ok=True)
    title = (f"alvo {who} (paleta CGRAM {o.cgram_palette}) · índices {indices[0]}-{indices[-1]} · contorno "
             f"{' '.join(fmt_color(c) for c in outline) or '—'} · frame {fd.frame}")
    ramp_sheet(fd, o, indices, orig, ramps, title).save(out_dir / "rampas.png")
    src = sprites.find_palette_sources([int(fd.colors[base + i]) for i in range(16)], rom_img.data,
                                       cap.meta.get("mapping", "lorom"), fd.wram)
    pal_pc = src["rom"][0]["pc"] if len(src["rom"]) == 1 and src["rom"][0]["indice_inicial"] == 0 else None
    result = {"imagem": rel(out_dir / "rampas.png"), "indices": indices, "original": [fmt_color(c) for c in orig],
              "contorno": [fmt_color(c) for c in outline], "candidatas": [r.to_dict() for r in ramps],
              "paleta_na_rom": src["rom"], "paleta_na_wram": src["wram"]}
    if pal_pc:
        result["proximo"] = (f'fab paint set mods/<id> --pc {pal_pc} --indices {a.indices} --colors "<cores da candidata>" '
                             f'--name <nome> --evidence "fab sprite snap {rel(cap.dir)} f{fd.frame} alvo {who}: '
                             f'paleta CGRAM {o.cgram_palette} ← ROM {pal_pc}"')
    else:
        result["proximo"] = ("a paleta não tem origem única na ROM (veja paleta_na_rom/paleta_na_wram): confirme qual "
                             "cópia o jogo lê com `fab probe reads` antes do `fab paint set`")
    write_json(out_dir / "rampas.json", result)
    out(result)


def fmt_addr_safe(pc: int, mapping: str) -> str | None:
    from .rom import fmt_addr, pc_to_snes
    try:
        return fmt_addr(pc_to_snes(pc, mapping))
    except FabError:
        return None


def cmd_paint(a):
    from .paint import apply_paint, set_palette
    if a.paint_cmd == "set":
        entry = set_palette(Path(a.mod), int(a.pc, 0), _indices_arg(a.indices), _colors_arg(a.colors), a.name,
                            a.evidence or "")
        res = apply_paint(Path(a.mod))
        res["gravado"] = entry
        out(res)
    elif a.paint_cmd == "apply":
        out(apply_paint(Path(a.mod)))
    elif a.paint_cmd == "oam-mirror":
        _paint_oam_mirror(a)
    elif a.paint_cmd == "remap":
        from . import sprites
        from .paint import remap_tiles
        cap = sprites.load_capture(Path(a.capture))
        fd, o = _pick_object(cap, int(a.frame) if a.frame else None, a.object)
        mapping = {}
        for pair in a.map.split(","):
            src, _, dst = pair.partition(":")
            mapping[int(src)] = int(dst)
        if any(not (0 <= k <= 15 and 0 <= v <= 15) for k, v in mapping.items()):
            raise FabError(f"mapa inválido: {a.map!r}", "pares índice:índice de 0 a 15, ex.: 14:9,15:12")
        only = None
        if a.part:
            from . import parts
            if not a.store:
                raise FabError("--part precisa de --store")
            store = parts.PartStore(Path(a.store))
            only = {h: set(int(p) for p in pxs) for h, pxs in store.data["parts"].get(a.part, {}).items()}
            if not only:
                raise FabError(f"a peça {a.part!r} não tem rótulos em {a.store}")
        res = remap_tiles(Path(a.mod), fd, o, mapping, a.name, a.evidence or "", only)
        if res["tiles_trocados"]:
            res["paint"] = apply_paint(Path(a.mod))
        out(res)
    elif a.paint_cmd == "check":
        from .game import state_path
        from .investigate import _macro
        from .mods import load_mod
        from .paint import check_paint
        from .paths import RUNS
        from .util import slugify, stamp
        mod = load_mod(Path(a.mod))
        out_dir = RUNS / f"{stamp()}-paintcheck-{slugify(mod['id'])}"
        r = check_paint(Path(a.mod), out_dir, state=state_path(mod["game"], a.state) if a.state else None,
                        macro=_macro(a.macro), frames=None if a.frames in (None, "auto") else _frames_arg(a.frames, []),
                        warmup=a.warmup or 0, max_frames=a.max_frames,
                        baseline_rom=Path(a.baseline_rom) if a.baseline_rom else None)
        out(r)
        return EXIT_OK if r["ok"] else EXIT_FAIL


PROBE_KINDS = {"writes": "write", "write": "write", "reads": "read", "read": "read", "exec": "exec"}


def _mod_label(mod_id: str, name: str) -> str:
    """Rótulo do código do mod (do build.json ATUAL) → endereço. Rótulos mudam de lugar a cada build:
    sondar um endereço velho dá 0 hits e parece que o código não roda."""
    from .mods import load_mod
    from .paths import BUILD
    from .rom import parse_addr
    try:
        parse_addr(name)
        return name
    except FabError:
        pass
    mod = load_mod(mod_id)
    bj = BUILD / mod["id"] / "build.json"
    if not bj.exists():
        raise FabError(f"o mod {mod['id']} ainda não foi montado", f"rode `fab build mods/{mod['id']}`")
    labels = json.loads(bj.read_text(encoding="utf-8")).get("labels", {})
    if name not in labels:
        raise FabError(f"rótulo {name!r} não existe no build atual de {mod['id']}", f"rótulos: {sorted(labels)[:30]}")
    return labels[name]


def cmd_probe(a):
    from .investigate import probe
    rom = Path(a.rom) if a.rom else None
    addr, end = a.addr, a.end
    if a.mod:
        rom = _rom_for(a)
        addr = _mod_label(a.mod, addr)
        end = _mod_label(a.mod, end) if end else None
    _evidence(probe(a.game, PROBE_KINDS[a.kind], addr, end, a.state, a.macro, a.frames, rom, a.max_hits))


def cmd_ram_search(a):
    from .investigate import ram_search
    out(ram_search(a.game, a.state, a.macro, a.frames, a.every, Path(a.rom) if a.rom else None))


def cmd_ram_query(a):
    from .investigate import ram_query
    r = ram_query(Path(a.run), a.changed, a.unchanged, a.increased, a.decreased, a.equals, a.word, a.limit, a.game)
    if "evidence_id" in r:
        _evidence(r)
    else:
        out(r)


def cmd_re(a):
    from . import ghidra
    from .investigate import cdl
    if a.re_cmd == "cdl":
        out(cdl(a.game, a.state, a.macro, a.frames))
    elif a.re_cmd == "analyze":
        out(ghidra.analyze(a.game))
    elif a.re_cmd == "funcs":
        _evidence(ghidra.q_funcs(a.game, a.limit, a.pattern))
    elif a.re_cmd == "func":
        _evidence(ghidra.q_func(a.game, a.addr))
    elif a.re_cmd == "xrefs":
        _evidence(ghidra.q_xrefs(a.game, a.addr))
    elif a.re_cmd == "search":
        _evidence(ghidra.q_search(a.game, a.regex, a.limit))
    elif a.re_cmd == "decompile":
        _evidence(ghidra.q_decompile(a.game, a.addrs))
    elif a.re_cmd == "evidence":
        from .evidence import find, ledger
        if a.id:
            rec = find(a.game, a.id)
            if not rec:
                raise FabError(f"evidência {a.id} não encontrada")
            _evidence(rec)
        else:
            for rec in ledger(a.game)[-a.limit:]:
                print(f"{rec['evidence_id']}  {rec['time']}  {rec['kind']:<12} {json.dumps(rec['query'], ensure_ascii=False)}")


def cmd_mod(a):
    from .mods import list_mods, new_mod
    if a.mod_cmd == "new":
        d = new_mod(a.id, a.game, a.title or "", a.goal or "")
        out({"mod": rel(d), "files": [rel(p) for p in sorted(d.iterdir())],
             "next": "preencha o mod.json (state, input, watch, checks) e patch.asm com evidências; depois `fab cycle run`"})
    else:
        out(list_mods())


def cmd_build(a):
    from .build import build_mod
    r = build_mod(Path(a.mod) if Path(a.mod).exists() else a.mod)
    keep = {k: r[k] for k in ("mod", "rom", "ok", "warnings", "leak_warning", "bps", "bps_size", "sha256")}
    keep["regions"] = r["regions"]
    keep["data"] = r.get("data", [])
    keep["labels"] = dict(list(r["labels"].items())[:40])
    if r.get("rom_expandida"):
        keep["rom_expandida"] = r["rom_expandida"]          # a ROM cresceu: quais emuladores a rodam
    out(keep)
    return EXIT_OK if r["ok"] else EXIT_FAIL


def cmd_cycle(a):
    from .cycle import ledger_status, record_verdict, run_cycle
    if a.cycle_cmd == "run":
        r = run_cycle(a.mod, a.note or "")
        brief = {k: r.get(k) for k in ("cycle", "status", "score", "prev_score", "verdict_auto", "checks_passed",
                                        "checks_total", "goal_met_by_checks", "visual_change", "report", "error")}
        brief["look_at"] = [p for s in r.get("scenarios", []) for p in
                            (s["compare"].get("compare_sheet"), s["compare"].get("trace_plot"))
                            if p]
        out(brief)
    elif a.cycle_cmd == "verdict":
        out(record_verdict(a.mod, a.cycle, a.verdict, a.notes or ""))
    else:
        out(ledger_status(a.mod))


def cmd_media(a):
    from .media import analyze_media
    from .paths import MEDIA_INBOX, RUNS
    from .util import slugify, stamp
    if a.media_cmd == "analyze":
        p = Path(a.path)
        dest = RUNS / "media" / f"{stamp()}-{slugify(p.stem)}"
        at = [float(x) for x in a.at.split(",")] if a.at else None
        out(analyze_media(p, dest, a.n, a.scene, at))
    elif a.media_cmd == "inbox":
        MEDIA_INBOX.mkdir(parents=True, exist_ok=True)
        done = RUNS / "media" / "inbox-processed.json"
        seen = json.loads(done.read_text()) if done.exists() else {}
        results = []
        for f in sorted(MEDIA_INBOX.iterdir()):
            if f.name.startswith(".") or f.name in seen:
                continue
            dest = RUNS / "media" / f"{stamp()}-{slugify(f.stem)}"
            try:
                r = analyze_media(f, dest, a.n, a.scene)
                seen[f.name] = r["out_dir"]
                results.append({"file": f.name, "out": r["out_dir"], "sheets": r.get("sheets")})
            except FabError as e:
                results.append({"file": f.name, "error": e.what})
        done.parent.mkdir(parents=True, exist_ok=True)
        done.write_text(json.dumps(seen, indent=1))
        out(results or "inbox sem arquivos novos (media/inbox/)")
    elif a.media_cmd == "compare":
        from .compare import compare_runs
        from .emu import read_trace
        A, B = Path(a.a), Path(a.b)
        ta = read_trace(A) if (A / "trace.csv").exists() else None
        tb = read_trace(B) if (B / "trace.csv").exists() else None
        dest = RUNS / "compare" / f"{stamp()}-{A.name[:20]}-vs-{B.name[:20]}"
        out(compare_runs(A, B, dest, a.title or "comparação", ta, tb))


def cmd_bps(a):
    from . import bps
    src = Path(a.rom).read_bytes()
    from .rom import SMC_HEADER
    if len(src) % 1024 == SMC_HEADER:
        src = src[SMC_HEADER:]
    Path(a.out).write_bytes(bps.apply(src, Path(a.patch).read_bytes()))
    out({"written": a.out})


def cmd_testbed(a):
    from .setup_tools import setup_testbed
    out(setup_testbed())


def cmd_selftest(a):
    import unittest
    from .paths import ROOT

    def flatten(suite):
        for t in suite:
            if isinstance(t, unittest.TestSuite):
                yield from flatten(t)
            else:
                yield t

    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    if a.quick:
        suite = unittest.TestSuite(t for t in flatten(suite) if "e2e" not in t.id())
    r = unittest.TextTestRunner(verbosity=2).run(suite)
    return EXIT_OK if r.wasSuccessful() else EXIT_FAIL


def cmd_memory(a):
    from . import memory
    if a.memory_cmd in ("dump", "restore"):
        for line in (memory.dump() if a.memory_cmd == "dump" else memory.restore(force=a.force)):
            out(line)
    else:
        state, detail = memory.dump_state()
        out(f"{state}: {detail}")
        return EXIT_OK if state == "ok" else EXIT_FAIL


# ── parser ────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fab", description="Fábrica de mods de SNES (ROM → evidência → patch → emulação → vídeo → veredito)")
    p.add_argument("--version", action="version", version=f"snesfab {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup", help="instala/configura o toolchain pinado (idempotente)")
    s.add_argument("--force", action="store_true")
    s.add_argument("--no-rea", action="store_true")
    s.add_argument("--no-testbed", action="store_true")
    s.set_defaults(fn=cmd_setup)

    s = sub.add_parser("doctor", help="verifica toolchain, harness headless e regras do repo")
    s.add_argument("--quick", action="store_true", help="sem smoke test no emulador")
    s.add_argument("--rea", action="store_true", help="inclui `rea doctor`")
    s.set_defaults(fn=cmd_doctor)

    rom = sub.add_parser("rom", help="registrar/inspecionar ROMs").add_subparsers(dest="rom_cmd", required=True)
    s = rom.add_parser("add", help="registra uma ROM (copia, remove cabeçalho SMC, detecta mapa, base limpa só leitura)")
    s.add_argument("path")
    s.add_argument("--id")
    s.add_argument("--force", action="store_true")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_rom_add)
    s = rom.add_parser("info")
    s.add_argument("game")
    s.set_defaults(fn=cmd_rom_info)
    s = rom.add_parser("list")
    s.set_defaults(fn=cmd_rom_list)

    s = sub.add_parser("addr", help="converte endereço SNES ↔ offset (--pc) e classifica (ROM/WRAM/MMIO)")
    s.add_argument("game")
    s.add_argument("value")
    s.add_argument("--pc", action="store_true", help="o valor é um offset no arquivo limpo")
    s.add_argument("--rom")
    s.set_defaults(fn=cmd_addr)

    s = sub.add_parser("disasm", help="desmontagem linear 65816 com rastreio de SEP/REP")
    s.add_argument("game")
    s.add_argument("addr")
    s.add_argument("--count", type=int, default=24)
    s.add_argument("--flags", help="ex.: m8,x16 (padrão m8,x8)")
    s.add_argument("--rom", help="outra ROM (ex.: build/<mod>/<mod>.sfc)")
    s.set_defaults(fn=cmd_disasm)

    s = sub.add_parser("play", help="abre o MesenCE (GUI) para jogar e gravar savestates (Shift+F1..)")
    s.add_argument("game")
    s.add_argument("--rom")
    s.set_defaults(fn=cmd_play)

    st = sub.add_parser("state", help="savestates do jogo").add_subparsers(dest="state_cmd", required=True)
    s = st.add_parser("list")
    s.add_argument("game")
    s.set_defaults(fn=cmd_state_list)
    s = st.add_parser("import", help="importa .mss (--file) ou slot do Mesen (--slot N)")
    s.add_argument("game")
    s.add_argument("name")
    s.add_argument("--file")
    s.add_argument("--slot", type=int)
    s.add_argument("--note")
    s.set_defaults(fn=cmd_state_import)
    s = st.add_parser("boot", help="cria um state headless: power-on (ou --from-state) + macro → grava no fim")
    s.add_argument("game")
    s.add_argument("name")
    s.add_argument("--macro", help="arquivo .txt ou texto inline com ';' separando linhas")
    s.add_argument("--frames", type=int)
    s.add_argument("--from-state")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_state_boot)

    s = sub.add_parser("run", help="roda um cenário headless e gera frames/vídeo/folha/traço")
    s.add_argument("game")
    s.add_argument("--state")
    s.add_argument("--macro")
    s.add_argument("--frames", type=int)
    s.add_argument("--watch", action="append", help="nome=7E:0096:2s (repetível)")
    s.add_argument("--probe", action="append", help="write:7E:007D | read:… | exec:80:A420 (repetível)")
    s.add_argument("--probe-max", type=int, help="máximo de hits guardados por sonda (padrão 500)")
    s.add_argument("--poke", action="append",
                   help="escrita num frame: 60:cgram:01D2:2=0x03E0 | 30:7E:06D2:2=0x1084 (repetível)")
    s.add_argument("--every", type=int, default=2, help="captura 1 frame a cada N (0 = sem frames)")
    s.add_argument("--warmup", type=int, default=0,
                   help="frames iniciais emulados sem medir (o state traz RAM/CGRAM velhas da ROM limpa)")
    s.add_argument("--wram-every", type=int)
    s.add_argument("--rom")
    s.add_argument("--mod", help="usa a ROM montada do mod")
    s.add_argument("--label")
    s.add_argument("--no-video", action="store_true")
    s.set_defaults(fn=cmd_run)

    spr = sub.add_parser("sprite", help="pintura de sprites: objetos numerados, índices de cor, origem das paletas"
                         ).add_subparsers(dest="sprite_cmd", required=True)
    s = spr.add_parser("snap", help="captura frames (real + falsa cor + snapshot do PPU) e gera imagens rotuladas + report.md")
    s.add_argument("game")
    s.add_argument("--state")
    s.add_argument("--macro")
    s.add_argument("--frames", help="ex.: 60 | 30,60,90 | 0-120:10 (padrão 60)")
    s.add_argument("--warmup", type=int, default=0)
    s.add_argument("--objects", type=int, default=6, help="quantos objetos ganham folhas próprias (os maiores)")
    s.add_argument("--reports", type=int, default=4, help="quantos frames ganham relatório completo")
    s.add_argument("--rom")
    s.add_argument("--mod", help="usa a ROM montada do mod")
    s.add_argument("--label")
    s.add_argument("--engine", action="store_true", help="grava também a sonda do motor de cels (filtro de efeitos "
                                                         "no `fab ai export`; exige sprite_engine no game.json)")
    s.set_defaults(fn=cmd_sprite)
    s = spr.add_parser("regions", help="regiões conexas de alguns índices num objeto, numeradas numa imagem")
    s.add_argument("capture")
    s.add_argument("--object", type=int, required=True)
    s.add_argument("--indices", required=True, help="ex.: 14,15")
    s.add_argument("--frame")
    s.add_argument("--store", help="parts.json: mostra o rótulo atual de cada região")
    s.set_defaults(fn=cmd_sprite)
    s = spr.add_parser("label", help="rótulo de peça por CONTEÚDO de tile (vale em qualquer pose que use o mesmo desenho)")
    s.add_argument("capture", nargs="?")
    s.add_argument("--object", type=int)
    s.add_argument("--indices")
    s.add_argument("--frame")
    s.add_argument("--regions", help="números das regiões que são a peça (do `fab sprite regions`)")
    s.add_argument("--pending", help="diretório de um `fab sprite census`: rotula os PENDENTES por número")
    s.add_argument("--items", help="com --pending: números dos pendentes que são a peça")
    s.add_argument("--part", required=True, help="nome da peça (ex.: luva)")
    s.add_argument("--rest", help="nome para as OUTRAS regiões (ex.: cabelo)")
    s.add_argument("--store", required=True, help="arquivo de rótulos, ex.: mods/<id>/parts.json")
    s.set_defaults(fn=cmd_sprite)
    s = spr.add_parser("census", help="cobertura dos rótulos em muitos frames + pendentes numerados + separabilidade por sprite")
    s.add_argument("game")
    s.add_argument("--store", required=True)
    s.add_argument("--target", required=True, help="a peça a pintar (ex.: luva)")
    s.add_argument("--palette", type=int, help="paleta OAM do objeto (padrão: a da loja)")
    s.add_argument("--indices")
    s.add_argument("--state")
    s.add_argument("--macro")
    s.add_argument("--frames", help="ex.: 0-600:3 (padrão 0-297:3)")
    s.add_argument("--warmup", type=int, default=0)
    s.add_argument("--capture", help="reusa (ou cria aqui) a captura do censo")
    s.add_argument("--engine", action="store_true", help="grava a sonda do motor de cels (game.json → sprite_engine)")
    s.add_argument("--rom")
    s.add_argument("--mod")
    s.set_defaults(fn=cmd_sprite)
    s = spr.add_parser("tiles", help="tiles 8x8 de um sprite (cor real, ampliados) e se o desenho está CRU na ROM")
    s.add_argument("capture")
    s.add_argument("--object", type=int, required=True)
    s.add_argument("--frame")
    s.add_argument("--indices", help="só tiles que têm estes índices (ex.: 14,15)")
    s.add_argument("--part", help="contorna os píxeis desta peça (rótulos da --store)")
    s.add_argument("--store")
    s.set_defaults(fn=cmd_sprite)
    s = spr.add_parser("marks", help="marcas por CEL (motor cel-list) a partir dos rótulos de um census com --engine")
    s.add_argument("capture", help="diretório do `fab sprite census --engine` (ROM LIMPA)")
    s.add_argument("--store", required=True)
    s.add_argument("--target", required=True)
    s.add_argument("--palette", type=int)
    s.add_argument("--indices")
    s.add_argument("--out", required=True, help="ex.: mods/<id>/marks.asm")
    s.add_argument("--mod-json", help="atualiza a região data[] das marcas neste mod.json")
    s.add_argument("--max-other-px", type=int, default=0,
                   help="cel MISTURADO entra se a outra peça tiver até N píxeis nele (padrão 0: nunca pinta a outra)")
    s.set_defaults(fn=cmd_sprite)
    s = spr.add_parser("report", help="refaz as imagens/relatório de uma captura existente (sem emular de novo)")
    s.add_argument("capture", help="diretório da captura (runs/…-snap-…)")
    s.add_argument("--frame", help="frame(s) da captura (padrão: o primeiro)")
    s.add_argument("--objects", type=int, default=6)
    s.set_defaults(fn=cmd_sprite)

    ai = sub.add_parser("ai", help="sprites para edição por IA (Nano Banana): exporta tilesheet expandida + mapa + "
                                   "prompt; re-importa a imagem devolvida e gera o plano de tiles"
                        ).add_subparsers(dest="ai_cmd", required=True)
    s = ai.add_parser("export", help="capturas → sheet.png (blocos N×N) + map.json + prompt.md + report.md")
    s.add_argument("--capture", action="append", required=True, help="dir de captura do `fab sprite snap` (repita)")
    s.add_argument("--palette", type=int, help="paleta OAM do alvo (ex.: 6 = Ken no SFA2)")
    s.add_argument("--object", type=int, help="nº do objeto na captura (alternativa a --palette)")
    s.add_argument("--frames", help="frames a usar (ex.: 0-300:3); padrão: todos")
    s.add_argument("--out", required=True, help="dir de saída (ex.: games/<jogo>/exports/<nome>)")
    s.add_argument("--name", required=True)
    s.add_argument("--game", default="", help="id do jogo (para o report)")
    s.add_argument("--bloco", type=int, help="px por píxel de arte (padrão: auto até --max)")
    s.add_argument("--max", type=int, default=1024, help="lado máximo da folha expandida (1024 = bucket 1K do Gemini)")
    s.add_argument("--cols", type=int, help="colunas da grelha de poses (padrão: auto)")
    s.add_argument("--gap", type=int, default=1, help="separação (px de arte) entre células")
    s.add_argument("--fundo", default="auto", help='cor de fundo = transparência; "auto" (padrão) CALCULA a cor '
                                                   'com máximo contraste à paleta; ou "#rrggbb" fora da paleta')
    s.add_argument("--mudanca", default="", help="texto da mudança para embutir no prompt")
    s.add_argument("--no-engine", action="store_true", help="não filtrar pela lista de cels do motor do jogo")
    s.set_defaults(fn=cmd_ai)
    s = ai.add_parser("import", help="imagem devolvida → re-quantização por bloco + limpeza + plano de tiles")
    s.add_argument("--map", required=True, help="map.json do export (ou o dir)")
    s.add_argument("--image", required=True, help="imagem devolvida pelo modelo (mesmo aspect ratio)")
    s.add_argument("--out", required=True)
    s.add_argument("--limpar", default="auto", choices=["auto", "nao"], help="auto = blocos sujos herdam a moda dos vizinhos limpos")
    s.add_argument("--mod", help="grava o plano no paint.json do mod (exige --name e --evidence)")
    s.add_argument("--name")
    s.add_argument("--evidence")
    s.set_defaults(fn=cmd_ai)
    s = ai.add_parser("roundtrip", help="prova o ciclo: identidade (0 mudanças) + perturbação (offset/blur)")
    s.add_argument("--map", required=True)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_ai)

    gx = sub.add_parser("gfx", help="gráficos: export do tileset capturado na VRAM (qualquer compressão)"
                        ).add_subparsers(dest="gfx_cmd", required=True)
    s = gx.add_parser("dump", help="grava cada upload para a VRAM nos cenários e exporta os tiles únicos + origem")
    s.add_argument("game")
    s.add_argument("--state", action="append", help="repetível: junta vários cenários (sem state = power-on)")
    s.add_argument("--macro")
    s.add_argument("--frames", type=int, default=600)
    s.add_argument("--bpp", type=int, choices=[2, 4, 8], default=4, help="como ler os tiles (sprites são sempre 4)")
    s.add_argument("--rom")
    s.add_argument("--mod")
    s.add_argument("--label")
    s.set_defaults(fn=cmd_gfx)
    s = gx.add_parser("override", help="muda o desenho de gráfico COMPRIMIDO (qualquer formato): o hook no disparo do "
                                       "DMA serve a cópia editada (crus na ROM viram patch de dados)")
    s.add_argument("mod")
    s.add_argument("--dump", required=True, help="diretório do `fab gfx dump` (runs/…-gfx-…)")
    s.add_argument("--tiles", help="nºs das folhas do dump (ex.: 12,13,40-45) ou hashes")
    s.add_argument("--map", help="troca de índices nesses tiles, pares origem:destino (ex.: 14:9,15:12)")
    s.add_argument("--name", help="nome da edição (paint.json)")
    s.add_argument("--evidence", help="de onde vêm os tiles e o mapa (obrigatório com --tiles)")
    s.add_argument("--chip-disarm", action="append",
                   help="ENDEREÇO=VALOR escrito no DMA redirecionado de fonte transformada por chip (da evidência)")
    s.add_argument("--expand", action="store_true",
                   help="ROM sem espaço: expande (expand_to) e põe tabela/cópias na área nova (S-DD1: acima de 4 MiB, "
                        "pela janela $F0-$FF); o resultado lista os emuladores que rodam a ROM expandida")
    s.add_argument("--data-at", help="offset (PC) para tabela/cópias em vez do espaço livre (com --data-evidence)")
    s.add_argument("--data-evidence", help="por que a região do --data-at está livre/sem uso")
    s.set_defaults(fn=cmd_gfx)
    s = gx.add_parser("check", help="roda os cenários do dump na ROM do mod e confere na VRAM o desenho editado")
    s.add_argument("mod")
    s.add_argument("--dump", required=True)
    s.set_defaults(fn=cmd_gfx)

    pp = sub.add_parser("ppu", help="memória de vídeo: log de DMA (de onde vêm paleta, OAM e gráficos)"
                        ).add_subparsers(dest="ppu_cmd", required=True)
    s = pp.add_parser("dma", help="cada DMA/HDMA do cenário: fonte (ROM/WRAM), destino (VRAM/OAM/CGRAM), quem dispara")
    s.add_argument("game")
    s.add_argument("--state")
    s.add_argument("--macro")
    s.add_argument("--frames", type=int, default=60)
    s.add_argument("--rom")
    s.add_argument("--mod")
    s.add_argument("--label")
    s.add_argument("--limit", type=int, default=30)
    s.add_argument("--no-vram-check", dest="vram_check", action="store_false",
                   help="não grava snapshots para conferir se os gráficos são crus (mais rápido)")
    s.set_defaults(fn=cmd_ppu)

    pal = sub.add_parser("palette", help="paletas: rampas que preservam o sombreado (com prévia) e busca na ROM"
                         ).add_subparsers(dest="palette_cmd", required=True)
    s = pal.add_parser("ramp", help="candidatas de cor para índices de um objeto + prévia exata sobre o frame")
    s.add_argument("capture", help="diretório do `fab sprite snap`")
    s.add_argument("--object", type=int, help="número do SPRITE no overview.png")
    s.add_argument("--bg", type=int, help="número da área de BG (B<N>) no bg.png")
    s.add_argument("--cgram-palette", type=int, help="linha de paleta da CGRAM (0-15), qualquer camada")
    s.add_argument("--box", help="com --cgram-palette: só os píxeis dentro de x,y,w,h")
    s.add_argument("--indices", required=True, help="ex.: 9-13 ou 14,15")
    s.add_argument("--to", help="cor-alvo: nome (azul, preto, rosa, verde-escuro…) ou #rrggbb ou $BGR555")
    s.add_argument("--colors", action="append", help="rampa explícita, uma cor por índice (repetível)")
    s.add_argument("--copy-from", action="append", help="PC[:i-j] de outra paleta na ROM (cópia fiel; repetível)")
    s.add_argument("--outline", help="auto (padrão) | none | índice do contorno")
    s.add_argument("--frame")
    s.set_defaults(fn=cmd_palette)
    s = pal.add_parser("find", help="procura uma sequência de cores BGR555 na ROM")
    s.add_argument("game")
    s.add_argument("--colors", required=True)
    s.add_argument("--rom")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(fn=cmd_palette)

    pt = sub.add_parser("paint", help="pintura declarativa: paint.json → paint.asm + data[] (sem calcular org à mão)"
                        ).add_subparsers(dest="paint_cmd", required=True)
    s = pt.add_parser("set", help="grava a troca de cores de uma paleta no paint.json e regenera o paint.asm")
    s.add_argument("mod")
    s.add_argument("--pc", required=True, help="offset da paleta (índice 0) no arquivo, ex.: 0x1F0260")
    s.add_argument("--indices", required=True)
    s.add_argument("--colors", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--evidence", required=True)
    s.set_defaults(fn=cmd_paint)
    s = pt.add_parser("remap", help="troca ÍNDICES dentro do desenho dos tiles de um sprite (gráfico cru na ROM)")
    s.add_argument("mod")
    s.add_argument("--capture", required=True)
    s.add_argument("--object", type=int, required=True)
    s.add_argument("--frame")
    s.add_argument("--map", required=True, help="pares origem:destino, ex.: 14:9,15:12")
    s.add_argument("--part", help="só nos píxeis desta peça (rótulos por conteúdo da --store)")
    s.add_argument("--store")
    s.add_argument("--name", required=True)
    s.add_argument("--evidence", required=True)
    s.set_defaults(fn=cmd_paint)
    s = pt.add_parser("oam-mirror", help="NÍVEL 2: hook antes do DMA do OAM + paleta-espelho por tabela de tiles (gera o .asm)")
    s.add_argument("mod")
    s.add_argument("--from-dma", help="run do `fab ppu dma` (tira dele a sombra do OAM, a instrução do DMA, o M/X e o buffer)")
    s.add_argument("--oam-shadow", help="sombra do OAM na WRAM (ex.: 7E:0200)")
    s.add_argument("--trigger", help="PC SEGUINTE à instrução que dispara o DMA do OAM (coluna dispara_pc_seguinte)")
    s.add_argument("--flags", help="M/X nesse ponto, ex.: m8,x16")
    s.add_argument("--buffer", help="buffer de paletas na WRAM (ex.: 7E:0500) ou none (escreve direto na CGRAM)")
    s.add_argument("--src-palette", type=int, required=True, help="paleta OAM do objeto (0-7)")
    s.add_argument("--mirror-palette", type=int, required=True, help="paleta OAM LIVRE (0-7) que vira o espelho")
    s.add_argument("--tiles", help="nºs de tile (ex.: $0C,$0E,0x120)")
    s.add_argument("--from-census", help="usa os 'tiles_seguros' de um `fab sprite census`")
    s.add_argument("--colors", required=True, help="índice:cor, ex.: 14:$2908,15:$1084")
    s.add_argument("--evidence", required=True)
    s.set_defaults(fn=cmd_paint)
    s = pt.add_parser("apply", help="regenera paint.asm e data[] a partir do paint.json")
    s.add_argument("mod")
    s.set_defaults(fn=cmd_paint)
    s = pt.add_parser("check", help="verifica por EFEITO: mod × base nos mesmos frames, píxel a píxel (imagem + veredito)")
    s.add_argument("mod")
    s.add_argument("--state")
    s.add_argument("--macro")
    s.add_argument("--frames", help="auto (padrão: logo depois de o jogo carregar as cores novas) ou ex.: 60,120")
    s.add_argument("--max-frames", type=int, default=600, help="limite da procura automática")
    s.add_argument("--warmup", type=int, default=0)
    s.add_argument("--baseline-rom", help="base alternativa (ex.: o mod montado com a pintura DESLIGADA)")
    s.set_defaults(fn=cmd_paint)

    s = sub.add_parser("probe", help="sonda dinâmica: quem escreve/lê um endereço ou o que executa nele (M/X reais)")
    s.add_argument("kind", choices=["writes", "reads", "exec", "write", "read"])
    s.add_argument("game")
    s.add_argument("addr")
    s.add_argument("--end")
    s.add_argument("--state")
    s.add_argument("--macro")
    s.add_argument("--frames", type=int, default=300)
    s.add_argument("--rom")
    s.add_argument("--mod", help="usa a ROM montada do mod e aceita NOME de rótulo do build atual (ex.: CopiaEspelho)")
    s.add_argument("--max-hits", type=int, default=4000)
    s.set_defaults(fn=cmd_probe)

    ram = sub.add_parser("ram", help="busca de RAM por diferenças entre frames").add_subparsers(dest="ram_cmd", required=True)
    s = ram.add_parser("search", help="roda o cenário gravando a WRAM a cada N frames")
    s.add_argument("game")
    s.add_argument("--state")
    s.add_argument("--macro")
    s.add_argument("--frames", type=int, default=120)
    s.add_argument("--every", type=int, default=1)
    s.add_argument("--rom")
    s.set_defaults(fn=cmd_ram_search)
    s = ram.add_parser("query", help="filtra candidatos: --changed A:B --unchanged A:B --increased/--decreased A:B --equals F=V")
    s.add_argument("run")
    s.add_argument("--game", help="registra como evidência do jogo")
    for flag in ("changed", "unchanged", "increased", "decreased", "equals"):
        s.add_argument(f"--{flag}", action="append")
    s.add_argument("--word", action="store_true", help="valores de 16 bits")
    s.add_argument("--limit", type=int, default=40)
    s.set_defaults(fn=cmd_ram_query)

    re_ = sub.add_parser("re", help="análise estática (Ghidra headless + ghidra-snes) com evidência").add_subparsers(dest="re_cmd", required=True)
    s = re_.add_parser("cdl", help="roda um cenário e acumula o Code/Data Log (sementes M/X para o Ghidra)")
    s.add_argument("game")
    s.add_argument("--state")
    s.add_argument("--macro")
    s.add_argument("--frames", type=int, default=1800)
    s.set_defaults(fn=cmd_re)
    s = re_.add_parser("analyze", help="importa + semeia + analisa + exporta")
    s.add_argument("game")
    s.set_defaults(fn=cmd_re)
    s = re_.add_parser("funcs")
    s.add_argument("game")
    s.add_argument("--pattern")
    s.add_argument("--limit", type=int, default=60)
    s.set_defaults(fn=cmd_re)
    s = re_.add_parser("func", help="função que contém o endereço: instruções com M/X, chamadores, chamadas")
    s.add_argument("game")
    s.add_argument("addr")
    s.set_defaults(fn=cmd_re)
    s = re_.add_parser("xrefs", help="referências a um endereço (WRAM com espelhos, MMIO, ROM)")
    s.add_argument("game")
    s.add_argument("addr")
    s.set_defaults(fn=cmd_re)
    s = re_.add_parser("search", help="regex sobre mnemónica+operandos da listagem")
    s.add_argument("game")
    s.add_argument("regex")
    s.add_argument("--limit", type=int, default=100)
    s.set_defaults(fn=cmd_re)
    s = re_.add_parser("decompile")
    s.add_argument("game")
    s.add_argument("addrs", nargs="+")
    s.set_defaults(fn=cmd_re)
    s = re_.add_parser("evidence", help="livro-razão de evidências do jogo (ou uma evidência por id)")
    s.add_argument("game")
    s.add_argument("id", nargs="?")
    s.add_argument("--limit", type=int, default=30)
    s.set_defaults(fn=cmd_re)

    mod = sub.add_parser("mod", help="criar/listar mods").add_subparsers(dest="mod_cmd", required=True)
    s = mod.add_parser("new")
    s.add_argument("id")
    s.add_argument("--game", required=True)
    s.add_argument("--title")
    s.add_argument("--goal")
    s.set_defaults(fn=cmd_mod)
    s = mod.add_parser("list")
    s.set_defaults(fn=cmd_mod)

    s = sub.add_parser("build", help="monta o mod com o Asar numa cópia da base limpa (+ verificação de hijack + BPS)")
    s.add_argument("mod")
    s.set_defaults(fn=cmd_build)

    cy = sub.add_parser("cycle", help="ciclo de evolução: build → baseline → mod → comparação → critérios → veredito").add_subparsers(dest="cycle_cmd", required=True)
    s = cy.add_parser("run")
    s.add_argument("mod")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_cycle)
    s = cy.add_parser("verdict", help="registra o veredito visual do agente para um ciclo")
    s.add_argument("mod")
    s.add_argument("verdict", choices=["evoluiu", "regrediu", "igual", "objetivo-cumprido", "inconclusivo"])
    s.add_argument("--cycle", type=int)
    s.add_argument("--notes")
    s.set_defaults(fn=cmd_cycle)
    s = cy.add_parser("status")
    s.add_argument("mod")
    s.set_defaults(fn=cmd_cycle)

    md = sub.add_parser("media", help="analisar vídeos/imagens gravados (ffmpeg → folhas de contato)").add_subparsers(dest="media_cmd", required=True)
    s = md.add_parser("analyze")
    s.add_argument("path")
    s.add_argument("--n", type=int, default=16, help="frames uniformes")
    s.add_argument("--scene", type=float, default=0.25, help="limiar de mudança de cena")
    s.add_argument("--at", help="instantes extra em segundos, ex.: 1.5,2.25")
    s.set_defaults(fn=cmd_media)
    s = md.add_parser("inbox", help="analisa os arquivos novos em media/inbox/")
    s.add_argument("--n", type=int, default=16)
    s.add_argument("--scene", type=float, default=0.25)
    s.set_defaults(fn=cmd_media)
    s = md.add_parser("compare", help="compara duas runs (frames + traços)")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--title")
    s.set_defaults(fn=cmd_media)

    s = sub.add_parser("bps", help="aplica um patch BPS a uma ROM (para quem recebe o mod)")
    s.add_argument("rom")
    s.add_argument("patch")
    s.add_argument("out")
    s.set_defaults(fn=cmd_bps)

    s = sub.add_parser("testbed", help="(re)monta a ROM homebrew de teste e o state 'parado'")
    s.set_defaults(fn=cmd_testbed)

    s = sub.add_parser("selftest", help="testes unitários + ponta a ponta (testbed)")
    s.add_argument("--quick", action="store_true", help="sem os testes e2e no emulador")
    s.set_defaults(fn=cmd_selftest)

    mem = sub.add_parser("memory", help="memória CoALA no git: dump | restore | status").add_subparsers(
        dest="memory_cmd", required=True)
    s = mem.add_parser("dump", help="exporta a base local para o dump versionado (antes de commitar)")
    s.set_defaults(fn=cmd_memory)
    s = mem.add_parser("restore", help="clone novo: recria a base a partir do dump + sync de docs e código")
    s.add_argument("--force", action="store_true", help="importa o dump por cima de uma base existente")
    s.set_defaults(fn=cmd_memory)
    s = mem.add_parser("status", help="o dump versionado está em dia com a base local?")
    s.set_defaults(fn=cmd_memory)
    return p


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        rc = args.fn(args)
        return rc if isinstance(rc, int) else EXIT_OK
    except FabError as e:
        print(e.render(), file=sys.stderr)
        return e.code
    except KeyboardInterrupt:
        return 130
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"Erro: inesperado ({type(e).__name__}: {e}) — Solução: reporte com a stack acima", file=sys.stderr)
        return EXIT_FAIL
