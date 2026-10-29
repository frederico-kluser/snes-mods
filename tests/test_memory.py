"""Memória CoALA versionada (snesfab/memory.py): dump em dia, restore fiel ao dump e o arquivo que vai para o git."""

import json
import re
import tempfile
import unittest
from pathlib import Path

from snesfab import memory
from snesfab.util import FabError


def base(d: Path, name: str, *notes: tuple[str, str]) -> Path:
    db = d / f"{name}.sqlite"
    memory._run("init", db=db)
    for key, content in notes:
        memory._run("add", "--type", "semantic", "--key", key, "--content", content, db=db)
    return db


class MemoryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = Path(tmp.name)

    def state(self, db: Path, dump: Path) -> str:
        return memory.dump_state(db=db, dump=dump, check_sync=False)[0]

    def test_dump_em_dia_e_crlf(self):
        db, dump = base(self.d, "a", ("fato-a", "fato A")), self.d / "a.jsonl"
        self.assertEqual(self.state(db, dump), "stale")                    # ainda sem dump
        memory.dump(db=db, out=dump, sync=False)
        self.assertEqual(self.state(db, dump), "ok")
        lf = dump.read_bytes()
        self.assertNotIn(b"\r\n", lf)                                       # o dump sai com LF em qualquer SO
        dump.write_bytes(lf.replace(b"\n", b"\r\n"))                        # checkout com CRLF = o mesmo dump
        self.assertEqual(self.state(db, dump), "ok")
        memory._run("add", "--type", "semantic", "--key", "fato-b", "--content", "fato B", db=db)
        self.assertEqual(self.state(db, dump), "stale")
        self.assertEqual(self.state(self.d / "nada.sqlite", dump), "absent")

    def test_restore_reproduz_o_dump(self):
        db, dump = base(self.d, "a", ("fato-a", "fato A")), self.d / "a.jsonl"
        memory._run("supersede", "1", "--content", "fato A corrigido", db=db)
        memory.dump(db=db, out=dump, sync=False)
        clone = self.d / "clone.sqlite"
        memory.restore(sync=False, db=clone, src=dump)
        self.assertEqual(self.state(clone, dump), "ok")                    # byte a byte, proveniência inclusive
        self.assertNotIn("Importado de", dump.read_text(encoding="utf-8"))
        with self.assertRaises(FabError):                                   # base existente sem --force
            memory.restore(sync=False, db=clone, src=dump)

    def test_force_so_mexe_no_que_importou(self):
        local = base(self.d, "local", ("so-local", "nota só desta máquina"))
        remoto, dump = base(self.d, "remoto", ("de-outra", "nota de outra máquina")), self.d / "remoto.jsonl"
        memory.dump(db=remoto, out=dump, sync=False)
        memory.restore(force=True, sync=False, db=local, src=dump)
        out = self.d / "local.jsonl"
        memory.dump(db=local, out=out, sync=False)
        recs = {r["content"]: r for r in map(json.loads, out.read_text(encoding="utf-8").splitlines())}
        remote = json.loads(dump.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(recs["nota de outra máquina"]["provenance"], remote["provenance"])
        self.assertNotIn("Importado de", recs["nota só desta máquina"]["provenance"])


class DumpVersionadoTests(unittest.TestCase):
    """O dump vai para o git público: JSONL íntegro (sem marcas de merge) e sem caminho local de máquina."""

    def test_dump_versionado(self):
        if not memory.DUMP.exists():
            self.skipTest("sem dump versionado")
        local = re.compile(r"[A-Za-z]:\\\\Users\\\\|/home/[^/\s]+/|/Users/[^/\s]+/")
        for n, line in enumerate(memory.DUMP.read_text(encoding="utf-8").splitlines(), 1):
            with self.subTest(linha=n):
                rec = json.loads(line)
                self.assertTrue({"cid", "content", "kind"} <= set(rec))
                self.assertIsNone(local.search(line))


if __name__ == "__main__":
    unittest.main()
