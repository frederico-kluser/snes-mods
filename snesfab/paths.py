"""Layout do projeto e localização do toolchain pinado em tools/manifest.json."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path

from .util import FabError, read_json

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
DOWNLOADS = TOOLS / "_downloads"
MANIFEST = TOOLS / "manifest.json"

ROMS = ROOT / "roms"            # originais + bases limpas (ignorado pelo git)
GAMES = ROOT / "games"          # um workspace por jogo: game.json, notes.md, states/
MODS = ROOT / "mods"            # um diretório por mod: mod.json, patch.asm, macros
BUILD = ROOT / "build"          # ROMs montadas pelo Asar (ignorado)
RUNS = ROOT / "runs"            # saídas de emulação/mídia (ignorado)
WORK = ROOT / "work"            # projetos Ghidra, exports, evidências (ignorado)
CYCLES = ROOT / "cycles"        # ledger e relatórios dos ciclos de evolução
MEDIA_INBOX = ROOT / "media" / "inbox"
LUA = ROOT / "lua"
GHIDRA_SCRIPTS = ROOT / "ghidra_scripts"
FIXTURES = ROOT / "fixtures"


def platform_key() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = "x64" if machine in ("amd64", "x86_64") else machine
    return f"{system}-{arch}"


def manifest() -> dict:
    if not MANIFEST.exists():
        raise FabError(f"manifesto do toolchain ausente: {MANIFEST}", "restaura tools/manifest.json do git")
    return read_json(MANIFEST)


def platform_tools() -> dict:
    key = platform_key()
    plats = manifest().get("platforms", {})
    if key not in plats:
        raise FabError(f"plataforma {key} sem toolchain no manifesto (há: {', '.join(plats)})",
                       "acrescente uma seção para esta plataforma em tools/manifest.json", 3)
    return plats[key]


@dataclass
class Toolchain:
    java_home: Path
    java: Path
    ghidra_dir: Path
    analyze_headless: Path
    sleigh: Path
    mesen_dir: Path
    mesen: Path
    asar: Path
    ffmpeg: Path
    ffprobe: Path

    def missing(self) -> list[str]:
        out = []
        for name in ("java", "analyze_headless", "mesen", "asar", "ffmpeg", "ffprobe"):
            if not getattr(self, name).exists():
                out.append(name)
        return out

    def require(self, *names: str) -> None:
        missing = [n for n in names if not getattr(self, n).exists()]
        if missing:
            raise FabError(f"ferramenta(s) ausente(s): {', '.join(missing)}", "rode `fab setup`", 3)

    def java_env(self) -> dict:
        env = {"JAVA_HOME": str(self.java_home)}
        env["PATH"] = str(self.java_home / "bin") + os.pathsep + os.environ.get("PATH", "")
        return env


def toolchain() -> Toolchain:
    t = platform_tools()
    jdk = TOOLS / t["jdk"]["home"]
    ghidra = TOOLS / t["ghidra"]["home"]
    mesen_dir = TOOLS / t["mesen"]["home"]
    ffmpeg_home = TOOLS / t["ffmpeg"]["home"]
    win = platform.system() == "Windows"
    return Toolchain(
        java_home=jdk,
        java=jdk / t["jdk"]["exe"],
        ghidra_dir=ghidra,
        analyze_headless=ghidra / t["ghidra"]["exe"],
        sleigh=ghidra / "support" / ("sleigh.bat" if win else "sleigh"),
        mesen_dir=mesen_dir,
        mesen=mesen_dir / t["mesen"]["exe"],
        asar=TOOLS / t["asar"]["home"] / t["asar"]["exe"],
        ffmpeg=ffmpeg_home / t["ffmpeg"]["exe"],
        ffprobe=ffmpeg_home / t["ffmpeg"].get("probe", "bin/ffprobe"),
    )
