"""Ponta a ponta no MesenCE headless com a ROM homebrew (precisa de `fab setup`)."""

import shutil
import unittest

import numpy as np

from snesfab.paths import BUILD, CYCLES, MODS, ROOT, RUNS, toolchain

try:
    _TC = toolchain()
    HAVE_TOOLS = not _TC.missing()
except Exception:  # noqa: BLE001
    HAVE_TOOLS = False


def testbed_label_pc(name: str) -> int:
    """Offset no arquivo de um rótulo do testbed (o .sym do `fab testbed`): o código pode andar, o teste não."""
    from snesfab.build import parse_sym
    from snesfab.rom import snes_to_pc
    return snes_to_pc(parse_sym(BUILD / "testbed" / "testbed.sym")[name], "lorom")


def fab_json(test: unittest.TestCase, *args: str) -> dict:
    """Roda um comando do fab (como na linha de comando) e devolve o JSON que ele imprime."""
    import contextlib
    import io
    import json

    from snesfab.cli import main
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(list(args))
    test.assertEqual(rc, 0, buf.getvalue()[-2000:])
    return json.loads(buf.getvalue())


@unittest.skipUnless(HAVE_TOOLS, "toolchain ausente (fab setup)")
class E2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from snesfab.game import list_states, load_game
        try:
            load_game("testbed")
            ok = any(s["name"] == "parado" for s in list_states("testbed"))
        except Exception:  # noqa: BLE001
            ok = False
        if not ok or not (BUILD / "testbed" / "testbed.sym").exists():
            from snesfab.setup_tools import setup_testbed
            setup_testbed()

    def test_capture_aligned_with_ram(self):
        """Imagem do frame N == estado da lógica do frame N-1 (atraso constante), sem frame skipping."""
        from snesfab.emu import Job, Watch, new_run_dir, read_trace, run_job
        from snesfab.game import clean_rom, state_path
        from snesfab.macro import parse_macro
        from snesfab.media import load_run_frames
        from snesfab.rom import load_rom
        rom = clean_rom("testbed")
        out = new_run_dir("e2e", "align")
        try:
            job = Job(frames=60, state=state_path("testbed", "parado"), macro=parse_macro("10;1 B;30 Right;19"),
                      watches=[Watch.from_spec("y=7E:0096:2"), Watch.from_spec("x=7E:0094:2")], capture_every=1)
            res = run_job(rom, job, out, rom_image=load_rom(rom))
            self.assertEqual(res["frames_captured"], 60)
            self.assertTrue(res["state_loaded"])
            tr, rf = read_trace(out), load_run_frames(out)
            for f, img in zip(rf.frames, rf.images):
                if f == 0:
                    continue
                red = np.argwhere((img[:, :, 0] > 200) & (img[:, :, 1] < 80))
                top, left = red.min(axis=0)
                self.assertEqual(left, tr["x"][f - 1], f"x no frame {f}")
                self.assertLessEqual(abs(top - ((tr["y"][f - 1] >> 4) + 1)), 1, f"y no frame {f}")
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def test_warmup_starts_measurement_late(self):
        """warmup: os primeiros N frames correm sem medir (state traz RAM velha da ROM limpa)."""
        from snesfab.emu import Job, Watch, new_run_dir, read_trace, run_job
        from snesfab.game import clean_rom, state_path
        from snesfab.macro import parse_macro
        from snesfab.rom import load_rom
        rom = clean_rom("testbed")
        out = new_run_dir("e2e", "warmup")
        try:
            job = Job(frames=40, state=state_path("testbed", "parado"), macro=parse_macro("10;1 B;29"),
                      watches=[Watch.from_spec("y=7E:0096:2")], capture_every=1, warmup=10)
            res = run_job(rom, job, out, rom_image=load_rom(rom))
            tr = read_trace(out)
            self.assertEqual(res["frames_run"], 40)
            self.assertEqual(res["frames_measured"], 30)
            self.assertEqual(res["frames_captured"], 30)
            self.assertEqual(tr["frame"][0], 10)          # o traço começa no frame 10
            self.assertEqual(len(tr["frame"]), 30)         # 40 - 10 medidos
            self.assertEqual(tr["frame"][-1], 39)
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def test_sprites_render_e_falsa_cor_batem_com_a_tela(self):
        """Snapshot do PPU (render da camada de sprites) e falsa cor (índice por píxel) contra a imagem real."""
        from snesfab import ppu, sprites
        from snesfab.emu import new_run_dir
        from snesfab.game import clean_rom, state_path
        from snesfab.macro import parse_macro
        out = new_run_dir("e2e", "sprites")
        try:
            cap = sprites.capture("testbed", out, rom=clean_rom("testbed"), state=state_path("testbed", "parado"),
                                  macro=parse_macro("10;1 B;30 Right;19"), frames=[5, 30, 59])
            self.assertEqual(sorted(cap.frames), [5, 30, 59])
            for fd in cap.frames.values():
                ag = fd.agreement()
                self.assertEqual(ag["fracao"], 1.0, ag)
                self.assertEqual(ag["obj_px_render"], 256)                 # o boneco 16x16
                objs = sprites.find_objects(fd)
                self.assertEqual([(o.palette, o.cgram_palette) for o in objs], [(0, 8)])
                rec = ppu.bgr555_array_to_rgb(fd.colors[np.clip(fd.index, 0, 255)])
                self.assertTrue((rec == fd.real).all())                    # tela real == CGRAM[índice]
            rep = sprites.snap_report(cap, 30)
            self.assertTrue((out / "f00030" / "overview.png").exists())
            self.assertEqual(rep["objetos"][0]["paleta_cgram"], 8)
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def test_paint_set_build_e_check(self):
        """O fluxo simples de pintura: paint set → build (org gerado) → check por efeito (0 colaterais)."""
        from snesfab.build import build_mod
        from snesfab.emu import new_run_dir
        from snesfab.paint import check_paint, set_palette
        from snesfab.util import write_json
        mid = "_e2e_paint"
        dst = MODS / mid
        for d in (dst, BUILD / mid):
            shutil.rmtree(d, ignore_errors=True)
        dst.mkdir(parents=True)
        out = new_run_dir("e2e", "paint")
        try:
            write_json(dst / "mod.json", {"id": mid, "game": "testbed", "title": "e2e paint", "goal": "boneco azul",
                                          "patches": [], "scenarios": []})
            set_palette(dst, testbed_label_pc("ObjPalette"), [1], [0x7C00], "boneco", "e2e: ObjPalette = CGRAM 128-130")
            from snesfab.paint import apply_paint
            res = apply_paint(dst)
            self.assertEqual(res["trocas"][0]["antes"], "$109F")
            b = build_mod(dst)
            self.assertTrue(b["ok"])
            self.assertEqual([r["kind"] for r in b["regions"] if r["kind"] != "header"], ["data"])
            r = check_paint(dst, out, state=None, macro=[], frames=[20, 40])   # power-on: a paleta vem da ROM do mod
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["total"]["colateral"], 0)
            self.assertEqual(r["total"]["esperado"], 2 * 248)
        finally:
            for d in (dst, BUILD / mid, out):
                shutil.rmtree(d, ignore_errors=True)

    def test_dma_log_acha_a_sombra_do_oam(self):
        """O log de DMA acha a sombra do OAM ($0200) e a instrução que dispara (STA $420B) em qualquer banco."""
        from snesfab import dma
        from snesfab.emu import Job, new_run_dir, run_job
        from snesfab.game import clean_rom, state_path
        from snesfab.rom import load_rom
        rom = clean_rom("testbed")
        out = new_run_dir("e2e", "dma")
        try:
            run_job(rom, Job(frames=10, state=state_path("testbed", "parado"), capture_every=0, dma_log=True), out)
            rep = dma.summarize(dma.read_dma(out), load_rom(rom))
            oam = [r for r in rep["transferencias"] if r["destino"] == "OAM"]
            self.assertEqual((oam[0]["fonte"], oam[0]["bytes"], oam[0]["frames"]), ("7E:0200", 544, 10))
            self.assertIn("STA $420B", oam[0]["instrucao"])
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def test_paint_remap_de_tiles_crus(self):
        """Desenho cru na ROM: trocar um índice DENTRO dos tiles (2→1) gera dados, monta e confere por efeito."""
        from snesfab import sprites
        from snesfab.build import build_mod
        from snesfab.emu import new_run_dir
        from snesfab.game import clean_rom
        from snesfab.paint import apply_paint, check_paint, remap_tiles
        from snesfab.util import write_json
        mid = "_e2e_remap"
        dst = MODS / mid
        for d in (dst, BUILD / mid):
            shutil.rmtree(d, ignore_errors=True)
        dst.mkdir(parents=True)
        out = new_run_dir("e2e", "remap")
        try:
            write_json(dst / "mod.json", {"id": mid, "game": "testbed", "title": "e2e remap", "goal": "sem branco",
                                          "patches": [], "scenarios": []})
            cap = sprites.capture("testbed", out / "snap", rom=clean_rom("testbed"), state=None, macro=[], frames=[20])
            fd = cap.frame(20)
            obj = sprites.find_objects(fd)[0]
            res = remap_tiles(dst, fd, obj, {2: 1}, "sem-branco", "e2e: tiles crus do boneco (fab sprite tiles)")
            self.assertEqual(len(res["tiles_trocados"]), 2)
            apply_paint(dst)
            self.assertTrue(build_mod(dst)["ok"])
            r = check_paint(dst, out / "check", state=None, macro=[], frames=[20, 40])
            self.assertTrue(r["ok"], r)
            self.assertEqual((r["total"]["esperado"], r["total"]["colateral"]), (16, 0))
        finally:
            for d in (dst, BUILD / mid, out):
                shutil.rmtree(d, ignore_errors=True)

    def test_oam_mirror_nivel2_gera_monta_e_cabe_no_vblank(self):
        """Nível 2 de ponta a ponta: log de DMA → gerador → build (hijack + tamanhos) → check com orçamento de VBlank."""
        from snesfab import dma, oamhook
        from snesfab.build import build_mod
        from snesfab.emu import Job, new_run_dir, run_job
        from snesfab.game import clean_rom, state_path
        from snesfab.paint import _load_spec, check_paint
        from snesfab.rom import load_rom, parse_addr
        from snesfab.util import write_json
        mid = "_e2e_oam_mirror"
        dst = MODS / mid
        for d in (dst, BUILD / mid):
            shutil.rmtree(d, ignore_errors=True)
        dst.mkdir(parents=True)
        out = new_run_dir("e2e", "oammirror")
        try:
            write_json(dst / "mod.json", {"id": mid, "game": "testbed", "title": "e2e oam mirror", "goal": "boneco verde",
                                          "patches": [], "scenarios": []})
            rom = load_rom(clean_rom("testbed"))
            run_job(clean_rom("testbed"), Job(frames=5, state=state_path("testbed", "parado"), capture_every=0,
                                              dma_log=True), out / "dma")
            rep = dma.summarize(dma.read_dma(out / "dma"), rom)
            oam = next(r for r in rep["transferencias"] if r["destino"] == "OAM")
            asm, hj = oamhook.generate(rom=rom, oam_shadow=parse_addr(oam["fonte"]),
                                       trigger_next=parse_addr(oam["dispara_pc_seguinte"]), m8=True, x8=False,
                                       src_palette=0, mirror_palette=1, tiles=[0], colors={1: 0x03E0},
                                       pal_buffer=None, evidence="e2e")
            oamhook.save(dst, asm, hj)
            spec = _load_spec(dst)
            spec["oam_mirror"] = {"src": 0, "mirror": 1, "tiles": [0], "colors": {"1": "$03E0"}}
            write_json(dst / "paint.json", spec)
            b = build_mod(dst)
            self.assertTrue(b["ok"], b.get("hijacks"))
            self.assertEqual(b["code_check"]["issues"], [])
            r = check_paint(dst, out / "check", state=state_path("testbed", "parado"), macro=[], frames=[5, 30])
            self.assertTrue(r["ok"], r)
            self.assertTrue(r["vblank"]["ok"], r["vblank"])
            self.assertEqual((r["total"]["esperado"], r["total"]["colateral"]), (2 * 248, 0))
        finally:
            for d in (dst, BUILD / mid, out):
                shutil.rmtree(d, ignore_errors=True)

    def test_gfx_dump_exporta_o_tileset(self):
        """Export do tileset pela VRAM: do power-on, os 6 uploads do testbed viram 5 tiles crus achados na ROM e 4
        montados na WRAM (a ROM os guarda invertidos: não estão crus em lugar nenhum)."""
        from snesfab import gfx
        from snesfab.emu import Job, new_run_dir, read_ppu, run_job
        from snesfab.game import clean_rom
        from snesfab.rom import load_rom
        rom = load_rom(clean_rom("testbed"))
        out = new_run_dir("e2e", "gfx")
        try:
            run_job(clean_rom("testbed"), Job(frames=30, capture_every=0, vram_uploads=True, ppu_frames=[29]), out)
            ups = gfx.read_uploads(out)
            self.assertEqual(len(ups), 6)
            self.assertTrue(all("ch" in u and "ps" in u for u in ups))       # canal e M/X do disparo (override)
            snap = read_ppu(out)[29]
            tiles = gfx.collect(ups, rom, 4, gfx.obj_regions(snap.meta))
            gfx.add_vram_snapshot(tiles, snap.vram, 29, 4, None, gfx.tilemap_regions(snap.meta))
            self.assertEqual(len(tiles), 9)
            self.assertEqual(gfx.find_raw(tiles, rom), 5)
            kinds = sorted(t.origins.most_common(1)[0][0] for t in tiles.values())
            self.assertEqual(kinds, ["cru"] * 5 + ["wram"] * 4)
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def test_gfx_override_serve_o_desenho_editado_sem_codec(self):
        """Desenho montado na WRAM (não está cru na ROM): dump → override de UM dos dois conteúdos que passam pelo
        mesmo buffer e pelo mesmo disparo (a impressão digital separa) → build confere o hook → gfx check na VRAM;
        controle negativo: a ROM limpa ainda manda o desenho velho; e o mesmo com tabela/cópia num blob."""
        import json

        from snesfab import gfx, gfxoverride
        from snesfab.emu import new_run_dir
        from snesfab.game import clean_rom
        from snesfab.util import write_json
        mid = "_e2e_gfxovr"
        dst = MODS / mid
        for d in (dst, BUILD / mid):
            shutil.rmtree(d, ignore_errors=True)
        dst.mkdir(parents=True)
        dirs = []
        try:
            write_json(dst / "mod.json", {"id": mid, "game": "testbed", "title": "e2e gfx override",
                                          "goal": "xadrez com a cor 3", "patches": [], "scenarios": []})
            dump = fab_json(self, "gfx", "dump", "testbed", "--frames", "30", "--label", "e2e-ovr")
            dump_dir = ROOT / dump["dir"]
            dirs.append(dump_dir)
            self.assertEqual(dump["por_origem"], {"cru": 5, "wram": 4})
            idx = json.loads((dump_dir / "tiles.json").read_text(encoding="utf-8"))
            tile = next(t for t in idx if "$1000" in t["vram"])            # tile $80 (xadrez), 1.º conteúdo
            res = fab_json(self, "gfx", "override", str(dst), "--dump", str(dump_dir), "--tiles", str(tile["n"]),
                           "--map", "1:3", "--name", "xadrez", "--evidence", "e2e: tile $80 do dump (WRAM 7F:0000)")
            self.assertEqual(res["edicao"]["via_override"], [tile["hash"]])
            blocks = res["override"]["blocos"]
            self.assertEqual([(b["tipo"], b["fonte"], b["bytes"]) for b in blocks], [("wram", "7F:0000", 64)])
            self.assertTrue(blocks[0]["impressao"])
            spec = json.loads((dst / "paint.json").read_text(encoding="utf-8"))
            e = spec["vram_tiles"][0]
            old, new = gfx.decode_tile(bytes.fromhex(e["original"]), 4), gfx.decode_tile(bytes.fromhex(e["new"]), 4)
            self.assertTrue(((old == 1) == (new == 3)).all() and (new[old != 1] == old[old != 1]).all())
            self.assertTrue(fab_json(self, "build", str(dst))["ok"])
            bj = json.loads((BUILD / mid / "build.json").read_text(encoding="utf-8"))
            self.assertEqual(bj["code_check"]["issues"], [])
            self.assertGreater(bj["code_check"]["instructions_checked"], 40)    # corpo do hook + conferência
            chk = fab_json(self, "gfx", "check", str(dst), "--dump", str(dump_dir))
            dirs.append(ROOT / chk["dir"])
            self.assertTrue(chk["ok"], chk)
            self.assertEqual(chk["desenho_novo_chegou"], {str(tile["n"]): 1})
            neg_dir = new_run_dir("e2e", "gfxneg")
            dirs.append(neg_dir)
            neg = gfxoverride.check(dst, gfxoverride.load_dump(dump_dir), clean_rom("testbed"), neg_dir)
            self.assertFalse(neg["ok"])
            self.assertTrue(neg["desenho_velho_ainda_aparece"])
            # o mesmo override com tabela e cópia num blob (ROM sem espaço livre: área expandida ou --data-at)
            res = fab_json(self, "gfx", "override", str(dst), "--dump", str(dump_dir), "--data-at", "0xF0000",
                           "--data-evidence", "e2e: padding vazio do testbed")
            self.assertTrue(res["override"]["blob"])
            b = fab_json(self, "build", str(dst))
            self.assertTrue(b["ok"])
            bj = json.loads((BUILD / mid / "build.json").read_text(encoding="utf-8"))
            self.assertIn("data", {r["kind"] for r in bj["regions"]})
            chk = fab_json(self, "gfx", "check", str(dst), "--dump", str(dump_dir))
            dirs.append(ROOT / chk["dir"])
            self.assertTrue(chk["ok"], chk)
        finally:
            for d in (dst, BUILD / mid, *dirs):
                shutil.rmtree(d, ignore_errors=True)

    def test_cycle_detects_evolution_and_regression(self):
        from snesfab.cycle import ledger_status, run_cycle
        from snesfab.util import read_json, write_json
        mid = "_e2e_double_jump"
        src, dst = MODS / "testbed-double-jump", MODS / mid
        for d in (dst, CYCLES / mid, BUILD / mid, RUNS / "cycles" / mid):
            shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(src, dst)
        try:
            mod = read_json(dst / "mod.json")
            mod["id"] = mid
            write_json(dst / "mod.json", mod)
            patch = dst / "patch.asm"
            good = patch.read_text(encoding="utf-8")

            r1 = run_cycle(dst, "patch do guia")
            self.assertEqual(r1["status"], "ok")
            self.assertEqual(r1["score"], 1.0)
            self.assertTrue(r1["goal_met_by_checks"])
            simples = next(s for s in r1["scenarios"] if s["id"] == "pulo-simples")
            self.assertEqual(simples["compare"]["frames_divergent"], 0)
            duplo = next(s for s in r1["scenarios"] if s["id"] == "pulo-duplo")
            self.assertEqual(duplo["hijack_mx_dynamic"]["80:A420"]["flags"], {"m8,x16": duplo["hijack_mx_dynamic"]["80:A420"]["executions"]})

            patch.write_text(good.replace("lda #$B8", "lda #$F8"), encoding="utf-8")   # salto duplo fraquinho
            r2 = run_cycle(dst, "impulso fraco")
            self.assertLess(r2["score"], 1.0)
            self.assertEqual(r2["verdict_auto"], "regrediu")

            patch.write_text(good, encoding="utf-8")
            r3 = run_cycle(dst, "volta ao impulso do guia")
            self.assertEqual(r3["verdict_auto"], "evoluiu")
            self.assertEqual(ledger_status(dst)["best_cycle"], 1)
        finally:
            for d in (dst, CYCLES / mid, BUILD / mid, RUNS / "cycles" / mid):
                shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
