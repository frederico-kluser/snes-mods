"""Registos de evidência no espírito do contrato `Evidence` do REA (v6.2+):
cada consulta devolve `evidence_id`, `analysis_profile`, `normalized_result` e `limitations`,
e fica num livro-razão por jogo (work/evidence/<jogo>.jsonl) para ser citada nas conclusões.

Disciplina: observações (bytes, instruções, xrefs, hits de sondas) ≠ inferências (o que um
endereço significa) ≠ incógnitas residuais (M/X ambíguo, ponteiros indiretos, DP/DB não resolvidos).
"""

from __future__ import annotations

import hashlib
import json

from .paths import WORK
from .util import append_jsonl, now_iso, read_jsonl


def _digest(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def record(game: str, kind: str, query: dict, profile: dict, result, limitations: list[str]) -> dict:
    eid = "ev-" + _digest({"k": kind, "q": query, "p": profile})[:12]
    rec = {
        "evidence_id": eid,
        "kind": kind,
        "time": now_iso(),
        "query": query,
        "analysis_profile": profile,
        "normalized_result": result,
        "limitations": limitations,
    }
    append_jsonl(WORK / "evidence" / f"{game}.jsonl", rec)
    return rec


def ledger(game: str) -> list[dict]:
    return read_jsonl(WORK / "evidence" / f"{game}.jsonl")


def find(game: str, evidence_id: str) -> dict | None:
    for rec in reversed(ledger(game)):
        if rec["evidence_id"] == evidence_id:
            return rec
    return None


STATIC_LIMITS = [
    "Análise estática: a largura dos imediatos depende das flags M/X em runtime; o contexto vem das sementes (CDL/vetores) e de SEP/REP no fluxo — confirme com `fab probe exec`.",
    "Endereços direct page/absolutos são resolvidos com D=$0000 e DB assumido; acessos via D≠0 ou DB≠banco atual podem apontar para o espelho errado.",
    "Saltos indiretos/tabelas de ponteiros só são seguidos se semeados (CDL) — código não executado nas runs de CDL pode faltar.",
]

DYNAMIC_LIMITS = [
    "Evidência dinâmica: cobre só o que o cenário (state + macro + frames) executou.",
    "Em sondas de escrita/leitura o PC reportado é o da instrução SEGUINTE; a instrução escritora é reconstruída por desmontagem para trás (candidatos listados).",
]
