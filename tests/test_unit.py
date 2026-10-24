"""Testes unitários (sem emulador): ROM/mapas, desmontador, macros, critérios, BPS, serialização."""

import os
import random
import tempfile
import unittest
from pathlib import Path

import numpy as np

from snesfab import bps
from snesfab.checks import Evaluator, evaluate_checks, score
from snesfab.disasm65816 import OPCODES, decode, disassemble, find_writer_before, instr_size
from snesfab.emu import Watch, to_lua
from snesfab.macro import mask_of, parse_macro, total_frames
from snesfab.paths import BUILD, ROOT
from snesfab.rom import load_rom, parse_addr, pc_to_snes, snes_checksum, snes_to_pc, wram_offset
from snesfab.util import FabError

TESTBED = BUILD / "testbed" / "testbed.sfc"


class RomTests(unittest.TestCase):
    def test_parse_addr_formats(self):
        for txt in ("80:A420", "$80A420", "0x80A420", "80A420", "$80:$A420"):
            self.assertEqual(parse_addr(txt), 0x80A420, txt)
        with self.assertRaises(FabError):
            parse_addr("zz:1")

    def test_lorom_hirom_exhirom(self):
        self.assertEqual(snes_to_pc(0x80A420, "lorom"), 0x2420)
        self.assertEqual(snes_to_pc(0x00A420, "lorom"), 0x2420)
        self.assertEqual(snes_to_pc(0x9F8000, "lorom"), 0xF8000)
        self.assertEqual(pc_to_snes(0x2420, "lorom"), 0x80A420)
        self.assertEqual(snes_to_pc(0xC12345, "hirom"), 0x012345)
        self.assertEqual(snes_to_pc(0x818000, "hirom"), 0x018000)
        self.assertEqual(pc_to_snes(0x012345, "hirom"), 0xC12345)
        self.assertEqual(snes_to_pc(0x401234, "exhirom"), 0x401234)
        with self.assertRaises(FabError):
            snes_to_pc(0x7E0000, "lorom")
        with self.assertRaises(FabError):
            snes_to_pc(0x801234, "lorom")

    def test_wram_mirrors(self):
        self.assertEqual(wram_offset(0x7E007D), 0x7D)
        self.assertEqual(wram_offset(0x00007D), 0x7D)
        self.assertEqual(wram_offset(0x80007D), 0x7D)
        self.assertEqual(wram_offset(0x7F0010), 0x10010)
        self.assertIsNone(wram_offset(0x802100))
        self.assertIsNone(wram_offset(0x80A420))

    def test_checksum_mirroring(self):
        data = bytes(range(256)) * (0x300000 // 256)   # 3 MB: 2 MB + 1 MB espelhado 2x
        expected = (sum(data[:0x200000]) + 2 * sum(data[0x200000:])) & 0xFFFF
        self.assertEqual(snes_checksum(data), expected)

    @unittest.skipUnless(TESTBED.exists(), "testbed não montado (fab testbed)")
    def test_testbed_header_and_smc(self):
        img = load_rom(TESTBED)
        self.assertEqual(img.mapping, "lorom")
        self.assertEqual(img.header.title, "SNESFAB TESTBED")
        self.assertTrue(img.checksum_info()["valid"])
        self.assertEqual(img.header.vectors["emu_reset"], 0x8000)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.smc"
            p.write_bytes(b"\x00" * 512 + TESTBED.read_bytes())
            img2 = load_rom(p)
            self.assertTrue(img2.had_smc_header)
            self.assertEqual(img2.data, img.data)


class DisasmTests(unittest.TestCase):
    JUMP = bytes.fromhex("E220A572D014A5162980F00EA9B0857DA9018572A9018DFA1DEA60")

    def test_table_complete(self):
        self.assertEqual(len(OPCODES), 256)

    def test_sizes_follow_mx(self):
        self.assertEqual(instr_size(0xA9, True, True), 2)    # LDA #imm8
        self.assertEqual(instr_size(0xA9, False, True), 3)   # LDA #imm16
        self.assertEqual(instr_size(0xA2, True, True), 2)    # LDX #imm8
        self.assertEqual(instr_size(0xA2, True, False), 3)   # LDX #imm16
        self.assertEqual(instr_size(0x22, True, True), 4)    # JSL
        self.assertEqual(instr_size(0x5C, True, True), 4)    # JML

    def test_guide_routine(self):
        ins = disassemble(self.JUMP, 0x80A41E, m8=False, x8=False)
        self.assertEqual(ins[0].text, "SEP #$20")
        self.assertTrue(ins[1].m8)                         # SEP #$20 → A de 8 bits
        self.assertEqual(ins[2].text, "BNE $A438")
        self.assertEqual(ins[2].target, 0x80A438)
        self.assertEqual([i.addr & 0xFFFF for i in ins][:8],
                         [0xA41E, 0xA420, 0xA422, 0xA424, 0xA426, 0xA428, 0xA42A, 0xA42C])
        self.assertEqual(ins[-1].mnemonic, "RTS")
        self.assertEqual(ins[-1].addr, 0x80A438)

    def test_rep_widens(self):
        ins = disassemble(bytes.fromhex("C230A93412A27856"), 0x808000)
        self.assertEqual(ins[1].text, "LDA #$1234")
        self.assertEqual(ins[2].text, "LDX #$5678")

    def test_writer_reconstruction(self):
        # STA $7D termina em A42E; o emulador reporta o PC seguinte
        cands = find_writer_before(self.JUMP, 0x10, 0x80A42E, True, False)
        self.assertTrue(any(c.text == "STA $7D" and c.addr == 0x80A42C for c in cands))

    def test_mvn_operands(self):
        ins = decode(bytes.fromhex("54 7F 7E".replace(" ", "")), 0, 0x808000, True, True)
        self.assertEqual(ins.text, "MVN $7E,$7F")


class MacroTests(unittest.TestCase):
    def test_parse(self):
        steps = parse_macro("# c\n30\n1 B ; pulo\n12 Right+B\n2x 1 A / 3 -\n")
        self.assertEqual(steps, [(30, 0), (1, 0x8000), (12, 0x8100), (1, 0x80), (3, 0), (1, 0x80), (3, 0)])
        self.assertEqual(total_frames(steps), 51)

    def test_cli_form(self):
        self.assertEqual(parse_macro("20;1 B;18"), [(20, 0), (1, 0x8000), (18, 0)])

    def test_bad_button(self):
        with self.assertRaises(FabError):
            mask_of("Jump")


class ChecksTests(unittest.TestCase):
    def setUp(self):
        self.mod = {"frame": list(range(6)), "input": [0, 0x8000, 0, 0, 0x8000, 0],
                    "y": [100, 90, 80, 70, 60, 100], "vy": [0, -70, 3, 6, -65, 0]}
        self.base = {"frame": list(range(6)), "input": self.mod["input"],
                     "y": [100, 90, 85, 95, 100, 100], "vy": [0, -70, 3, 6, 9, 0]}

    def test_examples(self):
        ev = Evaluator(self.mod, self.base)
        self.assertTrue(ev.eval("min(y) < baseline.min(y) - 20"))
        self.assertEqual(ev.eval("count(edges(vy < -60))"), 2)
        self.assertEqual(ev.eval("count(edges(baseline.vy < -60))"), 1)
        self.assertTrue(ev.eval("any(pressed('B') & (vy < 0))"))
        self.assertTrue(ev.eval("last(y) == 100 and first(y) == 100"))
        self.assertEqual(ev.eval("at(y, 2)"), 80)

    def test_report_and_score(self):
        res = evaluate_checks([{"expr": "min(y) < 70", "weight": 2}, {"expr": "all(y == baseline.y)"},
                               {"expr": "nope(y)"}], self.mod, self.base)
        self.assertEqual([r["passed"] for r in res], [True, False, False])
        self.assertIn("error", res[2])
        self.assertAlmostEqual(score(res), 0.5)

    def test_sandbox(self):
        ev = Evaluator(self.mod, self.base)
        for bad in ("__import__('os').system('echo x')", "y.__class__", "(lambda: 1)()", "open('x')"):
            with self.assertRaises(FabError, msg=bad):
                ev.eval(bad)


class BpsTests(unittest.TestCase):
    def test_roundtrip(self):
        rnd = random.Random(7)
        src = bytes(rnd.randrange(256) for _ in range(70000))
        tgt = bytearray(src)
        for _ in range(200):
            i = rnd.randrange(len(tgt))
            tgt[i] = rnd.randrange(256)
        tgt += bytes(rnd.randrange(256) for _ in range(5000))
        patch = bps.create(src, bytes(tgt), "meta")
        self.assertEqual(bps.apply(src, patch), bytes(tgt))
        with self.assertRaises(FabError):
            bps.apply(src[:-1] + b"\x00", patch)


class SerializationTests(unittest.TestCase):
    def test_to_lua(self):
        s = to_lua({"a": [1, True, None], "p": 'C:\\x "y"', "u": "ção"})
        self.assertIn('["a"] = {1, true, nil}', s)
        self.assertIn('\\\\x \\"y\\"', s)
        self.assertIn("\\195\\167", s)

    def test_watch_specs(self):
        w = Watch.from_spec("y=7E:0096:2s")
        self.assertEqual((w.addr, w.size, w.signed), (0x7E0096, 2, True))
        w = Watch.from_spec("air=7E:0072")
        self.assertEqual((w.addr, w.size, w.signed), (0x7E0072, 1, False))
        w = Watch.from_spec("dj=$7E1DF9:1")
        self.assertEqual((w.addr, w.size), (0x7E1DF9, 1))
        self.assertEqual(w.lua()["mem"], "snesWorkRam")
        self.assertEqual(w.lua()["offset"], 0x1DF9)


if __name__ == "__main__":
    unittest.main()
