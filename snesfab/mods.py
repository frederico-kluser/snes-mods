"""Mods: mods/<id>/mod.json (+ patch.asm, macros). Criação a partir do modelo e validação."""

from __future__ import annotations

import json
from pathlib import Path

from .paths import MODS
from .util import FabError, read_json, slugify, write_json

REQUIRED = ("id", "game", "goal", "patches", "scenarios")

PATCH_TEMPLATE = """; ════════════════════════════════════════════════════════════════════════════
;  {title}
;  Jogo: {game} · Objetivo: {goal}
;  Montado por `fab build mods/{mid}` sobre uma CÓPIA da base limpa (nunca a original).
; ════════════════════════════════════════════════════════════════════════════
{mapping}

; ── Definições COM evidência (endereço · como foi verificado) ───────────────
; !Exemplo = $7E0000     ; ex.: sonda de escrita `fab probe writes {game} 7E:0000` em <run>

; ── Hijack: substitui instruções inteiras que somem ≥ 4 bytes (JML/JSL = 4) ─
; Antes de escrever: `fab disasm {game} <addr> --flags <m>,<x>` e confirme M/X com
; `fab probe exec {game} <addr>` (o campo ps mostra M=bit5, X=bit4 em CADA execução).
; org $XXXXXX
;     autoclean jml MinhaRotina    ; + nop se as instruções substituídas somarem 5+ bytes

; ── Patch SÓ de dados (paletas, tabelas…): declare cada região em mod.json → "data" ─
;   [{{"addr": "BB:AAAA", "length": N, "evidence": "endereço · como foi verificado"}}]
;   → o build classifica a mudança como `kind: "data"` (fora de build["hijacks"], sem sondas
;   exec no ciclo); o que NÃO for declarado continua sendo tratado como hijack.

; freecode                         ; bancos $10-$3F (precisa de ROM ≥ 1 MB: "expand_to" no mod.json)
; MinhaRotina:
;     ; reproduz aqui as instruções originais sobrescritas
;     jml $XXXXXX                  ; volta para uma fronteira de instrução
"""

MACRO_TEMPLATE = """# macro de input (porta 1) — <frames> [Botão+Botão]
# Botões: A B X Y L R Start Select Up Down Left Right
30
1 B
60
"""


def mod_dir_of(ref: str | Path) -> Path:
    p = Path(ref)
    if (p / "mod.json").exists():
        return p.resolve()
    cand = MODS / str(ref)
    if (cand / "mod.json").exists():
        return cand.resolve()
    raise FabError(f"mod não encontrado: {ref}", "use mods/<id> ou crie com `fab mod new <id> --game <jogo>`")


def load_mod(ref: str | Path) -> dict:
    d = mod_dir_of(ref)
    try:
        mod = read_json(d / "mod.json")
    except json.JSONDecodeError as e:
        raise FabError(f"mod.json inválido em {d}: {e}") from e
    missing = [k for k in REQUIRED if k not in mod]
    if missing:
        raise FabError(f"mod.json sem campos obrigatórios: {', '.join(missing)}", "veja o exemplo mods/testbed-double-jump/mod.json")
    ids = [s.get("id") for s in mod["scenarios"]]
    if len(set(ids)) != len(ids) or any(not i for i in ids):
        raise FabError("cada cenário precisa de um 'id' único")
    mod["_dir"] = str(d)
    return mod


def new_mod(mid: str, game: str, title: str = "", goal: str = "", mapping: str = "lorom") -> Path:
    from .game import load_game
    g = load_game(game)
    mid = slugify(mid)
    d = MODS / mid
    if d.exists():
        raise FabError(f"o mod {mid} já existe", "escolha outro id")
    d.mkdir(parents=True)
    mapping_directive = {"lorom": "lorom", "hirom": "hirom", "exhirom": "exhirom", "sa1": "sa1rom", "sdd1": "lorom"}.get(g["mapping"], "lorom")
    write_json(d / "mod.json", {
        "id": mid,
        "title": title or mid,
        "game": game,
        "goal": goal or "descreve o objetivo observável (o que se deve VER e medir)",
        "patches": ["patch.asm"],
        "expand_to": None,
        "hijacks": [],
        "data": [],
        "max_cycles": 8,
        "scenarios": [{
            "id": "principal",
            "state": "<nome-do-state>",
            "input": "principal.txt",
            "frames": 180,
            "capture": {"every": 2},
            "watch": [],
            "checks": [],
        }],
    })
    (d / "patch.asm").write_text(PATCH_TEMPLATE.format(title=title or mid, game=game, goal=goal or "?", mid=mid,
                                                       mapping=mapping_directive), encoding="utf-8", newline="\n")
    (d / "principal.txt").write_text(MACRO_TEMPLATE, encoding="utf-8", newline="\n")
    (d / "README.md").write_text(f"# {title or mid}\n\nJogo: `{game}` ({g['title']})\n\nObjetivo: {goal or '?'}\n\n"
                                 "## Estado\n- [ ] evidências recolhidas\n- [ ] patch monta sem avisos\n"
                                 "- [ ] ciclo com todos os checks a passar\n- [ ] verificação visual\n",
                                 encoding="utf-8", newline="\n")
    return d


def list_mods() -> list[dict]:
    out = []
    if not MODS.exists():
        return out
    for d in sorted(MODS.iterdir()):
        if (d / "mod.json").exists() and not d.name.startswith("_"):
            m = read_json(d / "mod.json")
            out.append({"id": m["id"], "game": m["game"], "title": m.get("title", ""), "scenarios": len(m["scenarios"])})
    return out
