"""Memória CoALA no git (política `track-dump`): a base SQLite fica local e o git versiona o dump canônico.

`fab memory dump` sincroniza (docs + catálogo de código) e exporta; `fab memory restore` recria a base num clone novo
(import do dump + sync); `fab memory status` (também no `fab doctor`) diz se o dump está em dia. O export mascara
segredos e é determinístico: dump em dia = nada a sincronizar e export da base igual, byte a byte, ao arquivo.
Um clone restaurado de um dump feito com `fab memory dump` exporta o mesmo arquivo.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from .paths import ROOT
from .util import FabError, rel

SKILL = ROOT / ".agents" / "snes-mods-coala-agent-skill"
ENGINE = SKILL / "scripts" / "coala.py"
DB = SKILL / "memory" / "coala.sqlite"
DUMP = SKILL / "memory" / "coala.canonical.jsonl"
SYNC = ("sync", "--config", SKILL / "ingest.json", "--root", ROOT)
_SYNC_ROW = re.compile(r"^\s*(?:TOTAL|\(código\)).*?novos=\s*(\d+).*?atualizados=\s*(\d+).*?expirados=\s*(\d+)")


def _coala(*args, db: Path = DB) -> subprocess.CompletedProcess:
    """Motor CoALA da skill local, sempre sobre `db` (COALA_DB vence a base que o motor acharia sozinho)."""
    env = {**os.environ, "COALA_DB": str(db), "PYTHONUTF8": "1"}
    return subprocess.run([sys.executable, str(ENGINE), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=str(ROOT), env=env)


def _last_line(p: subprocess.CompletedProcess) -> str:
    lines = (p.stdout or p.stderr or "").strip().splitlines()
    return lines[-1] if lines else f"exit {p.returncode}"


def _run(*args, db: Path) -> str:
    p = _coala(*args, db=db)
    if p.returncode != 0:
        raise FabError(f"coala {args[0]} falhou: {_last_line(p)}", "veja a saída do motor CoALA (`coala.py doctor`)")
    return f"coala {args[0]}: {_last_line(p).strip()}"


def _same(a: bytes, b: bytes) -> bool:
    # um checkout com CRLF (git sem a regra `*.jsonl eol=lf`) é o mesmo dump
    return a.replace(b"\r\n", b"\n") == b.replace(b"\r\n", b"\n")


def pending_sync(db: Path = DB) -> int | None:
    """Registos que um `sync` criaria/atualizaria/expiraria (docs + código mudaram desde o último); None = ilegível."""
    p = _coala(*SYNC, "--dry-run", db=db)
    rows = [m.groups() for m in map(_SYNC_ROW.match, (p.stdout or "").splitlines()) if m]
    if p.returncode != 0 or not rows:
        return None
    return sum(int(n) for row in rows for n in row)


def dump_state(*, db: Path = DB, dump: Path = DUMP, check_sync: bool = True) -> tuple[str, str]:
    """('ok' | 'stale' | 'absent' | 'error', detalhe): o dump versionado bate com a base local?"""
    if not ENGINE.exists():
        return "error", f"motor ausente: {rel(ENGINE)}"
    if not db.exists():
        return "absent", "base local ausente — rode `fab memory restore`"
    if not dump.exists():
        return "stale", "dump ausente — rode `fab memory dump`"
    with tempfile.TemporaryDirectory() as d:
        fresh = Path(d) / "coala.jsonl"
        p = _coala("export", "--format", "jsonl", "--out", fresh, db=db)
        if p.returncode != 0:
            return "error", _last_line(p)
        if not _same(fresh.read_bytes(), dump.read_bytes()):
            return "stale", "dump desatualizado — rode `fab memory dump` antes de commitar"
    if check_sync and pending_sync(db):
        return "stale", "docs/código mudaram desde o último sync — `fab memory dump` sincroniza e exporta"
    return "ok", rel(dump)


def dump(*, db: Path = DB, out: Path = DUMP, sync: bool = True) -> list[str]:
    """Sincroniza docs e código e exporta a base local para o dump versionado."""
    if not db.exists():
        raise FabError(f"base local ausente: {rel(db)}", "num clone novo rode `fab memory restore` primeiro")
    done = [_run(*SYNC, db=db)] if sync else []
    done.append(_run("export", "--format", "jsonl", "--out", out, db=db))
    out.write_bytes(out.read_bytes().replace(b"\r\n", b"\n"))      # o motor escreve CRLF no Windows; o git guarda LF
    return done


def _max_id(db: Path) -> int:
    con = sqlite3.connect(db)
    try:
        return con.execute("SELECT COALESCE(MAX(id), 0) FROM memory_entries").fetchone()[0]
    finally:
        con.close()


def _keep_provenance(db: Path, src: Path, *, after: int) -> int:
    """O import anota em cada registo `Importado de <arquivo> (linha N) em <data>` e refaz as supersessões com outra
    nota: devolve aos registos que ELE criou (id > `after`) a proveniência exata do dump — senão o próximo dump
    levaria o caminho local para o git e reescreveria todos os registos. Tabela `provenance(entry_id, note)` do
    esquema v4 (references/schema.md)."""
    rows = []
    for line in src.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r.get("cid"):
                rows.append((r.get("provenance") or "", r["cid"]))
    con = sqlite3.connect(db)
    try:
        with con:
            cur = con.executemany("UPDATE provenance SET note = ? WHERE entry_id IN "
                                  "(SELECT id FROM memory_entries WHERE content_id = ? AND id > ?)",
                                  [(note, cid, after) for note, cid in rows])
        return cur.rowcount
    finally:
        con.close()


def restore(*, force: bool = False, sync: bool = True, db: Path = DB, src: Path = DUMP) -> list[str]:
    """Clone novo: cria a base, importa o dump (histórico e supersessões preservados) e sincroniza docs/código."""
    if db.exists() and not force:
        raise FabError(f"a base já existe ({rel(db)})", "use --force para importar o dump por cima (é idempotente)")
    if not src.exists():
        raise FabError(f"dump ausente: {rel(src)}", "rode `fab memory dump` numa máquina que tenha a base")
    done = [_run("init", db=db)]
    before = _max_id(db)
    done.append(_run("import", "--jsonl", src, db=db))
    done.append(f"proveniência do dump preservada em {_keep_provenance(db, src, after=before)} registo(s) importado(s)")
    if sync:
        done.append(_run(*SYNC, db=db))
    return done
