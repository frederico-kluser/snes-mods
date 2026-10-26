"""Testes unitários (sem emulador) do kit de pintura de sprites: PPU (OAM/tiles/render/falsa cor), objetos,
regiões e rótulos por conteúdo de tile, rampas que preservam o sombreado, paint.json → asm e portões do build."""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from snesfab import ppu
from snesfab.build import _source_instruction, parse_data_regions, verify_code_widths
from snesfab.emu import PPU_SNAPSHOT_SIZE, Job, PpuSnapshot, read_ppu, read_wram
from snesfab.dma import summarize as dma_summarize
from snesfab.paint import _merge_regions, _runs, classify_frame, expected_changes
from snesfab.parts import PartStore, census, classify, pixel_keys, regions, separability_levels
from snesfab.ramp import check_ramp, lch, make_ramps, parse_target
from snesfab.rom import asar_org, pc_to_snes, snes_to_pc
from snesfab.sprites import (FrameData, _search_words, color_index_map, components, find_bg_areas, find_objects,
                              find_palette_sources, find_raw_tile, object_tiles, palette_target)


# ── cena sintética: tiles, OAM e CGRAM montados à mão ──────────────────────────────

def tile(fill: int, mark: tuple[int, int, int] | None = None) -> bytes:
    """Tile 8x8 todo no índice `fill`; `mark` = (y, x, índice) pinta um píxel diferente."""
    px = np.full((8, 8), fill, np.uint8)
    if mark:
        px[mark[0], mark[1]] = mark[2]
    return ppu.encode_4bpp(px)


def oam_entry(x: int, y: int, t: int, pal: int, prio: int = 2, hflip=False, vflip=False, second=False) -> bytes:
    attr = (0x80 if vflip else 0) | (0x40 if hflip else 0) | (prio << 4) | (pal << 1) | (1 if second else 0)
    return bytes([x & 0xFF, y & 0xFF, t & 0xFF, attr])


def build_oam(entries: list[bytes], high: dict[int, int] | None = None) -> bytes:
    """`high` = {índice: bits} (bit 0 = X bit 8, bit 1 = grande). Os não usados ficam fora da tela (Y=240)."""
    low = bytearray()
    for e in entries:
        low += e
    while len(low) < 512:
        low += bytes([0, 240, 0, 0])
    hi = bytearray(32)
    for i, bits in (high or {}).items():
        hi[i // 4] |= (bits & 3) << (2 * (i % 4))
    return bytes(low) + bytes(hi)


def scene():
    """Objeto A (paleta 6): sprite 0 (16x16) com o tile 0 = índice 14 ("cabelo") e o tile 1 = índice 9;
    sprite 1 (8x8) logo abaixo com o tile 2 = índice 14 ("luva"). Objeto B (paleta 7) longe, 8x8 índice 3."""
    vram = bytearray(0x10000)
    vram[0x00:0x20] = tile(14)
    vram[0x20:0x40] = tile(9, (0, 0, 1))
    vram[0x200:0x220] = tile(9)            # tile 16 (linha de baixo do 16x16)
    vram[0x220:0x240] = tile(9)            # tile 17
    vram[0x40:0x60] = tile(14, (7, 7, 0))  # tile 2 (a "luva"), com um píxel transparente
    vram[0x60:0x80] = tile(3)              # tile 3
    oam = build_oam([oam_entry(40, 50, 0, 6), oam_entry(40, 66, 2, 6), oam_entry(150, 100, 3, 7)], {0: 2})
    cg = np.zeros(256, np.uint16)
    for i in range(16):
        cg[16 * 14 + i] = 0x0400 + i * 0x21     # paleta CGRAM 14 = OAM 6
        cg[16 * 15 + i] = 0x2000 + i            # paleta CGRAM 15 = OAM 7
    cg[16 * 14 + 14] = 0x339E
    cgram = cg.astype("<u2").tobytes()
    return oam, bytes(vram), cgram, cg


def frame_from(oam: bytes, vram: bytes, cgram: bytes, colors: np.ndarray) -> FrameData:
    lay = ppu.render_obj(oam, vram, 0, 0, 0x1000)
    real = lay.rgb(colors, background=(10, 20, 30))
    idx = np.where(lay.color >= 0, lay.cgram_index, 0).astype(np.int16)
    snap = PpuSnapshot(1, oam, cgram, vram, {"oamMode": 0, "oamBaseAddress": 0, "oamAddressOffset": 0x1000})
    return FrameData(1, real, idx, snap)


class PpuTests(unittest.TestCase):
    def test_cores(self):
        self.assertEqual(ppu.bgr555_to_rgb(0x7FFF), (255, 255, 255))
        self.assertEqual(ppu.bgr555_to_rgb(0x001F), (255, 0, 0))
        for v in (0, 0x1084, 0x2908, 0x7E06, 0x339E):
            self.assertEqual(ppu.rgb_to_bgr555(*ppu.bgr555_to_rgb(v)), v)
        self.assertEqual(ppu.parse_color("$2908"), 0x2908)
        self.assertEqual(ppu.parse_color("#ff0000"), 0x001F)
        with self.assertRaises(ValueError):
            ppu.parse_color("$8000")

    def test_tile_ida_e_volta(self):
        rng = np.random.default_rng(1)
        px = rng.integers(0, 16, (8, 8)).astype(np.uint8)
        self.assertTrue((ppu.decode_4bpp(ppu.encode_4bpp(px)) == px).all())

    def test_paleta_de_sprite_e_p_mais_8(self):
        self.assertEqual(ppu.obj_palette_cgram(6), 14)
        self.assertEqual(ppu.obj_palette_cgram(3), 11)
        with self.assertRaises(ValueError):
            ppu.obj_palette_cgram(8)

    def test_parse_oam(self):
        oam = build_oam([oam_entry(0xF8, 10, 0x05, 3, prio=1, hflip=True, second=True)], {0: 3})
        e = ppu.parse_oam(oam, obj_mode=0)[0]
        self.assertEqual((e.x, e.y, e.tile, e.palette, e.priority, e.hflip, e.large), (0x1F8 - 512, 10, 0x105, 3, 1, True, True))
        self.assertEqual((e.width, e.height), (16, 16))
        self.assertEqual(e.cgram_palette, 11)

    def test_render_prioridade_transparencia_e_tamanho(self):
        oam, vram, cgram, cg = scene()
        lay = ppu.render_obj(oam, vram, 0, 0, 0x1000)
        self.assertEqual(lay.oam[50, 40], 0)           # canto do 16x16, tile 0
        self.assertEqual(lay.color[50, 40], 14)
        self.assertEqual(lay.color[50, 48], 1)         # tile 1, píxel (0,0) marcado com o índice 1
        self.assertEqual(lay.color[58, 40], 9)         # linha de baixo: tile 16
        self.assertEqual(lay.cgram_index[50, 40], 16 * 14 + 14)
        self.assertEqual(lay.color[66 + 7, 40 + 7], -1)  # píxel transparente do tile 2
        self.assertEqual(lay.oam[100, 150], 2)
        self.assertEqual(lay.palette[100, 150], 7)

    def test_render_espelhamento(self):
        vram = bytearray(0x10000)
        vram[0:32] = tile(2, (0, 0, 5))
        lay = ppu.render_obj(build_oam([oam_entry(10, 10, 0, 0, hflip=True, vflip=True)]), bytes(vram), 0, 0, 0x1000)
        self.assertEqual(lay.color[17, 17], 5)          # (0,0) do tile vai para o canto oposto
        self.assertEqual(lay.tile_px[17, 17], 0)

    def test_render_frente_e_menor_indice(self):
        vram = bytearray(0x10000)
        vram[0:32], vram[32:64] = tile(4), tile(6)
        lay = ppu.render_obj(build_oam([oam_entry(10, 10, 0, 1), oam_entry(12, 10, 1, 2)]), bytes(vram), 0, 0, 0x1000)
        self.assertEqual(lay.oam[10, 13], 0)
        self.assertEqual(lay.color[10, 13], 4)

    def test_time_over_derruba_os_de_maior_prioridade(self):
        """35 fatias (1 + 17 sprites 16x16) numa linha: o hardware carrega do último para o primeiro, então
        quem perde a fatia é o sprite 0 — o de MAIOR prioridade. (Com 35 sprites 8x8 agiria o limite de 32.)"""
        vram = bytearray(0x10000)
        vram[0:32] = tile(1)
        vram[32:64] = tile(2)
        ents = [oam_entry(0, 20, 1, 0)] + [oam_entry(4 + 14 * i, 20, 0, 0) for i in range(17)]
        lay = ppu.render_obj(build_oam(ents, {i: 2 for i in range(1, 18)}), bytes(vram), 0, 0, 0x1000)
        self.assertIn(20, lay.dropped_lines)
        self.assertNotEqual(lay.oam[20, 0], 0)
        self.assertEqual(lay.oam[20, 4], 1)

    def test_falsa_cor(self):
        cols = np.array(ppu.FALSE_COLORS, dtype=np.int32)
        self.assertEqual(len(set(ppu.FALSE_COLORS)), 256)
        img = ppu.bgr555_array_to_rgb(cols.reshape(16, 16))
        dec = ppu.decode_false_color(img)
        self.assertTrue((dec == np.arange(256).reshape(16, 16)).all())
        blend = (img.astype(int) // 2).astype(np.uint8)       # color math / meia intensidade
        self.assertTrue((ppu.decode_false_color(blend) == -1).all())

    def test_job_ppu_no_lua(self):
        t = Job(frames=10, ppu_frames=[3, 3, 5], false_color=[5], capture_frames=[5], wram_frames=[5]).to_lua_table(Path("/tmp/x"))
        self.assertEqual(t["ppu_frames"], [3, 5])
        self.assertEqual(t["false_color"], [5])
        self.assertEqual(len(t["false_color_values"]), 256)
        self.assertEqual(t["capture"]["frames"], [5])
        self.assertEqual(t["wram_frames"], [5])
        self.assertNotIn("ppu_frames", Job(frames=10).to_lua_table(Path("/tmp/x")))

    def test_leitura_dos_snapshots(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            oam, vram, cgram, _ = scene()
            (d / "ppu.bin").write_bytes((oam + cgram + vram) * 2)
            (d / "ppu_index.jsonl").write_text('{"frame":3,"event":"start","oamMode":0}\n{"frame":7,"event":"irq@215"}\n')
            snaps = read_ppu(d)
            self.assertEqual(sorted(snaps), [3, 7])
            self.assertEqual(snaps[7].oam, oam)
            self.assertEqual(len(oam + cgram + vram), PPU_SNAPSHOT_SIZE)
            (d / "wram.bin").write_bytes(bytes(0x20000) + b"\x01" * 0x20000)
            (d / "wram_index.csv").write_text("frame\n4\n9\n")
            w = read_wram(d)
            self.assertEqual(sorted(w), [4, 9])
            self.assertEqual(w[9][0], 1)


class ObjectsAndPartsTests(unittest.TestCase):
    def setUp(self):
        oam, vram, cgram, cg = scene()
        self.fd = frame_from(oam, vram, cgram, cg)

    def test_objetos(self):
        objs = find_objects(self.fd)
        self.assertEqual([o.palette for o in objs], [6, 7])
        a = objs[0]
        self.assertEqual(a.cgram_palette, 14)
        self.assertEqual(a.oam, [0, 1])
        self.assertIn(14, a.counts)
        self.assertEqual(self.fd.agreement()["fracao"], 1.0)

    def test_componentes(self):
        m = np.zeros((10, 10), bool)
        m[1:3, 1:3] = True
        m[6, 6] = True
        comps = components(m)
        self.assertEqual([len(c) for c in comps], [4, 1])

    def test_regioes_rotulos_e_censo(self):
        obj = find_objects(self.fd)[0]
        regs = regions(self.fd, 6, [14], obj)
        self.assertEqual([len(r) for r in regs], [64, 63])    # "cabelo" (tile 0 do 16x16) e "luva" (8x8 abaixo)
        with tempfile.TemporaryDirectory() as d:
            store = PartStore(Path(d) / "parts.json")
            lay = self.fd.layer()
            hair, glove = regs
            self.assertTrue((lay.oam[glove[:, 0], glove[:, 1]] == 1).all())
            self.assertEqual(store.add("luva", pixel_keys(self.fd, glove)), (63, 0))
            self.assertEqual(store.add("cabelo", pixel_keys(self.fd, hair)), (64, 0))
            self.assertEqual(store.add("luva", pixel_keys(self.fd, hair[:3])), (0, 3))   # conflito não sobrescreve
            store.save("teste")
            again = PartStore(Path(d) / "parts.json")
            m = (lay.palette == 6) & (lay.color == 14)
            lab, parts = classify(self.fd, again, m, grow=False)
            self.assertEqual(int((lab == parts.index("luva")).sum()), 63)
            c = census([self.fd], again, 6, [14], "luva")
            self.assertEqual(c["separabilidade"], {"so_alvo": 1, "so_outras": 1, "misturados": 0})
            self.assertEqual(c["frames_100"], 1)

    def test_rotulo_por_conteudo_vale_em_outro_slot(self):
        """O mesmo desenho num slot diferente da VRAM herda o rótulo (o nº do tile é ambíguo; o conteúdo não)."""
        oam, vram, cgram, cg = scene()
        with tempfile.TemporaryDirectory() as d:
            store = PartStore(Path(d) / "p.json")
            lay = self.fd.layer()
            glove = np.argwhere(lay.oam == 1)
            store.add("luva", pixel_keys(self.fd, glove))
            v2 = bytearray(vram)
            v2[0x80:0xA0] = vram[0x40:0x60]               # o desenho da luva agora no tile 4
            oam2 = build_oam([oam_entry(40, 50, 0, 6), oam_entry(40, 66, 4, 6)], {0: 2})
            fd2 = frame_from(oam2, bytes(v2), cgram, cg)
            m = (fd2.layer().oam == 1)
            lab, parts = classify(fd2, store, m, grow=False)
            self.assertTrue((lab[m] == parts.index("luva")).all())


class PaletteSearchTests(unittest.TestCase):
    def test_busca_de_palavras_com_bit15(self):
        data = bytearray(64)
        seq = [0x011E, 0x001B, 0x0017]
        for i, v in enumerate(seq):
            v |= 0x8000 if i == 1 else 0                  # bit 15 ligado na ROM: a CGRAM ignora
            data[11 + 2 * i], data[12 + 2 * i] = v & 0xFF, v >> 8
        self.assertEqual(_search_words(bytes(data), seq), [11])

    def test_origem_da_paleta(self):
        rom = bytearray(0x10000)
        pal = [0x320C, 0x0842] + [0x1000 + i for i in range(14)]
        for i, v in enumerate(pal):
            rom[0x8260 + 2 * i], rom[0x8261 + 2 * i] = v & 0xFF, v >> 8
        wram = bytearray(0x20000)
        for i, v in enumerate([0x7FFF] + pal[1:]):
            wram[0x6C0 + 2 * i], wram[0x6C1 + 2 * i] = v & 0xFF, v >> 8
        src = find_palette_sources([0x7FFF] + pal[1:], bytes(rom), "lorom", bytes(wram))
        self.assertEqual(src["rom"][0]["pc"], "0x008262")
        self.assertEqual(src["rom"][0]["indice_inicial"], 1)
        self.assertEqual(src["wram"][0]["addr"], "7E:06C0")


class RampTests(unittest.TestCase):
    GI = [0x011E, 0x001B, 0x0017, 0x0013, 0x0011]

    def test_candidatas_preservam_o_sombreado(self):
        for alvo in ("azul", "verde", "preto", "#f070b0", "branco"):
            for r in make_ramps(self.GI, parse_target(alvo), outline=[0x0842]):
                Ls = [lch(c)[0] for c in r.colors]
                self.assertEqual(sorted(range(5), key=lambda i: -Ls[i]), list(range(5)), f"{alvo} {r.name}")
                self.assertEqual(len(set(r.colors)), 5, f"{alvo} {r.name} {r.colors}")
                self.assertNotIn(0x0842, r.colors)

    def test_conferencias(self):
        ok, msgs = check_ramp(self.GI, [0x1084] * 5, outline=[0x0842])
        self.assertFalse(ok)                               # tom único: achata
        self.assertTrue(any("IGUAIS" in m for m in msgs))
        ok, _ = check_ramp(self.GI, [0x0842, 0x1000, 0x0C00, 0x0800, 0x0400], outline=[0x0842])
        self.assertFalse(ok)                               # igual ao contorno
        self.assertEqual(parse_target("preto"), ppu.parse_color("#202024"))


class PaintAndBuildTests(unittest.TestCase):
    def test_asar_org_e_data_por_pc(self):
        self.assertEqual(asar_org(0x1F0272, "sdd1"), 0xBE8272)
        self.assertEqual(asar_org(0x3C49B1, "sdd1"), 0xF8C9B1)     # 2.º par de MiB: org LoROM, não a janela $FC
        self.assertEqual(pc_to_snes(0x3C49B1, "sdd1"), 0xFC49B1)   # … a CPU vê por $FC
        self.assertEqual(asar_org(0x012345, "hirom"), 0xC12345)
        self.assertEqual(snes_to_pc(asar_org(0x2420, "lorom"), "lorom"), 0x2420)
        r = parse_data_regions([{"pc": "0x3C49B1", "length": 4, "evidence": "marcas"}], "sdd1")[0]
        self.assertEqual((r["start_pc"], r["addr"]), (0x3C49B1, "FC:49B1"))

    def test_runs_de_indices(self):
        self.assertEqual(_runs([9, 10, 11, 14, 15, 3]), [[3], [9, 10, 11], [14, 15]])

    def test_check_de_pintura_classifica_pixeis(self):
        oam, vram, cgram, cg = scene()
        fd = frame_from(oam, vram, cgram, cg)
        spec = {"palettes": [{"set": {"14": "$2908"}, "original": {"14": "$339E"}}]}
        exp = expected_changes(spec, fd.colors)
        self.assertEqual(exp, {16 * 14 + 14: 0x2908})
        mod = fd.real.copy()
        tgt = fd.index == 16 * 14 + 14
        mod[tgt] = ppu.bgr555_to_rgb(0x2908)
        mod[100, 150] = (1, 2, 3)                           # um píxel colateral (no objeto B)
        k = classify_frame(fd, mod, exp)["counts"]
        self.assertEqual((k["esperado"], k["colateral"], k["faltou"], k["cor_errada"]), (int(tgt.sum()), 1, 0, 0))

    def test_linha_de_fonte_e_instrucao(self):
        self.assertEqual(_source_instruction("    lda.b #$08   ; x"), "lda.b #$08")
        self.assertEqual(_source_instruction("Rotina: sta.l $7E0660,x"), "sta.l $7E0660,x")
        self.assertEqual(_source_instruction(".copia"), None)
        self.assertIsNone(_source_instruction("    dw $7E06, $7102"))
        self.assertEqual(_source_instruction("    autoclean jml Espelho"), "jml Espelho")

    def test_imediato_de_16_bits_com_m8_e_acusado(self):
        """O bug do espelho pela metade: `lda #$0008` montado como A9 08 00 num ponto com M=8."""
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "p.asm").write_text("Entrada:\n    lda #$0008\n    sta $10\n    rts\n", encoding="utf-8")
            rom = bytearray(0x10000)
            code = bytes([0xA9, 0x08, 0x00, 0x85, 0x10, 0x60])
            rom[0x0100:0x0106] = code
            sym = d / "m.sym"
            sym.write_text("[labels]\n80:8100 Entrada\n\n[source files]\n0000 00000000 " + str(d / "p.asm") +
                           "\n\n[addr-to-line mapping]\n80:8100 0000:00000002\n80:8103 0000:00000003\n"
                           "80:8105 0000:00000004\n", encoding="utf-8")
            bad = verify_code_widths(bytes(rom), "lorom", sym, [(0x808100, True, True)])
            self.assertTrue(bad["issues"] and "p.asm:2" in bad["issues"][0], bad)
            good = verify_code_widths(bytes(rom), "lorom", sym, [(0x808100, False, True)])   # com M=16 está certo
            self.assertEqual(good["issues"], [])
            self.assertEqual(good["instructions"], 3)


class GenericTargetsTests(unittest.TestCase):
    """Alvos genéricos (qualquer jogo): áreas de BG pela falsa cor, paleta inteira, tiles crus, níveis de separação."""

    def test_areas_de_bg_e_paleta(self):
        idx = np.zeros((224, 256), np.int16)
        idx[10:40, 10:60] = 16 * 6 + 5          # "retrato": paleta CGRAM 6, índice 5
        idx[20:30, 20:30] = 16 * 6 + 8
        idx[100:110, 100:200] = 16 * 1 + 3      # outra área, paleta 1
        fd = FrameData(1, np.zeros((224, 256, 3), np.uint8), idx, None)
        areas = find_bg_areas(fd)
        self.assertEqual([(a.cgram_palette, a.pixels) for a in areas], [(6, 1500), (1, 1000)])
        self.assertEqual(areas[0].counts, {5: 1400, 8: 100})
        t = palette_target(fd, 6, (0, 0, 30, 30))
        self.assertEqual(t.pixels, 400)
        col = color_index_map(fd, areas[0])
        self.assertEqual(int(col[25, 25]), 8)
        self.assertEqual(int(col[105, 150]), -1)

    def test_tiles_crus(self):
        oam, vram, cgram, cg = scene()
        fd = frame_from(oam, vram, cgram, cg)
        obj = find_objects(fd)[0]
        tiles = object_tiles(fd, obj, [14])
        self.assertEqual(sorted(t["vram"] for t in tiles), [0x00, 0x40])
        rom = bytes(100) + tiles[0]["bytes"] + bytes(50)
        self.assertEqual(find_raw_tile(rom, tiles[0]["bytes"]), [100])
        self.assertEqual(find_raw_tile(rom, bytes(32)), [])          # tile vazio nunca conta

    def test_remap_de_desenho_no_check(self):
        """Píxeis de um tile remapeado (pelo hash do conteúdo) são alvo; a cor esperada é a do índice novo."""
        oam, vram, cgram, cg = scene()
        fd = frame_from(oam, vram, cgram, cg)
        glove = bytes(vram[0x40:0x60])
        new = ppu.decode_4bpp(glove).copy()
        new[new == 14] = 9
        from snesfab.sprites import tile_hash
        spec = {"palettes": [], "tiles": [{"hash": tile_hash(vram, 0x40), "new": ppu.encode_4bpp(new).hex()}]}
        mod = fd.real.copy()
        lay = fd.layer()
        m = lay.oam == 1
        mod[m] = ppu.bgr555_to_rgb(int(cg[16 * 14 + 9]))
        k = classify_frame(fd, mod, {}, spec)["counts"]
        self.assertEqual((k["esperado"], k["colateral"], k["cor_errada"]), (63, 0, 0))

    def test_niveis_de_separabilidade(self):
        from collections import Counter
        t = lambda **kw: Counter(kw)  # noqa: E731
        self.assertEqual(separability_levels({"so_alvo": 5, "so_outras": 0, "misturados": 0}, {1: t(alvo=5)})["nivel"], 1)
        self.assertEqual(separability_levels({"so_alvo": 5, "so_outras": 3, "misturados": 0},
                                             {1: t(alvo=5), 2: t(outra=3)})["nivel"], 2)
        lv = separability_levels({"so_alvo": 5, "so_outras": 3, "misturados": 0}, {1: t(alvo=2, outra=3)})
        self.assertEqual((lv["nivel"], lv["tiles_ambiguos"]), (3, 1))
        self.assertEqual(separability_levels({"so_alvo": 5, "so_outras": 3, "misturados": 2},
                                             {1: t(alvo=2, misto=2)})["nivel"], 4)

    def test_regioes_vizinhas_se_juntam(self):
        regs = _merge_regions([{"pc": "0x100", "length": 32, "evidence": "a"}, {"pc": "0x121", "length": 32, "evidence": "b"},
                               {"pc": "0x200", "length": 2, "evidence": "c"}])
        self.assertEqual([(r["pc"], r["length"]) for r in regs], [("0x100", 0x41), ("0x200", 2)])
        self.assertIn("b", regs[0]["evidence"])

    def test_resumo_do_dma(self):
        class Rom:
            mapping, data = "lorom", bytes(0x10000)

            def to_pc(self, addr):
                from snesfab.rom import snes_to_pc
                return snes_to_pc(addr, "lorom")
        ev = [{"kind": "dma", "frame": f, "scanline": 225, "ch": 0, "dmap": 0, "bbad": 0x22, "src": 0x7E0500, "size": 512,
               "vram": 0, "cgram": 0, "oam": 0, "fb": False, "k": 0x80, "pc": 0x8123, "ps": 0x20, "dbr": 0} for f in range(3)]
        ev.append({"kind": "dma", "frame": 1, "scanline": 225, "ch": 1, "dmap": 0, "bbad": 0x04, "src": 0x000200, "size": 544,
                   "vram": 0, "cgram": 0, "oam": 0, "fb": False, "k": 0x80, "pc": 0x8130, "ps": 0x30, "dbr": 0})
        rep = dma_summarize(ev, Rom())
        rows = {r["destino"]: r for r in rep["transferencias"]}
        self.assertEqual(rows["CGRAM"]["fonte"], "7E:0500")
        self.assertEqual(rows["CGRAM"]["frames"], 3)
        self.assertIn("buffer de PALETAS", rows["CGRAM"]["leitura"])
        self.assertEqual(rows["OAM"]["fonte"], "7E:0200")             # espelho baixo da WRAM
        self.assertTrue(any(line.startswith("paleta:") for line in rep["resumo"]))


class OamMirrorGeneratorTests(unittest.TestCase):
    """Gerador do nível 2 (sem emulador): escolha do hijack e o .asm gerado."""

    class Rom:
        mapping = "lorom"

        def __init__(self, data):
            self.data = data

        def to_pc(self, addr):
            return snes_to_pc(addr, "lorom")

        def to_snes(self, pc):
            return pc_to_snes(pc, "lorom")

    def rom(self, code: bytes, at: int = 0x2CB) -> "OamMirrorGeneratorTests.Rom":
        data = bytearray(0x8000)
        data[at:at + len(code)] = code
        return self.Rom(bytes(data))

    def test_hijack_de_instrucoes_inteiras(self):
        from snesfab.oamhook import choose_hijack
        rom = self.rom(bytes([0xA9, 0x01, 0x8D, 0x0B, 0x42, 0x60]))       # LDA #$01 / STA $420B / RTS
        hj = choose_hijack(rom, 0x8082D0, True, False)
        self.assertEqual((hj["pc"], hj["length"], hj["bytes"]), (0x2CB, 5, bytes([0xA9, 0x01, 0x8D, 0x0B, 0x42])))

    def test_hijack_recusa_desvio(self):
        from snesfab.oamhook import choose_hijack
        rom = self.rom(bytes([0xD0, 0x00, 0x8D, 0x0B, 0x42]), at=0x2CB + 1)   # BNE logo antes: não serve
        with self.assertRaises(Exception):
            choose_hijack(rom, 0x8082D1 + 4, True, False)

    def test_asm_gerado(self):
        from snesfab.oamhook import generate
        rom = self.rom(bytes([0xA9, 0x01, 0x8D, 0x0B, 0x42, 0x60]))
        asm, hj = generate(rom=rom, oam_shadow=0x7E0200, trigger_next=0x8082D0, m8=True, x8=False, src_palette=6,
                           mirror_palette=3, tiles=[0x0C, 0x10E], colors={14: 0x2908, 15: 0x1084}, pal_buffer=0x7E0500,
                           evidence="teste")
        self.assertIn("org $8082CB", asm)
        self.assertIn("cmp.b #$0C            ; paleta de origem?", asm)          # 6 << 1
        self.assertIn("ora.b #$06            ; → paleta-espelho", asm)           # 3 << 1
        self.assertIn("lda.l $7E06C0,x", asm)                                  # buffer + 2·(128+16·6)
        self.assertIn("sta.l $7E0660,x", asm)                                  # buffer + 2·(128+16·3)
        self.assertIn("db $A9,$01,$8D,$0B,$42", asm)                           # bytes originais copiados
        self.assertEqual((hj["addr"], hj["m"], hj["x"]), ("80:82CB", 8, 16))
        with self.assertRaises(Exception):
            generate(rom=rom, oam_shadow=0x7E0200, trigger_next=0x8082D0, m8=True, x8=False, src_palette=3,
                     mirror_palette=3, tiles=[1], colors={1: 0}, pal_buffer=None, evidence="x")


class TilesetExportTests(unittest.TestCase):
    """Export do tileset pela VRAM (qualquer jogo): origem de cada tile, dedupe por conteúdo, mapas fora."""

    class Rom:
        mapping = "lorom"

        def __init__(self, data):
            self.data = data

        def to_pc(self, addr):
            return snes_to_pc(addr, "lorom")

    def test_decodifica_2_4_e_8_bpp(self):
        from snesfab.gfx import decode_tile
        px = np.arange(64, dtype=np.uint8).reshape(8, 8) % 16
        self.assertTrue((decode_tile(ppu.encode_4bpp(px), 4) == px).all())
        two = bytes([0xFF, 0x00] * 8)                      # plano 0 cheio → índice 1
        self.assertTrue((decode_tile(two, 2) == 1).all())
        eight = bytes(48) + bytes([0xFF, 0x00] * 8)       # plano 6 cheio → índice 64
        self.assertTrue((decode_tile(eight, 8) == 64).all())

    def test_origem_e_dedupe(self):
        from snesfab.gfx import collect, tilemap_regions
        tile_a = ppu.encode_4bpp(np.full((8, 8), 3, np.uint8))
        tile_b = ppu.encode_4bpp(np.full((8, 8), 5, np.uint8))
        rom = bytearray(0x10000)
        rom[0x100:0x120] = tile_a
        r = self.Rom(bytes(rom))
        ups = [
            {"frame": 0, "start": 0x0000, "size": 32, "src": 0x808100, "mode": 1, "data": tile_a},      # cru na ROM
            {"frame": 1, "start": 0x0020, "size": 32, "src": 0x808200, "mode": 1, "data": tile_b},      # ROM ≠ dado
            {"frame": 2, "start": 0x0040, "size": 32, "src": 0x7E2000, "mode": 1, "data": tile_a},      # WRAM, repetido
            {"frame": 3, "start": 0x0060, "size": 32, "src": 0x808300, "mode": 9, "data": bytes(32)},   # preenchimento
            {"frame": 4, "start": 0x0080, "size": 32, "src": 0x808400, "mode": 9, "data": tile_b[::-1]}, # chip (fonte fixa)
        ]
        tiles = collect(ups, r, 4, [(0, 0x2000)])
        self.assertEqual(len(tiles), 3)                     # vazio fora; tile_a contado uma vez
        by_raw = {t.raw: t for t in tiles.values()}
        self.assertEqual(dict(by_raw[tile_a].origins), {"cru": 1, "wram": 1})
        self.assertEqual(dict(by_raw[tile_b].origins), {"transformado": 1})
        self.assertEqual(dict(by_raw[tile_b[::-1]].origins), {"transformado": 1})
        self.assertEqual(tilemap_regions({"layers[0].tilemapAddress": 0x1000, "layers[0].doubleWidth": True}),
                         [(0x2000, 0x3000)])



class GfxOverrideTests(unittest.TestCase):
    """Override de gráfico sem codec (sem emulador): impressão digital, plano por bloco e o .asm gerado."""

    Rom = OamMirrorGeneratorTests.Rom
    TRIG = 0x8082D0                       # PC seguinte ao STA $420B em 80:82CD (LDA #$01 em 80:82CB)

    def rom(self, code=bytes([0xA9, 0x01, 0x8D, 0x0B, 0x42, 0x60]), at=0x2CB):
        data = bytearray(0x8000)
        data[at:at + len(code)] = code
        return self.Rom(bytes(data))

    @staticmethod
    def tile(v):
        return ppu.encode_4bpp(np.full((8, 8), v, np.uint8))

    def upload(self, src, data, mode=1, linear=True, frame=3):
        return {"frame": frame, "start": 0x1000, "size": len(data), "src": src, "mode": mode, "data": data,
                "linear": linear, "k": self.TRIG >> 16, "pc": self.TRIG & 0xFFFF, "ps": 0x20, "ch": 0}

    def test_tile_ida_e_volta_2_4_8_bpp(self):
        from snesfab.gfx import decode_tile, encode_tile
        rng = np.random.default_rng(7)
        for bpp in (2, 4, 8):
            px = rng.integers(0, 1 << bpp, (8, 8)).astype(np.uint8)
            self.assertTrue((decode_tile(encode_tile(px, bpp), bpp) == px).all(), bpp)

    def test_impressao_separa_os_conteudos_do_buffer(self):
        from snesfab.gfxoverride import choose_fingerprint
        a = bytes(range(64))
        b = bytearray(a)
        b[40] ^= 0xFF
        fp = choose_fingerprint(a, [bytes(b)], 0x7F0000)
        self.assertTrue(any(o <= 40 < o + len(w) for o, w in fp))
        self.assertTrue(all(a[o:o + len(w)] == w for o, w in fp))
        with self.assertRaises(Exception):
            choose_fingerprint(a, [a], 0x7F0000)              # idênticos: impossível separar

    def test_selecao_e_mapa(self):
        from snesfab.gfxoverride import parse_map, parse_selection
        idx = [{"n": 1, "hash": "a" * 12}, {"n": 2, "hash": "b" * 12}, {"n": 3, "hash": "c" * 12}]
        self.assertEqual(parse_selection("1-2, 3, 2", idx), ["a" * 12, "b" * 12, "c" * 12])
        self.assertEqual(parse_selection("dddddddddddd", idx), ["d" * 12])
        self.assertEqual(parse_map("14:9,15:12", 4), {14: 9, 15: 12})
        for bad in ("16:1", "1-2", "x:1"):
            with self.assertRaises(Exception):
                parse_map(bad, 4)
        with self.assertRaises(Exception):
            parse_selection("9", idx)

    def blocks(self, rom):
        from snesfab.gfxoverride import _h, plan
        a = self.tile(1) + self.tile(2)
        b = self.tile(4) + self.tile(5)
        c = self.tile(7)
        edits = {_h(self.tile(1)): self.tile(3), _h(c): self.tile(6)}
        dump = {"bpp": 4, "uploads": [
            self.upload(0x7F0000, a), self.upload(0x7F0000, b),                    # mesmo buffer, dois conteúdos
            self.upload(0x808400, c, mode=9),                                        # chip: fonte fixa transformada
            self.upload(0x808800, c, mode=9), self.upload(0x808800, self.tile(8), mode=9),   # fonte ambígua
            self.upload(0x7E4000, a, linear=False)]}                                  # não linear
        return plan(dump, edits, rom), a, b

    def test_plano(self):
        p, a, b = self.blocks(self.rom())
        self.assertEqual([(x.kind, x.src) for x in p["blocks"]], [("wram", 0x7F0000), ("rom", 0x808400)])
        wram, chip = p["blocks"]
        self.assertEqual(wram.new, self.tile(3) + self.tile(2))
        (off, win), = wram.fingerprint
        self.assertNotEqual(a[off:off + 8], b[off:off + 8])
        self.assertEqual(win, a[off:off + 8])
        self.assertEqual(chip.fingerprint, [])
        self.assertEqual(sorted(s["fonte"][:7] for s in p["skipped"]), ["7E:4000", "80:8800"])

    def test_asm_com_tabela_em_espaco_livre(self):
        from snesfab.gfxoverride import generate
        rom = self.rom()
        p, _, _ = self.blocks(rom)
        gen = generate(rom, p["blocks"], chip_disarm=[(0x004801, 0x00)], evidence="teste")
        asm = gen["asm"]
        for frag in ("prot GfxOvrConfere, GfxOvrDevolve, GfxOvrTabela, GfxNovo1, GfxNovo2", "org $8082CB",
                     "autoclean jml GfxOvr1", "jsl GfxOvrDevolve", "lda.l GfxOvrTabela+11,x",
                     "lda $06,s", "db $A9,$01", "db $8D,$0B,$42", "jml $8082D0", "jsl GfxOvrConfere",
                     "lda.l GfxOvrTabela+0,x", "cpx.w #$0030", "and.b #$E7", "sta.l $004801",
                     "dw GfxNovo1&$FFFF : db GfxNovo1>>16, $08 : dw $0000 : db $01",
                     "dw GfxNovo2&$FFFF : db GfxNovo2>>16, $03 : dw $0000 : db $09", "freedata"):
            self.assertIn(frag, asm)
        self.assertNotIn("sei", asm)                                   # sem janela de chip: sem troca nem SEI
        self.assertIsNone(gen["blob"])
        h = gen["hijacks"][0]
        self.assertEqual((h["addr"], h["m"], h["x"]), ("80:82CB", 8, 16))
        self.assertEqual([v["label"] for v in h["verify"]], ["GfxOvr1Corpo", "GfxOvr1Volta", "GfxOvrConfere", "GfxOvrDevolve"])
        self.assertEqual(gen["avisos"], [])

    def test_blob_na_area_expandida_do_sdd1_usa_a_janela(self):
        from snesfab.gfxoverride import ENTRY, generate
        from snesfab.rom import pc_to_snes, snes_to_pc

        class Sdd1:
            mapping = "sdd1"
            data = bytes(0x400000)

            def to_pc(self, addr):
                return snes_to_pc(addr, "sdd1")

            def to_snes(self, pc):
                return pc_to_snes(pc, "sdd1")

        rom = Sdd1()
        code = bytes([0xA9, 0x01, 0x8D, 0x0B, 0x42, 0x60])
        rom.data = bytes(0x2CB) + code + bytes(0x400000 - 0x2CB - len(code))
        p, _, _ = self.blocks(rom)
        chip = [b for b in p["blocks"] if b.kind == "rom"]
        gen = generate(rom, chip, chip_disarm=[(0x004801, 0x00)], data_at=0x400000, data_evidence="área nova")
        asm, blob = gen["asm"], gen["blob"]
        self.assertEqual(gen["window"], {"reg": 0x004807, "page": 4, "restore": 3})
        for frag in ("sei", "lda.b #$04", "sta.l $004807", "lda.b #$03", "lda $07,s", "lda.l $F00008,x",
                     "prot GfxOvrConfere, GfxOvrDevolve", "lda.l $F00013,x"):
            self.assertIn(frag, asm)
        self.assertNotIn("GfxOvrTabela", asm)
        self.assertEqual(blob[:4], b"STAR")
        entry = blob[8:8 + ENTRY]
        self.assertEqual((entry[0], entry[1:3], entry[3:5]), (0x80, bytes([0x00, 0x84]), bytes([0x20, 0x00])))
        self.assertEqual((entry[5:8], entry[8]), (bytes([0x20, 0x00, 0xF0]), 0x03))   # cópia em $F0:0020; fixo + desarme
        self.assertEqual(entry[11], 0x09)                                                # DMAP do jogo (devolvido)
        self.assertEqual(blob[0x20:0x40], chip[0].new)
        self.assertEqual(gen["data"][0]["pc"], "0x400000")
        self.assertTrue(any("janela" in a for a in gen["avisos"]))

    def test_colocacao_nao_cruza_banco(self):
        from snesfab.gfxoverride import place
        rom = self.Rom(bytes(0x100000))
        self.assertEqual(place([0x100, 0x7F00], 0x7F80, rom), [0x8000, 0x8100])

    def test_hijack_com_stx_e_aviso_de_desvio(self):
        from snesfab.oamhook import choose_hijack
        rom = self.rom(bytes([0xA2, 0x01, 0x8E, 0x0B, 0x42, 0x60]))           # LDX #$01 / STX $420B (x8)
        hj = choose_hijack(rom, self.TRIG, True, True)
        self.assertEqual((hj["store"], hj["sizes"], hj["avisos"]), ("STX", [2, 3], []))
        code = bytes([0x80, 0x04, 0xEA, 0xEA, 0xA9, 0x01, 0x8D, 0x0B, 0x42])     # BRA para o STA, no meio do hijack
        rom = self.rom(code, at=0x2CB - 4)
        hj = choose_hijack(rom, self.TRIG, True, False)
        self.assertTrue(any("desvio" in a for a in hj["avisos"]), hj["avisos"])

if __name__ == "__main__":
    unittest.main()
