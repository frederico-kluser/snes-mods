"""Macros de input (comando SNES, porta 1) num formato de texto simples.

Uma linha = duração em frames + botões mantidos pressionados durante essa duração:

    # comentário (também ';')
    30              ← 30 frames sem botões (igual a "30 -")
    1   B           ← 1 frame com B
    12  Right+B     ← 12 frames com Direita e B
    2x  1 A / 5 -   ← repete o grupo "1 A" seguido de "5 -" duas vezes

Botões: A B X Y L R Start Select Up Down Left Right (maiúsculas/minúsculas indiferentes).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .util import FabError

# Bits na ordem do registrador JOY1 ($4218/$4219): B Y Select Start Up Down Left Right A X L R
BUTTON_BITS = {
    "b": 0x8000, "y": 0x4000, "select": 0x2000, "start": 0x1000,
    "up": 0x0800, "down": 0x0400, "left": 0x0200, "right": 0x0100,
    "a": 0x0080, "x": 0x0040, "l": 0x0020, "r": 0x0010,
}
ALIASES = {"sel": "select", "st": "start", "u": "up", "d": "down", "lt": "left", "rt": "right"}
LUA_NAMES = ["a", "b", "x", "y", "l", "r", "up", "down", "left", "right", "start", "select"]

# Macros vêm de mods de terceiros: limites contra "99999999x 1 B" (memória) e "2x 2x 2x … 1 B" (aninhamento)
MAX_STEPS = 100_000        # passos depois de expandir as repetições
MAX_FRAMES = 1_000_000     # frames num passo (~4,6 h a 60 fps)
MAX_NESTING = 8            # níveis de "Nx" dentro de "Nx"


def mask_of(spec: str) -> int:
    spec = spec.strip()
    if spec in ("", "-", "none", "nada"):
        return 0
    mask = 0
    for tok in re.split(r"[+,\s]+", spec):
        if not tok:
            continue
        key = ALIASES.get(tok.lower(), tok.lower())
        if key not in BUTTON_BITS:
            raise FabError(f"botão desconhecido no macro: {tok!r}", f"use um de: {', '.join(sorted(BUTTON_BITS))}")
        mask |= BUTTON_BITS[key]
    return mask


def names_of(mask: int) -> list[str]:
    return [n for n, b in BUTTON_BITS.items() if mask & b]


def _too_long() -> FabError:
    return FabError(f"macro grande demais (mais de {MAX_STEPS} passos)",
                    "use menos repetições ou passos mais longos (ex.: '600 B' em vez de '600x 1 B')")


def _count(digits: str, limit: int, what: str, lineno: int) -> int:
    # int() recusa mais de 4300 dígitos com ValueError; aqui vira o erro de limite
    n = int(digits) if len(digits.lstrip("0")) <= 18 else limit + 1
    if n > limit:
        raise FabError(f"linha {lineno} do macro: {what} acima do limite ({limit})", "divida o macro em partes")
    return n


def _parse_steps(text: str, depth: int = 0) -> list[tuple[int, int]]:
    if depth > MAX_NESTING:
        raise FabError("repetições aninhadas demais no macro", f"no máximo {MAX_NESTING} níveis de 'Nx'")
    steps: list[tuple[int, int]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        line = re.split(r"[#;]", line, maxsplit=1)[0].strip()
        if not line:
            continue
        m = re.fullmatch(r"(\d+)x\s+(.+)", line)
        if m:
            reps = _count(m.group(1), MAX_STEPS, "repetições", lineno)
            group = [g.strip() for g in m.group(2).split("/")]
            sub = _parse_steps("\n".join(group), depth + 1)
            if len(steps) + len(sub) * reps > MAX_STEPS:
                raise _too_long()
            steps.extend(sub * reps)
            continue
        m = re.fullmatch(r"(\d+)\s*(.*)", line)
        if not m:
            raise FabError(f"linha {lineno} do macro inválida: {line!r}", "formato: <frames> [Botão+Botão]")
        steps.append((_count(m.group(1), MAX_FRAMES, "frames", lineno), mask_of(m.group(2))))
        if len(steps) > MAX_STEPS:
            raise _too_long()
    return steps


def _list_step(item) -> tuple[int, int]:
    if not isinstance(item, (list, tuple)) or not 1 <= len(item) <= 2:
        raise FabError(f"passo do macro inválido: {repr(item)[:60]}", 'use [frames, "B+Right"] ou [frames, máscara]')
    n, b = item[0], item[1] if len(item) > 1 else 0
    try:
        n = int(n)
    except (TypeError, ValueError, OverflowError):
        raise FabError(f"frames inválidos no macro: {repr(item)[:60]}", "frames é um inteiro ≥ 0") from None
    if not 0 <= n <= MAX_FRAMES:
        raise FabError(f"frames fora do limite no macro: {n}", f"use de 0 a {MAX_FRAMES}")
    if isinstance(b, int) and not isinstance(b, bool):
        if not 0 <= b <= 0xFFFF:
            raise FabError(f"máscara de botões fora de 16 bits no macro: {b}", "use os nomes, ex.: \"B+Right\"")
        return n, b
    return n, mask_of(str(b))


def parse_macro(source: str | list | Path | None) -> list[tuple[int, int]]:
    """Aceita texto, caminho para .txt/.json, ou lista [[frames, "B+Right"|mask], ...]."""
    if source is None:
        return []
    if isinstance(source, Path) or (isinstance(source, str) and ("\n" not in source) and source.endswith((".txt", ".json", ".macro"))):
        p = Path(source)
        if not p.is_file():
            raise FabError(f"macro não encontrado: {p}")
        if p.suffix == ".json":
            return parse_macro(json.loads(p.read_text(encoding="utf-8")))
        return _parse_steps(p.read_text(encoding="utf-8"))
    if isinstance(source, list):
        if len(source) > MAX_STEPS:
            raise _too_long()
        return [_list_step(item) for item in source]
    text = str(source)
    if "\n" not in text:
        # forma de linha de comando: "20;1 B;18;1 B;100" (';' ou '|' separam linhas)
        text = text.replace(";", "\n").replace("|", "\n")
    return _parse_steps(text)


def total_frames(steps: list[tuple[int, int]]) -> int:
    return sum(n for n, _ in steps)


def mask_at(steps: list[tuple[int, int]], frame: int) -> int:
    acc = 0
    for n, mask in steps:
        if frame < acc + n:
            return mask
        acc += n
    return 0


def to_text(steps: list[tuple[int, int]]) -> str:
    return "\n".join(f"{n} {'+'.join(x.capitalize() for x in names_of(m)) or '-'}" for n, m in steps) + "\n"
