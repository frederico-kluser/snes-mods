"""Ponta a ponta no MesenCE headless com a ROM homebrew (precisa de `fab setup`)."""

import shutil
import unittest

import numpy as np

from snesfab.paths import BUILD, CYCLES, MODS, RUNS, toolchain

try:
    _TC = toolchain()
    HAVE_TOOLS = not _TC.missing()
except Exception:  # noqa: BLE001
    HAVE_TOOLS = False


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
        if not ok:
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
