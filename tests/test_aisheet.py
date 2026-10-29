"""Testes do pipeline de tilesheet para edição por IA (fab ai export/import/roundtrip).

Tudo sintético (sem emulador): poses fabricadas com tiles coerentes (os bytes do tile reproduzem os
índices da pose) para exercitar export → mapa → re-quantização → plano de tiles → limpeza.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from snesfab import aisheet, ppu

CORES = [0, 0x001F, 0x03E0, 0x7C00, 0x03FF, 0x7C1E, 0x7FE0, 0x3DEF,
         0x1084, 0x2108, 0x318C, 0x4631, 0x56B5, 0x6739, 0x7BDE, 0x7FFF]


def make_pose(indices: np.ndarray, x: int = 0, y: int = 0, flip: tuple[bool, bool] = (False, False),
              oam: int = 1, frame: int = 1) -> aisheet.Pose:
    """Pose com UM tile 8x8 cujos bytes reproduzem `indices` (máx. 8x8)."""
    h, w = indices.shape
    raw = ppu.encode_4bpp(indices)
    hsh = hashlib.sha1(raw).hexdigest()[:12]
    inst = aisheet.TileInstance(hsh, x, y, flip[0], flip[1], 0x2000, oam, raw)
    return aisheet.Pose(f"p-{frame}", frame, "sintetica", indices.copy(), [inst])


def checker(n1: int = 1, n2: int = 2) -> np.ndarray:
    """8x8 xadrez de dois índices."""
    a = np.zeros((8, 8), np.uint8)
    for yy in range(8):
        for xx in range(8):
            a[yy, xx] = n1 if (xx + yy) % 2 == 0 else n2
    return a


def unique_pattern() -> np.ndarray:
    """8x8 em que cada píxel tem um índice próprio (1-15) — alinhamento inequívoco em ambos os eixos."""
    return (1 + (np.arange(64).reshape(8, 8) % 15)).astype(np.uint8)


class RleTests(unittest.TestCase):
    def test_ida_e_volta(self):
        a = np.array([[0, 0, 1, 1], [2, 2, 2, 0]], np.uint8)
        runs = aisheet.rle_encode(a)
        b = aisheet.rle_decode(runs, 4, 2)
        self.assertTrue((a == b).all())

    def test_rle_corrompido_falha(self):
        with self.assertRaises(Exception):
            aisheet.rle_decode([[1, 3]], 4, 2)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="aisheet-"))
        self.pose1 = make_pose(checker(1, 2), frame=1)
        self.pose2 = make_pose(checker(3, 0), frame=2)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def export(self, **kw):
        kw.setdefault("fundo", "#FF00FF")
        return aisheet.export_sheet([self.pose1, self.pose2], CORES, self.dir, "teste", bloco=8, **kw)

    def test_mapa_e_folha(self):
        res = self.export(jogo="teste")
        mapa = json.loads((self.dir / "map.json").read_text(encoding="utf-8"))
        self.assertEqual(res["poses"], 2)
        self.assertEqual(mapa["versao"], 1)
        self.assertEqual(mapa["imagem"]["bloco"], 8)
        self.assertEqual(len(mapa["poses"]), 2)
        # caixa_expandida = caixa 1px × bloco
        p0 = mapa["poses"][0]
        self.assertEqual(p0["caixa_expandida"][2], p0["caixa_celula_px"][2] * 8)
        # os blocos da folha expandida são sólidos: cada bloco 8x8 tem 1 cor
        img = np.asarray(Image.open(self.dir / "sheet.png").convert("RGB"))
        X0, Y0 = p0["caixa_expandida"][0], p0["caixa_expandida"][1]
        bloco = img[Y0:Y0 + 8, X0:X0 + 8]
        self.assertEqual(len(np.unique(bloco.reshape(-1, 3), axis=0)), 1)
        self.assertTrue((self.dir / "prompt.md").exists() and (self.dir / "report.md").exists())
        # os bytes dos tiles estão no mapa
        self.assertTrue(all(t.get("bytes") for t in mapa["tiles"].values()))

    def test_prompt_tem_lock_change_constraints(self):
        self.export(mudanca="turn the gi blue")
        txt = (self.dir / "prompt.md").read_text(encoding="utf-8")
        self.assertIn("LOCK", txt)
        self.assertIn("CHANGE: turn the gi blue", txt)
        self.assertIn("CONSTRAINTS", txt)
        self.assertIn("#FF00FF", txt)

    def test_fundo_auto_contrasta_com_a_paleta(self):
        fundo = aisheet.fundo_ideal(CORES)
        rgb = tuple(int(fundo.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        cores = [ppu.bgr555_to_rgb(v) for v in CORES[1:]]
        dists = [sum((a - b) ** 2 for a, b in zip(rgb, c)) for c in cores]
        self.assertGreater(min(dists), 40 * 40 * 3, "o fundo calculado tem de ficar LONGE de toda a paleta")
        aisheet.export_sheet([self.pose1], CORES, self.dir, "auto", bloco=8)
        mapa = json.loads((self.dir / "map.json").read_text(encoding="utf-8"))
        self.assertEqual(mapa["imagem"]["fundo"], fundo)
        txt = (self.dir / "prompt.md").read_text(encoding="utf-8")
        self.assertIn(fundo, txt)


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="aisheet-"))
        self.pose1 = make_pose(checker(1, 2), frame=1)
        self.pose2 = make_pose(checker(3, 0), frame=2)
        aisheet.export_sheet([self.pose1, self.pose2], CORES, self.dir, "teste", bloco=8)
        self.mapa = aisheet.load_map(self.dir / "map.json")
        self.sheet = self.dir / "sheet.png"

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_identidade_zero_mudancas(self):
        res = aisheet.import_sheet(self.mapa, self.sheet, self.dir / "id", auto_align=False)
        self.assertEqual(res["tiles_alterados"], 0)
        self.assertEqual(res["pixeis_alterados"], 0)
        self.assertEqual(res["blocos_sujos"], 0)

    def test_mudanca_volta_ao_tile_certo(self):
        # pinta o píxel (0,0) da pose 1 com a cor do índice 3
        img = np.asarray(Image.open(self.sheet).convert("RGB")).copy()
        p0 = self.mapa["poses"][0]
        X0, Y0, bloco = p0["caixa_expandida"][0], p0["caixa_expandida"][1], self.mapa["imagem"]["bloco"]
        cores_rgb = {c["indice"]: tuple(int(c["cor"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
                     for c in self.mapa["paleta"]["cores"]}
        img[Y0:Y0 + bloco, X0:X0 + bloco] = cores_rgb[3]
        Image.fromarray(img).save(self.dir / "editada.png")
        res = aisheet.import_sheet(self.mapa, self.dir / "editada.png", self.dir / "out", auto_align=False)
        self.assertEqual(res["pixeis_alterados"], 1)
        self.assertEqual(res["tiles_alterados"], 1)
        plano = json.loads((self.dir / "out" / "plan.json").read_text(encoding="utf-8"))
        t = plano["tiles"][0]
        novo = ppu.decode_4bpp(bytes.fromhex(t["novo"]))
        self.assertEqual(int(novo[0, 0]), 3)                 # tile_px 0 = píxel (0,0)
        self.assertEqual(t["mapa"], {"0": 3})

    def test_perturbado_realinha(self):
        # pose de padrão único (o xadrez é ambíguo por paridade: qualquer deslocação par bate)
        d = Path(tempfile.mkdtemp(prefix="aisheet-"))
        try:
            pose = make_pose(unique_pattern(), frame=5)
            aisheet.export_sheet([pose], CORES, d, "uniq", bloco=8)
            mapa = aisheet.load_map(d / "map.json")
            fundo = tuple(int(mapa["imagem"]["fundo"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
            base = Image.open(d / "sheet.png").convert("RGB")
            canvas = Image.new("RGB", base.size, fundo)
            canvas.paste(base, (3, 2))
            canvas.save(d / "shift.png")
            res = aisheet.import_sheet(mapa, d / "shift.png", d / "out", auto_align=True)
            # a votação por maioria tolera deslocamentos até ~meio bloco: o que interessa é o RESULTADO
            self.assertGreaterEqual(res["alinhamento"]["concordancia"], 0.9)
            self.assertLessEqual(res["pixeis_alterados"], 64 // 4)   # só as bordas contaminadas
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_bloco_sujo_marcado_e_limpo(self):
        # pose sólida (índice 1): um bloco meio-a-meio de cor 4/2 fica sujo; os vizinhos limpos mandam
        d = Path(tempfile.mkdtemp(prefix="aisheet-"))
        try:
            pose = make_pose(np.full((8, 8), 1, np.uint8), frame=9)
            aisheet.export_sheet([pose], CORES, d, "solido", bloco=8)
            mapa = aisheet.load_map(d / "map.json")
            img = np.asarray(Image.open(d / "sheet.png").convert("RGB")).copy()
            cores_rgb = {c["indice"]: tuple(int(c["cor"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
                         for c in mapa["paleta"]["cores"]}
            p0 = mapa["poses"][0]
            X0, Y0, bloco = p0["caixa_expandida"][0], p0["caixa_expandida"][1], mapa["imagem"]["bloco"]
            bx, by = X0 + bloco, Y0 + bloco
            img[by:by + bloco, bx:bx + bloco // 2] = cores_rgb[4]
            img[by:by + bloco, bx + bloco // 2:bx + bloco] = cores_rgb[2]
            Image.fromarray(img).save(d / "sujo.png")
            res = aisheet.import_sheet(mapa, d / "sujo.png", d / "out", limpar="auto")
            self.assertGreaterEqual(res["blocos_sujos"], 1)
            plano = json.loads((d / "out" / "plan.json").read_text(encoding="utf-8"))
            sujo = [b for b in plano["blocos_sujos"] if b["px"] == [1, 1]]
            self.assertTrue(sujo)
            self.assertTrue(sujo[0].get("limpo"), "vizinhos limpos tinham maioria clara → o bloco devia ser limpo")
            self.assertEqual(res["tiles_alterados"], 0)      # limpo para o índice original → sem plano
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_conflito_entre_poses_e_reportado(self):
        # as duas poses usam tiles diferentes; força o MESMO tile nas duas com edições divergentes
        mapa = json.loads((self.dir / "map.json").read_text(encoding="utf-8"))
        mapa["poses"][1]["tiles"] = [dict(mapa["poses"][0]["tiles"][0], x=0, y=0)]
        img = np.asarray(Image.open(self.sheet).convert("RGB")).copy()
        cores_rgb = {c["indice"]: tuple(int(c["cor"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
                     for c in mapa["paleta"]["cores"]}
        bloco = mapa["imagem"]["bloco"]
        for pose, cor in ((mapa["poses"][0], 5), (mapa["poses"][1], 6)):
            X0, Y0 = pose["caixa_expandida"][0], pose["caixa_expandida"][1]
            img[Y0:Y0 + bloco, X0:X0 + bloco] = cores_rgb[cor]
        Image.fromarray(img).save(self.dir / "conflito.png")
        mapa["_dir"] = str(self.dir)
        res = aisheet.import_sheet(mapa, self.dir / "conflito.png", self.dir / "out", auto_align=False)
        self.assertEqual(res["conflitos"], 1)


class RoundtripTests(unittest.TestCase):
    def test_roundtrip_perfeito(self):
        d = Path(tempfile.mkdtemp(prefix="aisheet-"))
        try:
            pose = make_pose(unique_pattern(), frame=1)
            aisheet.export_sheet([pose], CORES, d, "rt", bloco=8)
            mapa = aisheet.load_map(d / "map.json")
            res = aisheet.roundtrip(mapa, d / "rt")
            self.assertEqual(res["veredito"], "PERFEITO")
            self.assertEqual(res["identidade"]["pixeis_alterados"], 0)
            self.assertLessEqual(res["perturbado"]["pixeis_alterados"], 64 // 4)   # só bordas do blur/deslocamento
        finally:
            shutil.rmtree(d, ignore_errors=True)


class CelFilterTests(unittest.TestCase):
    """Filtro pelas listas de cels do motor: só fica o que o personagem desenha (efeitos saem)."""

    class _E:
        def __init__(self, index, tile):
            self.index, self.tile = index, tile

    def test_efeitos_fora_da_lista_saem(self):
        from snesfab.cels import CelList
        entries = {1: self._E(1, 0x020), 2: self._E(2, 0x021), 3: self._E(3, 0x022)}   # 3 = efeito
        lists = [CelList(0x1000, [(0, 0, 0x20, 0), (8, 0, 0x21, 0)])]
        keep, excl = aisheet.filter_entries_by_cels([1, 2, 3], entries, lists)
        self.assertEqual(keep, [1, 2])
        self.assertEqual(excl, 1)

    def test_multiplicidade_respeitada(self):
        from snesfab.cels import CelList
        entries = {1: self._E(1, 0x020), 2: self._E(2, 0x020), 3: self._E(3, 0x020)}
        lists = [CelList(0x1000, [(0, 0, 0x20, 0), (8, 0, 0x20, 0)])]                  # 2 cels com o tile
        keep, excl = aisheet.filter_entries_by_cels([1, 2, 3], entries, lists)
        self.assertEqual(keep, [1, 2])
        self.assertEqual(excl, 1)

    def test_sem_lista_nao_filtra(self):
        entries = {1: self._E(1, 0x020)}
        self.assertEqual(aisheet.filter_entries_by_cels([1], entries, None)[0], [1])
        self.assertEqual(aisheet.filter_entries_by_cels([1], entries, [])[0], [1])

    def test_lista_que_nao_bate_nao_filtra(self):
        from snesfab.cels import CelList
        entries = {1: self._E(1, 0x020), 2: self._E(2, 0x021)}
        lists = [CelList(0x1000, [(0, 0, 0x77, 0), (8, 0, 0x78, 0), (16, 0, 0x79, 0), (24, 0, 0x7A, 0)])]
        keep, excl = aisheet.filter_entries_by_cels([1, 2], entries, lists)
        self.assertEqual(keep, [1, 2])
        self.assertEqual(excl, 0)


if __name__ == "__main__":
    unittest.main()
