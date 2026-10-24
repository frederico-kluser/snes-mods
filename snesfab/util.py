"""Utilitários partilhados: erros com solução, subprocessos, hashes, JSON."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_MISSING = 3


class FabError(Exception):
    """Erro operacional com sugestão de solução (impresso como `Erro: … — Solução: …`)."""

    def __init__(self, what: str, fix: str = "", code: int = EXIT_FAIL):
        super().__init__(what)
        self.what = what
        self.fix = fix
        self.code = code

    def render(self) -> str:
        return f"Erro: {self.what}" + (f" — Solução: {self.fix}" if self.fix else "")


def info(msg: str) -> None:
    print(msg, flush=True)


def warn(msg: str) -> None:
    print(f"aviso: {msg}", file=sys.stderr, flush=True)


def now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    return text.strip("-") or "x"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def run(cmd: Sequence[str | os.PathLike], *, cwd: Path | None = None, env: dict | None = None,
        timeout: float | None = None, capture: bool = True, check: bool = False,
        input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    """Executa um comando (sem shell). Devolve CompletedProcess com stdout/stderr em texto."""
    full_env = os.environ.copy()
    if env:
        full_env.update({k: str(v) for k, v in env.items()})
    try:
        proc = subprocess.run(
            [str(c) for c in cmd], cwd=str(cwd) if cwd else None, env=full_env,
            timeout=timeout, input=input_bytes,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
        )
    except FileNotFoundError as e:
        raise FabError(f"executável não encontrado: {cmd[0]}", "rode `fab setup` e depois `fab doctor`", 3) from e
    except subprocess.TimeoutExpired as e:
        raise FabError(f"tempo esgotado ({timeout}s) rodando {Path(str(cmd[0])).name}",
                       "aumenta o timeout ou reduz o trabalho (frames/análise)") from e
    if capture:
        proc.stdout = (proc.stdout or b"").decode("utf-8", "replace")
        proc.stderr = (proc.stderr or b"").decode("utf-8", "replace")
    if check and proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-2000:] if capture else ""
        raise FabError(f"{Path(str(cmd[0])).name} terminou com código {proc.returncode}: {tail.strip()}",
                       "veja a saída acima")
    return proc


def rel(path: Path, root: Path | None = None) -> str:
    """Caminho relativo à raiz do projeto (para mensagens curtas)."""
    from .paths import ROOT
    base = root or ROOT
    try:
        return str(Path(path).resolve().relative_to(base)).replace("\\", "/")
    except ValueError:
        return str(path)


def chunks(seq: Sequence, n: int) -> Iterable[Sequence]:
    for i in range(0, len(seq), n):
        yield seq[i:i + n]
