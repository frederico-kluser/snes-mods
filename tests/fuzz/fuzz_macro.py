"""Fuzzing dos macros de controle (snesfab/macro.py): texto `<frames> [Botão+Botão]`, forma de linha de comando
com `;` e a lista JSON do mod.json ([[frames, "B+Right"], ...]) — mods de terceiros trazem os seus.

Contrato: parse_macro() devolve passos (frames ≥ 0, máscara de 16 bits) ou levanta FabError; o texto
de to_text() é relido igual; nada trava nem estoura a memória.
"""

import json

import fuzzlib

with fuzzlib.instrumented():
    from snesfab import macro
    from snesfab.util import FabError


def _check(steps) -> None:
    assert all(isinstance(n, int) and n >= 0 and 0 <= m <= 0xFFFF for n, m in steps)
    macro.mask_at(steps, macro.total_frames(steps) // 2)


def TestOneInput(data: bytes) -> None:
    text = data.decode("utf-8", "replace")
    if "\n" not in text and text.endswith((".txt", ".json", ".macro")):
        return  # vira caminho de arquivo: fora do escopo do fuzzing
    try:
        steps = macro.parse_macro(text)
    except FabError:
        steps = None
    if steps is not None:
        _check(steps)
        assert macro.parse_macro(macro.to_text(steps)) == steps
    try:
        obj = json.loads(text)
    except (ValueError, RecursionError):
        return
    if isinstance(obj, list):
        try:
            _check(macro.parse_macro(obj))
        except FabError:
            pass


if __name__ == "__main__":
    fuzzlib.main(TestOneInput)
