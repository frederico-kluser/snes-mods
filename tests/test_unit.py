"""Testes unitários (sem emulador): ROM/mapas, desmontador, macros, critérios, BPS, serialização."""

import json
import random
import tempfile
import unittest
import zlib
from pathlib import Path


from snesfab import bps
from snesfab.build import data_coverage, parse_data_regions
from snesfab.checks import Evaluator, evaluate_checks, score
from snesfab.disasm65816 import OPCODES, decode, disassemble, find_writer_before, instr_size
from snesfab.emu import Poke, Watch, job_from_scenario, to_lua
from snesfab.ghidra import ghidra_addr
from snesfab.macro import mask_of, parse_macro, total_frames
from snesfab.paths import BUILD
from snesfab.rom import load_rom, parse_addr, parse_rom, pc_to_snes, snes_checksum, snes_to_pc, wram_offset
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

    def test_sa1_como_o_asar(self):
        # MMC padrão (o `sa1rom` do Asar): $80-$BF são os blocos 2-3, não espelhos FastROM de $00-$3F
        self.assertEqual(snes_to_pc(0x008000, "sa1"), 0x000000)
        self.assertEqual(snes_to_pc(0x3FFFFF, "sa1"), 0x1FFFFF)
        self.assertEqual(snes_to_pc(0x808000, "sa1"), 0x200000)
        self.assertEqual(snes_to_pc(0xA0B130, "sa1"), 0x303130)
        self.assertEqual(snes_to_pc(0xE0B130, "sa1"), 0x20B130)
        self.assertEqual(pc_to_snes(0x002420, "sa1"), 0x00A420)
        self.assertEqual(pc_to_snes(0x303130, "sa1"), 0xA0B130)
        self.assertEqual(ghidra_addr(0x002420, "sa1"), 0xC02420)    # o ghidra-snes usa a vista HiROM
        self.assertEqual(ghidra_addr(0x002420, "lorom"), 0x80A420)
        with self.assertRaises(FabError):
            snes_to_pc(0x408000, "sa1")      # BW-RAM, não ROM

    def test_sdd1_mmc_padrao(self):
        # S-DD1 (Star Ocean, SF Alpha 2): LoROM fixa só nos 2 primeiros MiB; $C0-$FF são janelas HiROM de 1 MiB.
        # O SFA2 executa código em $C0:3A91 (= PC 0x3A91) e lê paletas em $DF:0260 (= PC 0x1F0260).
        self.assertEqual(snes_to_pc(0xC03A91, "sdd1"), 0x003A91)
        self.assertEqual(snes_to_pc(0xDF0260, "sdd1"), 0x1F0260)
        self.assertEqual(snes_to_pc(0xBE8260, "sdd1"), 0x1F0260)
        self.assertEqual(snes_to_pc(0x3E8260, "sdd1"), 0x1F0260)
        self.assertEqual(snes_to_pc(0xE00000, "sdd1"), 0x200000)
        self.assertEqual(snes_to_pc(0xFFFFFF, "sdd1"), 0x3FFFFF)
        self.assertEqual(pc_to_snes(0x1F0260, "sdd1"), 0xBE8260)
        self.assertEqual(pc_to_snes(0x200000, "sdd1"), 0xE00000)
        with self.assertRaises(FabError):
            snes_to_pc(0x408000, "sdd1")      # $40-$7D não mapeiam ROM no S-DD1

    def test_pc_to_snes_ida_e_volta(self):
        # achado pelo fuzzing (tests/fuzz/fuzz_rom.py): o endereço canônico tem de voltar ao mesmo byte
        limits = {"lorom": 0x400000, "sdd1": 0x400000, "sa1": 0x400000, "hirom": 0x400000, "exhirom": 0x800000}
        for mapping, limit in limits.items():
            for pc in [*range(0, limit, 0x1357), limit - 1]:
                if mapping == "exhirom" and pc >= 0x7E0000 and pc & 0xFFFF < 0x8000:
                    with self.assertRaises(FabError):    # metade baixa de $3E-$3F: sem endereço de CPU
                        pc_to_snes(pc, mapping)
                    continue
                self.assertEqual(snes_to_pc(pc_to_snes(pc, mapping), mapping), pc, (mapping, hex(pc)))
            with self.assertRaises(FabError):
                pc_to_snes(limit, mapping)
        with self.assertRaises(FabError):
            parse_rom(bytes(100))

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


class DataRegionTests(unittest.TestCase):
    """mod.json → "data" (regiões de dados com evidência): o build não as trata como hijack."""

    def test_parse_e_cobertura(self):
        regs = parse_data_regions([{"addr": "BE:8272", "length": 10, "evidence": "gi do Ken (ev-x)"},
                                   {"addr": "BE:CE6A", "length": 8, "evidence": "retrato do Ken"}], "sdd1")
        self.assertEqual([(r["start_pc"], r["end_pc"]) for r in regs],
                         [(0x1F0272, 0x1F027C), (0x1F4E6A, 0x1F4E72)])
        self.assertIs(data_coverage(regs, 0x1F0272, 0x1F027C), regs[0])     # exatamente a região
        self.assertIs(data_coverage(regs, 0x1F0274, 0x1F0278), regs[0])     # dentro
        self.assertIsNone(data_coverage(regs, 0x1F0270, 0x1F0276))          # começa antes
        self.assertIsNone(data_coverage(regs, 0x1F0278, 0x1F0280))          # termina depois
        self.assertIsNone(data_coverage(regs, 0x000100, 0x000200))          # longe
        self.assertIsNone(data_coverage([], 0, 16))
        # espelho LoROM/S-DD1 resolve para o mesmo byte
        self.assertEqual(parse_data_regions([{"addr": "3E:8272", "length": 1, "evidence": "x"}], "sdd1")[0]["start_pc"],
                         0x1F0272)

    def test_data_invalido(self):
        for bad in ({"addr": "BE:8272", "length": 10},                        # sem evidence
                    {"addr": "BE:8272", "length": 10, "evidence": "   "},     # evidence vazia
                    {"addr": "BE:8272", "length": 0, "evidence": "x"},        # comprimento zero
                    {"addr": "BE:8272", "length": -4, "evidence": "x"},       # negativo
                    {"addr": "BE:8272", "length": "abc", "evidence": "x"},    # não numérico
                    {"length": 10, "evidence": "x"},                          # sem addr
                    {"addr": "zz:1", "length": 10, "evidence": "x"},          # addr inválido
                    "BE:8272"):                                               # não é objeto
            with self.assertRaises(FabError, msg=repr(bad)):
                parse_data_regions([bad], "sdd1")
        self.assertEqual(parse_data_regions([], "lorom"), [])
        self.assertEqual(parse_data_regions(None, "lorom"), [])


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

    def test_limites(self):
        # macros vêm de mods de terceiros: tamanho, aninhamento e números absurdos viram FabError
        for bad in ("99999999x 1 B", "2x " * 12 + "1 B", "1" * 5000 + " B", "2000000 B",
                    [[1, 30, "B"]], [[1, 0x1FFFF]], [[]], ["20 B"], [[-1, "B"]], [["x", "B"]], [[1e400, 0]]):
            with self.assertRaises(FabError, msg=repr(bad)[:40]):
                parse_macro(bad)
        self.assertEqual(len(parse_macro("1000x 1 B / 1 -")), 2000)
        self.assertEqual(parse_macro([[20, "B+Right"], [3], [1, 0x8000]]), [(20, 0x8100), (3, 0), (1, 0x8000)])


class JobTests(unittest.TestCase):
    def test_warmup_do_cenario(self):
        # o state carrega RAM/CGRAM da ROM limpa: cenários de paleta medem só depois da recarga
        sc = {"frames": 60, "warmup": 40, "input": "30;1 B", "watch": ["gi=cgram:01D2:2"], "capture": {"every": 4}}
        job = job_from_scenario(sc, Path("."))
        self.assertEqual((job.frames, job.warmup, job.capture_every), (60, 40, 4))
        self.assertEqual(job.to_lua_table(Path("out"))["warmup"], 40)
        self.assertEqual(job_from_scenario({"frames": 10, "input": "5"}, Path(".")).warmup, 0)


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

    def test_recursos_limitados(self):
        # expressão patológica num mod.json vira erro do critério, nunca trava nem estoura a memória
        exprs = ("9**9**9**9", "1 << 10**10", "'a' * 10**10", "[0] * 10**9", "(2**64)**64**64")
        res = evaluate_checks([{"expr": e} for e in exprs], self.mod, self.base)
        self.assertTrue(all(not r["passed"] and "error" in r for r in res), res)
        self.assertEqual(Evaluator(self.mod).eval("2 ** 10"), 1024)

    def test_relatorio_serializavel(self):
        # achado pelo fuzzing: o resultado vai para o ledger em JSON, com tupla, inteiro enorme ou complexo
        res = evaluate_checks([{"expr": e} for e in ("(y, 2**100)", "[y, -1] == 1", "(-8) ** 0.5", "y[0:3]")],
                              self.mod, self.base)
        json.dumps(res)
        self.assertEqual(res[0]["value"][1], "<inteiro de 101 bits>")


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

    @staticmethod
    def _patch(src: bytes, tgt_size: int, actions: bytes, tgt_crc: bytes = bytes(4)) -> bytes:
        crc = lambda b: (zlib.crc32(b) & 0xFFFFFFFF).to_bytes(4, "little")  # noqa: E731
        p = b"BPS1" + bps._enc(len(src)) + bps._enc(tgt_size) + bps._enc(0) + actions + crc(src) + tgt_crc
        return p + crc(p)

    def test_patch_malformado(self):
        # BPS de terceiros: todo defeito vira FabError (o fuzzing achou IndexError no TargetCopy)
        src, enc = bytes(range(256)) * 4, bps._enc
        bad = {
            "número truncado": self._patch(src, 8, b"\x00"),
            "número longo": self._patch(src, 8, b"\x00" * 11 + b"\x80"),
            "alvo gigante": self._patch(src, 1 << 40, b""),
            "TargetCopy fora do alvo": self._patch(src, 4, enc(1) + b"A" + enc((2 << 2) | 3) + enc(100 << 1)),
            "SourceRead além da origem": self._patch(src, 2000, enc(1999 << 2)),
            "TargetRead além do patch": self._patch(src, 64, enc((63 << 2) | 1) + b"xy"),
            "SourceCopy negativo": self._patch(src, 8, enc((7 << 2) | 2) + enc((5 << 1) | 1)),
            "curto": b"BPS1" + b"\x80" * 3,
        }
        for name, p in bad.items():
            with self.assertRaises(FabError, msg=name):
                bps.apply(src, p)

    def test_target_copy_sobreposto(self):
        # TargetCopy sobreposto repete o padrão (RLE), como no beat/Flips
        src, tgt = bytes(range(256)) * 4, b"ab" * 10
        tgt_crc = (zlib.crc32(tgt) & 0xFFFFFFFF).to_bytes(4, "little")
        actions = bps._enc((1 << 2) | 1) + b"ab" + bps._enc((17 << 2) | 3) + bps._enc(0)
        self.assertEqual(bps.apply(src, self._patch(src, len(tgt), actions, tgt_crc)), tgt)


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

    def test_watch_ppu(self):
        # paletas/VRAM/OAM: offset em bytes na memória do PPU (cor 233 = bytes $1D2-$1D3 da CGRAM)
        w = Watch.from_spec("gi=cgram:01D2:2")
        self.assertEqual((w.space, w.addr, w.size), ("cgram", 0x1D2, 2))
        self.assertEqual(w.lua()["mem"], "snesCgRam")
        self.assertEqual(w.lua()["offset"], 0x1D2)
        self.assertEqual(Watch.from_spec(w.to_dict()), w)          # o dicionário volta ao mesmo watch
        self.assertEqual(Watch.from_spec("t=VRAM:$8000").lua()["mem"], "snesVideoRam")
        self.assertEqual(Watch.from_spec("o=oam:0x21F").size, 1)
        for bad in ("c=cgram:01FF:2", "c=cgram:0200", "o=oam:0220", "c=cgram:01:02:2"):
            with self.assertRaises(FabError, msg=bad):
                Watch.from_spec(bad)

    def test_poke_specs(self):
        p = Poke.from_spec("60:cgram:01D2:2=0x03E0")
        self.assertEqual((p.frame, p.space, p.addr, p.size, p.value), (60, "cgram", 0x1D2, 2, 0x03E0))
        self.assertEqual(p.lua(), {"frame": 60, "mem": "snesCgRam", "offset": 0x1D2, "value": 0x03E0, "size": 2})
        p = Poke.from_spec("30:7E:06D2:2=0x1084")                  # WRAM: o offset é o da work RAM
        self.assertEqual((p.frame, p.space, p.lua()["mem"], p.lua()["offset"]),
                         (30, "", "snesWorkRam", 0x6D2))
        p = Poke.from_spec("0:oam:0x21A=0x2F")                     # OAM, 1 byte, decimal
        self.assertEqual((p.addr, p.size, p.value, p.lua()["mem"]), (0x21A, 1, 0x2F, "snesSpriteRam"))
        # mod.json: os mesmos campos, com ou sem prefixo de espaço
        self.assertEqual(Poke.from_spec({"frame": 5, "addr": "7E:06D2", "value": 1}).lua()["offset"], 0x6D2)
        self.assertEqual(Poke.from_spec({"frame": 5, "addr": "cgram:0160:2", "value": 0, "size": 2}).space, "cgram")
        for bad in ("60:cgram:01D2:2", "cgram:01D2=1", "60:cgram:01FF:2=1", "x:cgram:01D2=1"):
            with self.assertRaises(FabError, msg=bad):
                Poke.from_spec(bad)

    def test_poke_expansao_por_frame(self):
        # "*" = todos os frames medidos; "3-5" = intervalo; "7" = um frame
        from snesfab.cli import _expand_pokes
        self.assertEqual([p.frame for p in _expand_pokes(["*:cgram:01DC:2=0x7C1F"], 4)], [0, 1, 2, 3])
        self.assertEqual([p.frame for p in _expand_pokes(["3-5:7E:06D2:2=1"], 10)], [3, 4, 5])
        self.assertEqual([p.frame for p in _expand_pokes(["7:cgram:01DC:2=1"], 10)], [7])
        self.assertTrue(all(p.size == 2 and p.space == "cgram" for p in _expand_pokes(["*:cgram:01DC:2=1"], 2)))
        with self.assertRaises(FabError):
            _expand_pokes(["semframe=1"], 3)


if __name__ == "__main__":
    unittest.main()
