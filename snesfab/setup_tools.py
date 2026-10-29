"""`fab setup` (instala/configura o toolchain pinado, idempotente) e `fab doctor` (verifica tudo)."""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

from .paths import DOWNLOADS, ROOT, TOOLS, manifest, platform_tools, toolchain
from .util import FabError, info, read_json, rel, run, sha256_file, warn, write_json

ARCHIVE_TOOLS = ("jdk", "ghidra", "mesen", "asar", "ffmpeg")
REA_HOME = TOOLS / "rea"                                  # npm --prefix (fora do git)
REA_PKG = REA_HOME / "node_modules" / "rea-agents"


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    info(f"  baixando {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "snesfab-setup"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done, last = 0, -10
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                pct = done * 100 // total
                if pct >= last + 10:
                    info(f"    {pct}% ({done >> 20} MiB)")
                    last = pct
    os.replace(tmp, dest)


def install_archive(name: str, spec: dict, force: bool = False) -> str:
    home = TOOLS / spec["home"]
    exe = home / spec["exe"]
    if exe.exists() and not force:
        return "ok (já instalado)"
    archive = DOWNLOADS / spec["archive"]
    if not archive.exists() or sha256_file(archive) != spec["sha256"]:
        _download(spec["url"], archive)
    digest = sha256_file(archive)
    if digest != spec["sha256"]:
        raise FabError(f"sha256 de {archive.name} não confere ({digest[:16]}… ≠ {spec['sha256'][:16]}…)",
                       "apague o arquivo em tools/_downloads e repita; se persistir, a release mudou: atualize o manifesto")
    dest = TOOLS / spec.get("extract_to", ".")
    dest.mkdir(parents=True, exist_ok=True)
    info(f"  extraindo {archive.name} → {rel(dest)}")
    with zipfile.ZipFile(archive) as z:
        z.extractall(dest)
    if not exe.exists():
        raise FabError(f"{name}: depois de extrair não encontro {exe}", "o layout do arquivo mudou; corrija 'home'/'exe' no manifesto")
    return "instalado"


def install_ghidra_snes(force: bool = False) -> str:
    tc = toolchain()
    src_spec = manifest()["sources"]["ghidra_snes"]
    ext_dir = tc.ghidra_dir / "Ghidra" / "Extensions" / "ghidra-snes"
    marker = ext_dir / ".snesfab-commit"
    sla = ext_dir / "data" / "languages" / "65816.sla"
    if sla.exists() and marker.exists() and marker.read_text().strip() == src_spec["commit"] and not force:
        return "ok (já instalado)"
    src = TOOLS / src_spec["src"]
    if not (src / ".git").exists():
        src.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--quiet", src_spec["repo"], src], check=True, timeout=600)
    run(["git", "-C", src, "fetch", "--quiet", "--all"], timeout=600)
    run(["git", "-C", src, "checkout", "--quiet", "--force", src_spec["commit"]], check=True)
    props = src / "extension.properties"
    lines = [("version=@extversion@" if line.startswith("version=") else line) for line in props.read_text().splitlines()]
    props.write_text("\n".join(lines) + "\n")
    env = tc.java_env() | {"GHIDRA_INSTALL_DIR": str(tc.ghidra_dir)}
    gradlew = src / ("gradlew.bat" if platform.system() == "Windows" else "gradlew")
    info("  compilando ghidra-snes contra o Ghidra pinado (gradle)…")
    proc = run([gradlew, "-p", src, "--no-daemon", "clean", "buildExtension"], env=env, timeout=1800)
    if proc.returncode != 0:
        raise FabError(f"build do ghidra-snes falhou: {(proc.stdout + proc.stderr)[-1500:]}")
    zips = sorted((src / "dist").glob("*.zip"), key=lambda p: p.stat().st_mtime)
    if not zips:
        raise FabError("o gradle não produziu o zip da extensão")
    if ext_dir.exists():
        shutil.rmtree(ext_dir)
    with zipfile.ZipFile(zips[-1]) as z:
        z.extractall(ext_dir.parent)
    # Module.manifest do projeto tem linhas que o Ghidra 12 rejeita (só avisos, mas poluem o log)
    (ext_dir / "Module.manifest").write_text("MODULE NAME: Ghidra-SNES\n")
    proc = run([tc.sleigh, ext_dir / "data" / "languages" / "65816.slaspec"], env=tc.java_env(), timeout=600)
    if not sla.exists():
        raise FabError(f"compilação SLEIGH falhou: {(proc.stdout + proc.stderr)[-1500:]}")
    marker.write_text(src_spec["commit"] + "\n")
    return "instalado"


def install_rea(force: bool = False) -> str:
    """rea-agents fica em tools/rea (versão pinada no manifesto), como o resto do toolchain."""
    want = manifest().get("npm", {}).get("rea-agents")
    pkg = REA_PKG / "package.json"
    if pkg.exists() and read_json(pkg).get("version") == want and not force:
        status = "ok (já instalado)"
    else:
        npm = shutil.which("npm") or shutil.which("npm.cmd")
        if not npm:
            raise FabError("npm não encontrado", "instale Node.js ≥ 22.19 (fnm/nvm) e repita `fab setup`", 3)
        REA_HOME.mkdir(parents=True, exist_ok=True)
        proc = run([npm, "install", "--no-audit", "--no-fund", "--save-exact", "--prefix", REA_HOME,
                    f"rea-agents@{want}"], cwd=REA_HOME, timeout=900)
        if proc.returncode != 0:
            raise FabError(f"npm install falhou: {(proc.stdout + proc.stderr)[-1200:]}")
        status = "instalado"
    write_mcp_json()
    copy_rea_skill()
    return status


def _real_node() -> str:
    """Caminho estável do node: o fnm põe no PATH um diretório temporário por shell
    (fnm_multishells/…) que desaparece — resolve-se para a instalação real."""
    found = shutil.which("node")
    if not found:
        return "node"
    try:
        proc = run([found, "-e", "process.stdout.write(require('fs').realpathSync(process.execPath))"], timeout=30)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except FabError:
        pass
    return os.path.realpath(found)


def write_mcp_json() -> Path:
    """Registra o servidor MCP do REA SÓ neste projeto (.mcp.json, gerado com caminhos desta máquina)."""
    tc = toolchain()
    node = _real_node()
    cfg = {
        "mcpServers": {
            "rea": {
                "command": node,
                "args": [str(REA_PKG / "scripts" / "rea.mjs"), "mcp"],
                "env": {
                    "REA_ANALYSIS_PROVIDER": "ghidra",
                    "REA_MCP_INPUT_SCHEMA_PROFILE": "compact",
                    "REA_GHIDRA_STARTUP_TIMEOUT_MS": "120000",
                    "GHIDRA_INSTALL_DIR": str(tc.ghidra_dir),
                    "JAVA_HOME": str(tc.java_home),
                },
            }
        }
    }
    p = ROOT / ".mcp.json"
    p.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return p


def copy_rea_skill() -> None:
    src = REA_PKG / "skills" / "reverse-engineer-anything"
    if not src.exists():
        return
    for dest_root in (ROOT / ".claude" / "skills", ROOT / ".agents" / "skills"):
        dest = dest_root / "reverse-engineer-anything"
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        elif dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)


def setup(force: bool = False, rea: bool = True, testbed: bool = True) -> dict:
    report = {}
    plat = platform_tools()
    for name in ARCHIVE_TOOLS:
        info(f"[{name}] {plat[name]['version']}")
        report[name] = install_archive(name, plat[name], force)
        info(f"  {report[name]}")
    info("[ghidra-snes]")
    report["ghidra_snes"] = install_ghidra_snes(force)
    info(f"  {report['ghidra_snes']}")
    from .emu import ensure_mesen_settings
    report["mesen_settings"] = rel(ensure_mesen_settings())
    if rea:
        info("[rea-agents] MCP do REA (só neste projeto)")
        try:
            report["rea"] = install_rea(force)
        except FabError as e:
            warn(e.render())
            report["rea"] = f"falhou: {e.what}"
        info(f"  {report['rea']}")
    if testbed:
        info("[testbed] ROM homebrew de teste + savestates")
        report["testbed"] = setup_testbed()
        info(f"  {report['testbed']}")
    return report


def setup_testbed() -> dict:
    """Monta a ROM de teste, registra o jogo 'testbed' e cria o savestate 'parado' (no chão)."""
    from .build import build_testbed
    from .emu import Job, run_job, new_run_dir
    from .game import add_rom, states_dir
    from .macro import parse_macro
    from .rom import load_rom
    from .util import now_iso
    rom = build_testbed()
    meta = add_rom(rom, "testbed", force=True, note="ROM homebrew do repositório (fixtures/testbed) — material próprio")
    clean = ROOT / meta["rom"]["clean"]
    sdir = states_dir("testbed")
    dest = sdir / "parado.mss"
    out = new_run_dir("state", "testbed-parado")
    run_job(clean, Job(frames=30, macro=parse_macro("30"), capture_every=0, save_end=dest), out, rom_image=load_rom(clean))
    write_json(dest.with_suffix(".json"), {"created": now_iso(), "how": "fab state boot (power-on + 30 frames)",
                                           "note": "jogador parado no chão, x=64"})
    return {"game": "testbed", "states": [p.name for p in sdir.glob("*.mss")]}


# ── doctor ────────────────────────────────────────────────────────────────────

def doctor(quick: bool = False, rea: bool = False) -> dict:
    checks = []

    def add(status, name, detail=""):
        checks.append({"status": status, "check": name, "detail": detail})

    add("OK" if sys.version_info >= (3, 12) else "FAIL", "python", sys.version.split()[0])
    for mod in ("numpy", "PIL", "matplotlib"):
        try:
            __import__(mod)
            add("OK", f"python:{mod}")
        except ImportError:
            add("FAIL", f"python:{mod}", "rode o fab via fab.cmd/fab.ps1 (cria a .venv) ou pip install -r requirements.txt")
    try:
        tc = toolchain()
    except FabError as e:
        add("FAIL", "manifesto", e.render())
        return {"ok": False, "checks": checks}
    for name in ("java", "analyze_headless", "mesen", "asar", "ffmpeg", "ffprobe"):
        p = getattr(tc, name)
        add("OK" if p.exists() else "FAIL", name, rel(p) if p.exists() else f"em falta: {rel(p)} → fab setup")
    if tc.java.exists():
        v = run([tc.java, "-version"], timeout=60)
        add("OK", "java -version", (v.stderr or v.stdout).splitlines()[0] if (v.stderr or v.stdout) else "?")
    if tc.asar.exists():
        v = run([tc.asar, "--version"], timeout=30)
        add("OK", "asar --version", (v.stdout or v.stderr).splitlines()[0])
    props = tc.ghidra_dir / "Ghidra" / "application.properties"
    if props.exists():
        ver = next((line.split("=", 1)[1] for line in props.read_text().splitlines() if line.startswith("application.version=")), "?")
        add("OK", "ghidra", ver)
    ext = tc.ghidra_dir / "Ghidra" / "Extensions" / "ghidra-snes"
    sla = ext / "data" / "languages" / "65816.sla"
    add("OK" if sla.exists() else "FAIL", "ghidra-snes (65816:LE:24:snes)",
        (ext / ".snesfab-commit").read_text().strip() if (ext / ".snesfab-commit").exists() else "não instalado → fab setup")
    st = tc.mesen_dir / "settings.json"
    if st.exists():
        d = json.loads(st.read_text(encoding="utf-8-sig"))
        io_ok = d.get("Debug", {}).get("ScriptWindow", {}).get("AllowIoOsAccess") is True
        port = d.get("Snes", {}).get("Port1", {}).get("Type")
        add("OK" if io_ok and port == "SnesController" else "FAIL", "mesen settings.json",
            f"Lua I/O={io_ok} porta1={port}")
    else:
        add("FAIL", "mesen settings.json", "em falta → fab setup")
    # ROMs nunca versionadas
    try:
        tracked = run(["git", "-C", ROOT, "ls-files"], timeout=30).stdout.splitlines()
        bad = [f for f in tracked if f.lower().endswith((".sfc", ".smc", ".swc", ".fig", ".mss", ".srm", ".bps",
                                                         ".sqlite", ".sqlite-wal", ".sqlite-shm"))
               or (f.startswith("games/") and f.split("/")[2:3] == ["prints"])]   # prints = frames do jogo
        add("OK" if not bad else "FAIL", "git sem ROMs/states/prints/base", ", ".join(bad[:5]) or "nenhum arquivo proibido versionado")
    except FabError:
        add("WARN", "git", "não consegui listar arquivos")
    from . import memory
    state, detail = memory.dump_state()
    add({"ok": "OK", "stale": "WARN", "absent": "WARN"}.get(state, "FAIL"), "memória CoALA no git (dump)", detail)
    mcp = ROOT / ".mcp.json"
    reapkg = REA_PKG / "package.json"
    add("OK" if reapkg.exists() else "WARN", "rea-agents (tools/rea)", read_json(reapkg).get("version") if reapkg.exists() else "fab setup")
    add("OK" if mcp.exists() else "WARN", ".mcp.json (REA MCP no projeto)", "presente" if mcp.exists() else "fab setup")
    if mcp.exists():
        node_cmd = json.loads(mcp.read_text(encoding="utf-8"))["mcpServers"]["rea"]["command"]
        stable = Path(node_cmd).exists() and "fnm_multishells" not in node_cmd
        add("OK" if stable else "FAIL", ".mcp.json → node", node_cmd if stable else f"{node_cmd} (temporário/inexistente) → fab setup")
        script = json.loads(mcp.read_text(encoding="utf-8"))["mcpServers"]["rea"]["args"][0]
        add("OK" if Path(script).exists() else "FAIL", ".mcp.json → rea.mjs",
            rel(Path(script)) if Path(script).exists() else f"{script} não existe → fab setup")
    if rea and reapkg.exists():
        v = run([_real_node(), REA_PKG / "scripts" / "rea.mjs", "doctor", "--provider", "ghidra",
                 "--format", "json"], env={"GHIDRA_INSTALL_DIR": str(tc.ghidra_dir.resolve()), "JAVA_HOME": str(tc.java_home.resolve())},
                timeout=300)
        try:
            g = next(p for p in json.loads(v.stdout)["providerInspections"] if p["id"] == "ghidra")
            bad = [c["name"] for c in g["checks"] if not c.get("ok")]
            add("OK" if g["available"] else "FAIL", "rea doctor --provider ghidra",
                f"disponível, Ghidra {g.get('providerVersion')}" if g["available"] else f"falhas: {', '.join(bad)}")
        except (ValueError, KeyError, StopIteration):
            add("WARN", "rea doctor --provider ghidra", (v.stdout or v.stderr)[-300:].strip())
        add("INFO", "REA × SNES", "rea-agents 6.7.0 não abre ROMs de SNES (65816 fora da lista raw; morluto/rea#4911 aberto) → usar `fab re`")
    if not quick and tc.mesen.exists():
        try:
            from .emu import Job, run_job, new_run_dir
            from .game import clean_rom
            from .macro import parse_macro
            from .rom import load_rom
            rom = clean_rom("testbed")
            out = new_run_dir("doctor", "smoke")
            r = run_job(rom, Job(frames=20, macro=parse_macro("20"), capture_every=10), out, rom_image=load_rom(rom))
            add("OK" if r["status"] == "ok" and r["frames_captured"] == 2 else "FAIL", "mesen headless + harness Lua",
                f"{r['frames_run']} frames em {r['cpu_seconds']}s CPU")
            shutil.rmtree(out, ignore_errors=True)
        except FabError as e:
            add("FAIL", "mesen headless + harness Lua", e.render())
    ok = all(c["status"] != "FAIL" for c in checks)
    return {"ok": ok, "checks": checks}
