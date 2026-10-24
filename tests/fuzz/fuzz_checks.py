"""Fuzzing dos critérios de aceitação (snesfab/checks.py): as expressões vêm do mod.json, que pode ser de terceiros.

Contrato: evaluate_checks() sempre devolve um resultado serializável em JSON (o ciclo grava no ledger), com
`passed` booleano; expressão ruim vira `error`, nunca exceção, travamento ou estouro de memória.
"""

import json
import warnings

import numpy as np

import fuzzlib

with fuzzlib.instrumented():
    from snesfab.checks import evaluate_checks, score

N = 48
_rng = np.random.default_rng(7)
MOD = {
    "frame": list(range(N)),
    "input": [int(v) for v in _rng.choice([0, 0x8000, 0x0100, 0x8100, 0x0080], N)],
    "x": [int(v) for v in np.cumsum(_rng.integers(0, 3, N)) + 0x40],
    "y": [int(v) for v in 0x150 - np.abs(np.arange(N) - N // 2) * 8],
    "vy": [int(v) for v in _rng.integers(-80, 64, N)],
    "air": [int(v) for v in _rng.integers(0, 2, N)],
}
BASE = {k: list(v) for k, v in MOD.items()}
BASE["y"] = [v + 16 for v in MOD["y"]]

warnings.simplefilter("ignore")
np.seterr(all="ignore")


def TestOneInput(data: bytes) -> None:
    expr = data.decode("utf-8", "replace")
    res = evaluate_checks([{"id": "fuzz", "expr": expr}], MOD, BASE)
    assert len(res) == 1 and isinstance(res[0]["passed"], bool)
    json.dumps(res, ensure_ascii=False)
    score(res)


if __name__ == "__main__":
    fuzzlib.main(TestOneInput)
