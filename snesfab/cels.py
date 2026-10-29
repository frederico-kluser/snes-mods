"""Motores de sprite por LISTA DE CELS (ex.: SFA2): cada pose é uma lista `[n][x, y, tile, flags]…` na ROM e o
motor gera um sprite do OAM por cel. Marcar um cel (um bit livre das flags) deixa um hook tratar SÓ aquele
pedaço da pose — é assim que a luva vai para a paleta-espelho sem levar o cabelo.

Configuração por jogo em `game.json → "sprite_engine"` (dados, não código):
    {"kind": "cel-list", "probe": "C0:5C8E", "pointer": "y", "bank": "dbr", "count_size": 1, "record": 4,
     "x": 0, "y": 1, "tile": 2, "flags": 3, "mark_bit": 2, "evidence": "…"}
- `probe`: endereço executado com o ponteiro da lista num registrador (achado com `fab probe exec`);
- o sprite do OAM liga-se ao cel pelo número do tile (8 bits) dentro da lista daquele frame.

As marcas saem dos RÓTULOS POR CONTEÚDO (`fab sprite label/census`): um cel só é marcado se, em TODOS os
frames em que apareceu, tinha píxeis da peça-alvo e nenhum de outra peça nem sem rótulo (qualidade primeiro).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .emu import Probe, read_probes
from .parts import PartStore, classify, target_mask
from .rom import asar_org, fmt_addr, parse_addr
from .util import FabError, rel


@dataclass
class CelEngine:
    probe: str
    pointer: str = "y"
    bank: str = "dbr"
    count_size: int = 1
    record: int = 4
    x: int = 0
    y: int = 1
    tile: int = 2
    flags: int = 3
    mark_bit: int = 2
    evidence: str = ""

    @classmethod
    def from_game(cls, game: dict) -> "CelEngine":
        cfg = game.get("sprite_engine")
        if not cfg or cfg.get("kind") != "cel-list":
            raise FabError(f"o jogo {game.get('id')} não tem 'sprite_engine' do tipo cel-list no game.json",
                           "descubra a rotina que lê a lista de cels (fab probe exec) e declare-a no game.json")
        keys = {k: cfg[k] for k in cls.__dataclass_fields__ if k in cfg}
        return cls(**keys)

    def probe_obj(self, max_hits: int = 4000) -> Probe:
        return Probe("exec", parse_addr(self.probe), max_hits=max_hits, label="cel-list")


@dataclass
class CelList:
    pc: int
    cels: list[tuple[int, int, int, int]] = field(default_factory=list)   # x, y, tile, flags


def lists_by_frame(cap_dir: Path, rom, engine: CelEngine) -> dict[int, list[CelList]]:
    """Listas de cels lidas pelo motor em cada frame (da sonda gravada na captura)."""
    hits = [h for h in read_probes(Path(cap_dir) / "run-real") if h.get("label") == "cel-list"]
    out: dict[int, dict[int, CelList]] = defaultdict(dict)
    for h in hits:
        ptr = h[engine.pointer] & 0xFFFF
        bank = h[engine.bank] & 0xFF
        try:
            pc = rom.to_pc((bank << 16) | ptr)
        except FabError:
            continue
        if pc in out[h["frame"]]:
            continue
        n = rom.data[pc] if engine.count_size == 1 else rom.data[pc] | (rom.data[pc + 1] << 8)
        if not 1 <= n <= 128:
            continue
        cels = []
        for i in range(n):
            o = pc + engine.count_size + engine.record * i
            rec = rom.data[o:o + engine.record]
            cels.append((rec[engine.x], rec[engine.y], rec[engine.tile], rec[engine.flags]))
        out[h["frame"]][pc] = CelList(pc, cels)
    return {f: list(v.values()) for f, v in out.items()}


def match_list(tiles: list[int], lists: list[CelList]) -> CelList | None:
    """A lista do frame cujo conjunto de tiles mais bate com os tiles (8 bits) dos sprites do objeto."""
    want = Counter(t & 0xFF for t in tiles)
    best, score = None, 0
    for cl in lists:
        have = Counter(c[2] for c in cl.cels)
        s = sum((want & have).values())
        if s > score:
            best, score = cl, s
    return best if best and score >= max(1, len(tiles) // 2) else None


def mark_votes(cap, store: PartStore, palette: int, indices: list[int], target: str, engine: CelEngine, rom) -> dict:
    """Para cada (lista, cel): quantas vezes o sprite dele teve só a peça-alvo, só outra peça, as duas, ou
    píxeis do índice sem rótulo."""
    by_frame = lists_by_frame(cap.dir, rom, engine)
    votes: dict[tuple[int, int], Counter] = defaultdict(Counter)
    frames_sem_lista = []
    for f in sorted(cap.frames):
        fd = cap.frames[f]
        lay = fd.layer()
        vis = fd.visible_obj() & (lay.palette == palette)
        ents = sorted({int(e) for e in np.unique(lay.oam[vis])})
        if not ents:
            continue
        cl = match_list([lay.entries[e].tile for e in ents], by_frame.get(f, []))
        if cl is None:
            frames_sem_lista.append(f)
            continue
        m = target_mask(fd, palette, indices)
        lab, parts = classify(fd, store, m)
        ti = parts.index(target) if target in parts else -1
        for e in ents:
            em = m & (lay.oam == e)
            n_t = n_o = n_u = 0
            if not em.any():
                kind = "sem_alvo"
            else:
                vals = lab[em]
                n_t = int((vals == ti).sum())
                n_o = int(((vals >= 0) & (vals != ti)).sum())
                n_u = int((vals < 0).sum())
                kind = "misturado" if n_t and n_o else "outra" if n_o else "sem_rotulo" if n_u else "alvo"
            t8 = lay.entries[e].tile & 0xFF
            for i, c in enumerate(cl.cels):
                if c[2] == t8:
                    v = votes[(cl.pc, i)]
                    v[kind] += 1
                    if kind == "misturado":
                        v["px_alvo_misturado"] += n_t
                        v["px_outra_misturado"] += n_o
                        v["max_outra_misturado"] = max(v["max_outra_misturado"], n_o)
    return {"votes": votes, "frames_sem_lista": frames_sem_lista, "listas": len({k[0] for k in votes})}


def decide(votes: dict, max_other_px: int = 0) -> tuple[list[tuple[int, int]], Counter]:
    """Marca o cel que teve a peça-alvo e nunca foi SÓ outra peça nem teve píxel sem rótulo. Cel MISTURADO (as
    duas peças no mesmo sprite) só entra se a outra peça ocupar no máximo `max_other_px` píxeis nele (padrão 0:
    nunca pinta a outra peça). O balanço do que fica de fora vai no relatório."""
    marked, why = [], Counter()
    for key, v in sorted(votes.items()):
        if v["alvo"] == 0 and v["misturado"] == 0:
            continue
        if v["outra"]:
            why["excluido_cel_que_e_outra_peca"] += 1
        elif v["sem_rotulo"]:
            why["excluido_por_pixel_sem_rotulo"] += 1
        elif v["misturado"] and v["max_outra_misturado"] > max_other_px:
            why["excluido_misturado"] += 1
            why["px_da_peca_que_ficam_sem_pintar"] += v["px_alvo_misturado"]
        else:
            if v["misturado"]:
                why["misturado_aceito"] += 1
                why["px_da_outra_peca_pintados"] += v["px_outra_misturado"]
            marked.append(key)
    return marked, why


def marks_asm(marked: list[tuple[int, int]], rom, engine: CelEngine, header: list[str]) -> tuple[str, dict]:
    """marks.asm (orgs do Asar gerados por PC) + a região data[] que cobre todas as marcas."""
    targets = {}
    for pc, i in marked:
        a = pc + engine.count_size + engine.record * i + engine.flags
        targets[a] = rom.data[a] | (1 << engine.mark_bit)
    if not targets:
        raise FabError("nenhum cel a marcar", "rotule mais regiões (fab sprite census → label) ou confira a peça-alvo")
    keys = sorted(targets)
    runs, cur = [], [keys[0]]
    for a in keys[1:]:
        if a == cur[-1] + 1:
            cur.append(a)
        else:
            runs.append(cur)
            cur = [a]
    runs.append(cur)
    lines = [*header, "", "lorom" if rom.mapping in ("lorom", "sdd1") else {"hirom": "hirom", "sa1": "sa1rom"}.get(rom.mapping, "lorom"), ""]
    for r in runs:
        lines.append(f"org ${asar_org(r[0], rom.mapping):06X}   ; PC 0x{r[0]:06X}")
        lines.append("    db " + ",".join(f"${targets[a]:02X}" for a in r))
    lo, hi = keys[0], keys[-1]
    region = {"pc": f"0x{lo:06X}", "length": hi - lo + 1, "source": "marks",
              "evidence": f"MARCAS de cel (bit {engine.mark_bit} das flags) geradas por `fab sprite marks` a partir de "
                          f"rótulos por conteúdo; {len(targets)} cels; motor {engine.probe} ({engine.evidence})"}
    return "\n".join(lines) + "\n", region


def report_lines(cap, votes: dict, marked, why, store: PartStore) -> list[str]:
    return [f"; captura: {rel(cap.dir)} ({len(cap.frames)} frames) · loja de rótulos: {rel(store.path)}",
            f"; cels com voto: {len(votes)} · marcados: {len(marked)} · "
            + " · ".join(f"{k}: {v}" for k, v in sorted(why.items())),
            f"; listas (poses) com marca: {len({k[0] for k in marked})}",
            "; regra: marca só o cel que mostrou a peça-alvo e NUNCA outra peça, mistura ou píxel sem rótulo"]


def fmt_list(pc: int, rom) -> str:
    try:
        return fmt_addr(rom.to_snes(pc))
    except FabError:
        return f"0x{pc:06X}"
