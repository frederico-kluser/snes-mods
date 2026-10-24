"""Workspace por jogo: registro da ROM (original + base limpa, só leitura), game.json, notes.md e savestates."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

from .paths import GAMES, ROMS, ROOT, toolchain
from .rom import load_rom
from .util import FabError, now_iso, read_json, rel, slugify, write_json

NOTES_TEMPLATE = """# {title} (`{gid}`)

> Notas duráveis sobre este jogo. Cada fato leva a evidência (como foi verificado: sonda
> dinâmica, xref do Ghidra, teste no emulador). Nada de dumps de código comercial aqui.

## Identificação
- Mapa: {mapping} · ROM: {size_kb} KiB · região: {region}
- SHA-256 (base limpa): `{sha}`
- Cabeçalho SMC no original: {smc}

## Mapa de RAM (verificado)
| endereço | tam. | significado | evidência |
|---|---|---|---|

## Rotinas
| endereço | o que faz | M/X à entrada | evidência |
|---|---|---|---|

## Savestates (`games/{gid}/states/`)
| nome | o que mostra | criado como |
|---|---|---|

## Hijacks usados por mods
| endereço | bytes originais | mod | notas |
|---|---|---|---|

## Perguntas em aberto
-
"""


def _make_readonly(p: Path) -> None:
    try:
        os.chmod(p, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    except OSError:
        pass


def game_dir(gid: str) -> Path:
    return GAMES / gid


def load_game(gid: str) -> dict:
    p = GAMES / gid / "game.json"
    if not p.exists():
        known = ", ".join(sorted(d.name for d in GAMES.iterdir() if (d / "game.json").exists())) if GAMES.exists() else ""
        raise FabError(f"jogo '{gid}' não registrado" + (f" (registrados: {known})" if known else ""),
                       "registre com `fab rom add <caminho-da-rom> --id <id>`")
    g = read_json(p)
    g["_dir"] = str(GAMES / gid)
    return g


def clean_rom(gid: str) -> Path:
    g = load_game(gid)
    p = ROOT / g["rom"]["clean"]
    if not p.exists():
        raise FabError(f"base limpa de '{gid}' ausente: {p}", f"registre de novo: `fab rom add <rom> --id {gid} --force`")
    return p


def list_games() -> list[dict]:
    if not GAMES.exists():
        return []
    out = []
    for d in sorted(GAMES.iterdir()):
        if (d / "game.json").exists():
            g = read_json(d / "game.json")
            out.append({"id": g["id"], "title": g["title"], "mapping": g["mapping"],
                        "states": len(list((d / "states").glob("*.mss"))) if (d / "states").exists() else 0})
    return out


def add_rom(src: Path, gid: str | None = None, force: bool = False, note: str = "") -> dict:
    src = Path(src).resolve()
    img = load_rom(src)
    gid = slugify(gid or img.header.title or src.stem)
    hashes = img.hashes()
    gdir = GAMES / gid
    if (gdir / "game.json").exists() and not force:
        old = read_json(gdir / "game.json")
        if old["hashes"]["clean_sha256"] == hashes["clean_sha256"]:
            return old | {"_status": "já registrado (mesma ROM)"}
        raise FabError(f"o id '{gid}' já está registrado com outra ROM (sha256 {old['hashes']['clean_sha256'][:12]}…)",
                       "use outro --id ou --force para substituir")
    rdir = ROMS / gid
    rdir.mkdir(parents=True, exist_ok=True)
    orig_dest = rdir / f"original{src.suffix.lower()}"
    clean_dest = rdir / f"{gid}.sfc"
    for p in (orig_dest, clean_dest):
        if p.exists():
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
    if src != orig_dest:
        shutil.copyfile(src, orig_dest)
    clean_dest.write_bytes(img.data)
    _make_readonly(orig_dest)
    _make_readonly(clean_dest)
    (gdir / "states").mkdir(parents=True, exist_ok=True)
    hdr = img.header.describe()
    meta = {
        "id": gid,
        "title": img.header.title,
        "added": now_iso(),
        "source_path": str(src),
        "note": note,
        "rom": {"original": rel(orig_dest), "clean": rel(clean_dest)},
        "smc_header": img.had_smc_header,
        "size": len(img.data),
        "mapping": img.mapping,
        "header": hdr,
        "checksum": img.checksum_info(),
        "hashes": hashes,
        "detection": img.candidates,
    }
    write_json(gdir / "game.json", meta)
    notes = gdir / "notes.md"
    if not notes.exists():
        notes.write_text(NOTES_TEMPLATE.format(
            title=img.header.title, gid=gid, mapping=img.mapping, size_kb=len(img.data) // 1024,
            region=hdr["region"], sha=hashes["clean_sha256"], smc="sim (removido na base limpa)" if img.had_smc_header else "não",
        ), encoding="utf-8", newline="\n")
    return meta


# ── savestates ────────────────────────────────────────────────────────────────

def states_dir(gid: str) -> Path:
    d = GAMES / gid / "states"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_states(gid: str) -> list[dict]:
    d = states_dir(gid)
    out = []
    for p in sorted(d.glob("*.mss")):
        side = p.with_suffix(".json")
        info = read_json(side) if side.exists() else {}
        out.append({"name": p.stem, "path": rel(p), "size": p.stat().st_size, **{k: v for k, v in info.items() if k != "name"}})
    return out


def state_path(gid: str, name_or_path: str) -> Path:
    p = Path(name_or_path)
    if p.suffix == ".mss" and p.exists():
        return p.resolve()
    cand = states_dir(gid) / f"{name_or_path}.mss"
    if cand.exists():
        return cand
    raise FabError(f"savestate '{name_or_path}' não existe para '{gid}'",
                   f"veja `fab state list {gid}`; crie com `fab state boot` ou `fab state import`")


def mesen_slot_path(gid: str, slot: int) -> Path:
    tc = toolchain()
    return tc.mesen_dir / "SaveStates" / f"{gid}_{slot}.mss"


def import_state(gid: str, name: str, source: str | None = None, slot: int | None = None, note: str = "") -> dict:
    """Importa um .mss (caminho) ou um slot do Mesen (gravado com Shift+F<slot> no `fab play`)."""
    load_game(gid)
    if source:
        src = Path(source)
    elif slot is not None:
        src = mesen_slot_path(gid, slot)
    else:
        raise FabError("indique --file <state.mss> ou --slot <n>")
    if not src.exists():
        raise FabError(f"savestate não encontrado: {src}",
                       f"no `fab play {gid}` salve com Shift+F{slot or 1} (slot {slot or 1}) e repita")
    dest = states_dir(gid) / f"{slugify(name)}.mss"
    shutil.copyfile(src, dest)
    write_json(dest.with_suffix(".json"), {"created": now_iso(), "how": f"import de {src.name}", "note": note})
    return {"name": dest.stem, "path": rel(dest)}


def play(gid: str, rom: Path | None = None) -> dict:
    """Abre o MesenCE (GUI) com a ROM do jogo (ou uma ROM montada) para o usuário jogar/gravar states."""
    tc = toolchain()
    tc.require("mesen")
    from .emu import ensure_mesen_settings
    ensure_mesen_settings()
    # o Mesen nomeia os slots pelo nome do arquivo da ROM: <id>_<slot>.mss
    target = Path(rom) if rom else clean_rom(gid)
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    subprocess.Popen([str(tc.mesen), str(target)], cwd=str(tc.mesen_dir), creationflags=flags,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"rom": rel(target), "slots_dir": rel(tc.mesen_dir / "SaveStates"),
            "hint": f"Shift+F1..F10 grava o slot; depois `fab state import {gid} <nome> --slot <n>`"}
