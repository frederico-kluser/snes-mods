"""CLI `fab` — fábrica de mods de SNES. `fab <comando> --help` para detalhes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .util import EXIT_FAIL, EXIT_OK, EXIT_USAGE, FabError, rel


def out(obj) -> None:
    if isinstance(obj, str):
        print(obj)
    else:
        print(json.dumps(obj, indent=1, ensure_ascii=False, default=str))


def _evidence(rec: dict) -> None:
    """Imprime um registro de evidência com o cabeçalho primeiro (id, perfil, limitações)."""
    print(f"evidence_id: {rec['evidence_id']}  ({rec['kind']})")
    print("analysis_profile: " + json.dumps(rec["analysis_profile"], ensure_ascii=False, default=str))
    res = rec["normalized_result"]
    lines_key = next((k for k in ("instructions", "matches") if isinstance(res, dict) and k in res), None)
    if rec["kind"] == "decompile":
        print("normalized_result:")
        for item in res:
            print(f"  // {item.get('entry')} {item.get('name')} (pedido {item.get('request')})")
            body = (item.get("c") or f"/* erro: {item.get('error')} */").replace("\r\n", "\n").strip("\n")
            print("\n".join("  " + l for l in body.splitlines()))
    elif lines_key:
        meta = {k: v for k, v in res.items() if k != lines_key}
        print("normalized_result: " + json.dumps(meta, ensure_ascii=False, default=str))
        for line in res[lines_key]:
            print("  " + line)
    else:
        print("normalized_result:")
        print(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    print("limitations:")
    for l in rec["limitations"]:
        print("  - " + l)


# ── comandos ──────────────────────────────────────────────────────────────────

def cmd_setup(a):
    from .setup_tools import setup
    out(setup(force=a.force, rea=not a.no_rea, testbed=not a.no_testbed))


def cmd_doctor(a):
    from .setup_tools import doctor
    r = doctor(quick=a.quick, rea=a.rea)
    for c in r["checks"]:
        print(f"{c['status']:<4} {c['check']:<34} {c['detail']}")
    print("RESULTADO: " + ("SAUDÁVEL" if r["ok"] else "COM FALHAS"))
    return EXIT_OK if r["ok"] else EXIT_FAIL


def cmd_rom_add(a):
    from .game import add_rom
    m = add_rom(Path(a.path), a.id, a.force, a.note or "")
    out({k: m[k] for k in ("id", "title", "mapping", "size", "smc_header", "checksum", "rom") if k in m}
        | {"header": m["header"], "next": [f"fab state boot {m['id']} <nome> --macro \"…\"  (ou fab play {m['id']} + fab state import)",
                                           f"fab re cdl {m['id']} --state <nome> --frames 3600", f"fab re analyze {m['id']}"]})


def cmd_rom_info(a):
    from .game import load_game
    g = load_game(a.game)
    g.pop("_dir", None)
    out(g)


def cmd_rom_list(a):
    from .game import list_games
    out(list_games())


def cmd_addr(a):
    from .game import clean_rom
    from .rom import fmt_addr, load_rom, parse_addr, wram_offset, is_mmio
    img = load_rom(Path(a.rom) if a.rom else clean_rom(a.game))
    if a.pc:
        pc = int(a.value, 16) if not a.value.startswith("0x") else int(a.value, 0)
        s = img.to_snes(pc)
        out({"pc": f"0x{pc:06X}", "snes": fmt_addr(s), "mapping": img.mapping})
        return
    addr = parse_addr(a.value)
    r = {"snes": fmt_addr(addr), "mapping": img.mapping}
    w = wram_offset(addr)
    if w is not None:
        r["wram"] = f"7E:{w:04X}" if w < 0x10000 else f"7F:{w - 0x10000:04X}"
        r["kind"] = "WRAM"
    elif is_mmio(addr):
        r["kind"] = "MMIO"
    else:
        try:
            pc = img.to_pc(addr)
            r.update({"kind": "ROM", "pc": f"0x{pc:06X}", "canonical": fmt_addr(img.to_snes(pc))})
        except FabError as e:
            r.update({"kind": "?", "note": e.what})
    out(r)


def cmd_disasm(a):
    from .disasm65816 import disassemble
    from .game import clean_rom
    from .rom import load_rom, parse_addr
    img = load_rom(Path(a.rom) if a.rom else clean_rom(a.game))
    addr = parse_addr(a.addr)
    m8, x8 = True, True
    if a.flags:
        f = a.flags.lower().replace(" ", "").split(",")
        m8 = "m16" not in f
        x8 = "x16" not in f
    pc = img.to_pc(addr)
    for ins in disassemble(img.data[pc:pc + a.count * 4 + 8], addr, count=a.count, m8=m8, x8=x8):
        print(ins.fmt())
    print("; flags iniciais assumidas: " + ("m8" if m8 else "m16") + "," + ("x8" if x8 else "x16")
          + " — confirme com `fab probe exec` (o '?' indica PLP/RTI/XCE: estado incerto)")


def cmd_play(a):
    from .game import play
    out(play(a.game, Path(a.rom) if a.rom else None))


def cmd_state_list(a):
    from .game import list_states
    out(list_states(a.game))


def cmd_state_import(a):
    from .game import import_state
    out(import_state(a.game, a.name, a.file, a.slot, a.note or ""))


def cmd_state_boot(a):
    from .emu import Job, run_job, new_run_dir
    from .game import clean_rom, state_path, states_dir
    from .investigate import _macro
    from .macro import total_frames
    from .media import postprocess_run
    from .rom import load_rom
    from .util import now_iso, slugify, write_json
    rom = clean_rom(a.game)
    steps = _macro(a.macro)
    frames = max(a.frames or 0, total_frames(steps), 1)
    start = state_path(a.game, a.from_state) if a.from_state else None
    dest = states_dir(a.game) / f"{slugify(a.name)}.mss"
    run_dir = new_run_dir("state", f"{a.game}-{a.name}")
    job = Job(frames=frames, state=start, macro=steps, capture_every=max(1, frames // 16), save_end=dest)
    r = run_job(rom, job, run_dir, rom_image=load_rom(rom))
    media = postprocess_run(run_dir, title=f"{a.game}: a caminho do state '{a.name}'", video=False)
    write_json(dest.with_suffix(".json"), {"created": now_iso(), "how": f"fab state boot (from={a.from_state or 'power-on'}, frames={frames})",
                                           "macro": a.macro, "note": a.note or "", "preview": media.get("sheets", [None])[0]})
    out({"state": rel(dest), "frames": r["frames_run"], "preview_sheet": media.get("sheets"),
         "check": "abra a folha de pré-visualização e confirme que o último frame mostra o momento certo"})


def cmd_run(a):
    from .emu import Job, Probe, Watch, read_probes, read_trace, run_job, new_run_dir
    from .game import clean_rom, state_path
    from .investigate import _macro
    from .macro import total_frames
    from .media import postprocess_run, trace_plot
    from .mods import load_mod
    from .paths import BUILD
    from .rom import load_rom, parse_addr
    if a.mod:
        mod = load_mod(a.mod)
        rom = BUILD / mod["id"] / f"{mod['id']}.sfc"
        if not rom.exists():
            raise FabError(f"ROM do mod ainda não montada: {rom}", f"rode `fab build mods/{mod['id']}`")
    else:
        rom = Path(a.rom) if a.rom else clean_rom(a.game)
    steps = _macro(a.macro)
    frames = max(a.frames or 0, total_frames(steps), 1)
    probes = []
    for p in a.probe or []:
        kind, _, addr = p.partition(":")
        probes.append(Probe(kind, parse_addr(addr)))
    job = Job(frames=frames, state=state_path(a.game, a.state) if a.state else None, macro=steps,
              watches=[Watch.from_spec(w) for w in a.watch or []], probes=probes,
              capture_every=a.every, wram_every=a.wram_every or 0)
    run_dir = new_run_dir("run", a.label or a.game)
    r = run_job(rom, job, run_dir, rom_image=load_rom(rom))
    media = postprocess_run(run_dir, title=a.label or f"{a.game} run", video=not a.no_video)
    tr = read_trace(run_dir)
    res = {"run": rel(run_dir), "status": r["status"], "frames": r["frames_run"], "media": media}
    if a.watch:
        res["trace_plot"] = rel(trace_plot(tr, run_dir / "trace.png", a.label or a.game))
    if probes:
        res["probe_hits"] = r["probe_hits"]
        res["probes_file"] = rel(run_dir / "probes.jsonl")
    out(res)


PROBE_KINDS = {"writes": "write", "write": "write", "reads": "read", "read": "read", "exec": "exec"}


def cmd_probe(a):
    from .investigate import probe
    _evidence(probe(a.game, PROBE_KINDS[a.kind], a.addr, a.end, a.state, a.macro, a.frames,
                    Path(a.rom) if a.rom else None, a.max_hits))


def cmd_ram_search(a):
    from .investigate import ram_search
    out(ram_search(a.game, a.state, a.macro, a.frames, a.every, Path(a.rom) if a.rom else None))


def cmd_ram_query(a):
    from .investigate import ram_query
    r = ram_query(Path(a.run), a.changed, a.unchanged, a.increased, a.decreased, a.equals, a.word, a.limit, a.game)
    if "evidence_id" in r:
        _evidence(r)
    else:
        out(r)


def cmd_re(a):
    from . import ghidra
    from .investigate import cdl
    if a.re_cmd == "cdl":
        out(cdl(a.game, a.state, a.macro, a.frames))
    elif a.re_cmd == "analyze":
        out(ghidra.analyze(a.game))
    elif a.re_cmd == "funcs":
        _evidence(ghidra.q_funcs(a.game, a.limit, a.pattern))
    elif a.re_cmd == "func":
        _evidence(ghidra.q_func(a.game, a.addr))
    elif a.re_cmd == "xrefs":
        _evidence(ghidra.q_xrefs(a.game, a.addr))
    elif a.re_cmd == "search":
        _evidence(ghidra.q_search(a.game, a.regex, a.limit))
    elif a.re_cmd == "decompile":
        _evidence(ghidra.q_decompile(a.game, a.addrs))
    elif a.re_cmd == "evidence":
        from .evidence import find, ledger
        if a.id:
            rec = find(a.game, a.id)
            if not rec:
                raise FabError(f"evidência {a.id} não encontrada")
            _evidence(rec)
        else:
            for rec in ledger(a.game)[-a.limit:]:
                print(f"{rec['evidence_id']}  {rec['time']}  {rec['kind']:<12} {json.dumps(rec['query'], ensure_ascii=False)}")


def cmd_mod(a):
    from .mods import list_mods, new_mod
    if a.mod_cmd == "new":
        d = new_mod(a.id, a.game, a.title or "", a.goal or "")
        out({"mod": rel(d), "files": [rel(p) for p in sorted(d.iterdir())],
             "next": "preencha o mod.json (state, input, watch, checks) e patch.asm com evidências; depois `fab cycle run`"})
    else:
        out(list_mods())


def cmd_build(a):
    from .build import build_mod
    r = build_mod(Path(a.mod) if Path(a.mod).exists() else a.mod)
    keep = {k: r[k] for k in ("mod", "rom", "ok", "warnings", "leak_warning", "bps", "bps_size", "sha256")}
    keep["regions"] = r["regions"]
    keep["labels"] = dict(list(r["labels"].items())[:40])
    out(keep)
    return EXIT_OK if r["ok"] else EXIT_FAIL


def cmd_cycle(a):
    from .cycle import ledger_status, record_verdict, run_cycle
    if a.cycle_cmd == "run":
        r = run_cycle(a.mod, a.note or "")
        brief = {k: r.get(k) for k in ("cycle", "status", "score", "prev_score", "verdict_auto", "checks_passed",
                                        "checks_total", "goal_met_by_checks", "visual_change", "report", "error")}
        brief["look_at"] = [p for s in r.get("scenarios", []) for p in
                            (s["compare"].get("compare_sheet"), s["compare"].get("trace_plot"))
                            if p]
        out(brief)
    elif a.cycle_cmd == "verdict":
        out(record_verdict(a.mod, a.cycle, a.verdict, a.notes or ""))
    else:
        out(ledger_status(a.mod))


def cmd_media(a):
    from .media import analyze_media
    from .paths import MEDIA_INBOX, RUNS
    from .util import slugify, stamp
    if a.media_cmd == "analyze":
        p = Path(a.path)
        dest = RUNS / "media" / f"{stamp()}-{slugify(p.stem)}"
        at = [float(x) for x in a.at.split(",")] if a.at else None
        out(analyze_media(p, dest, a.n, a.scene, at))
    elif a.media_cmd == "inbox":
        MEDIA_INBOX.mkdir(parents=True, exist_ok=True)
        done = RUNS / "media" / "inbox-processed.json"
        seen = json.loads(done.read_text()) if done.exists() else {}
        results = []
        for f in sorted(MEDIA_INBOX.iterdir()):
            if f.name.startswith(".") or f.name in seen:
                continue
            dest = RUNS / "media" / f"{stamp()}-{slugify(f.stem)}"
            try:
                r = analyze_media(f, dest, a.n, a.scene)
                seen[f.name] = r["out_dir"]
                results.append({"file": f.name, "out": r["out_dir"], "sheets": r.get("sheets")})
            except FabError as e:
                results.append({"file": f.name, "error": e.what})
        done.parent.mkdir(parents=True, exist_ok=True)
        done.write_text(json.dumps(seen, indent=1))
        out(results or "inbox sem arquivos novos (media/inbox/)")
    elif a.media_cmd == "compare":
        from .compare import compare_runs
        from .emu import read_trace
        A, B = Path(a.a), Path(a.b)
        ta = read_trace(A) if (A / "trace.csv").exists() else None
        tb = read_trace(B) if (B / "trace.csv").exists() else None
        dest = RUNS / "compare" / f"{stamp()}-{A.name[:20]}-vs-{B.name[:20]}"
        out(compare_runs(A, B, dest, a.title or "comparação", ta, tb))


def cmd_bps(a):
    from . import bps
    src = Path(a.rom).read_bytes()
    from .rom import SMC_HEADER
    if len(src) % 1024 == SMC_HEADER:
        src = src[SMC_HEADER:]
    Path(a.out).write_bytes(bps.apply(src, Path(a.patch).read_bytes()))
    out({"written": a.out})


def cmd_testbed(a):
    from .setup_tools import setup_testbed
    out(setup_testbed())


def cmd_selftest(a):
    import unittest
    from .paths import ROOT

    def flatten(suite):
        for t in suite:
            if isinstance(t, unittest.TestSuite):
                yield from flatten(t)
            else:
                yield t

    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    if a.quick:
        suite = unittest.TestSuite(t for t in flatten(suite) if "e2e" not in t.id())
    r = unittest.TextTestRunner(verbosity=2).run(suite)
    return EXIT_OK if r.wasSuccessful() else EXIT_FAIL


# ── parser ────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fab", description="Fábrica de mods de SNES (ROM → evidência → patch → emulação → vídeo → veredito)")
    p.add_argument("--version", action="version", version=f"snesfab {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup", help="instala/configura o toolchain pinado (idempotente)")
    s.add_argument("--force", action="store_true")
    s.add_argument("--no-rea", action="store_true")
    s.add_argument("--no-testbed", action="store_true")
    s.set_defaults(fn=cmd_setup)

    s = sub.add_parser("doctor", help="verifica toolchain, harness headless e regras do repo")
    s.add_argument("--quick", action="store_true", help="sem smoke test no emulador")
    s.add_argument("--rea", action="store_true", help="inclui `rea doctor`")
    s.set_defaults(fn=cmd_doctor)

    rom = sub.add_parser("rom", help="registrar/inspecionar ROMs").add_subparsers(dest="rom_cmd", required=True)
    s = rom.add_parser("add", help="registra uma ROM (copia, remove cabeçalho SMC, detecta mapa, base limpa só leitura)")
    s.add_argument("path")
    s.add_argument("--id")
    s.add_argument("--force", action="store_true")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_rom_add)
    s = rom.add_parser("info")
    s.add_argument("game")
    s.set_defaults(fn=cmd_rom_info)
    s = rom.add_parser("list")
    s.set_defaults(fn=cmd_rom_list)

    s = sub.add_parser("addr", help="converte endereço SNES ↔ offset (--pc) e classifica (ROM/WRAM/MMIO)")
    s.add_argument("game")
    s.add_argument("value")
    s.add_argument("--pc", action="store_true", help="o valor é um offset no arquivo limpo")
    s.add_argument("--rom")
    s.set_defaults(fn=cmd_addr)

    s = sub.add_parser("disasm", help="desmontagem linear 65816 com rastreio de SEP/REP")
    s.add_argument("game")
    s.add_argument("addr")
    s.add_argument("--count", type=int, default=24)
    s.add_argument("--flags", help="ex.: m8,x16 (padrão m8,x8)")
    s.add_argument("--rom", help="outra ROM (ex.: build/<mod>/<mod>.sfc)")
    s.set_defaults(fn=cmd_disasm)

    s = sub.add_parser("play", help="abre o MesenCE (GUI) para jogar e gravar savestates (Shift+F1..)")
    s.add_argument("game")
    s.add_argument("--rom")
    s.set_defaults(fn=cmd_play)

    st = sub.add_parser("state", help="savestates do jogo").add_subparsers(dest="state_cmd", required=True)
    s = st.add_parser("list")
    s.add_argument("game")
    s.set_defaults(fn=cmd_state_list)
    s = st.add_parser("import", help="importa .mss (--file) ou slot do Mesen (--slot N)")
    s.add_argument("game")
    s.add_argument("name")
    s.add_argument("--file")
    s.add_argument("--slot", type=int)
    s.add_argument("--note")
    s.set_defaults(fn=cmd_state_import)
    s = st.add_parser("boot", help="cria um state headless: power-on (ou --from-state) + macro → grava no fim")
    s.add_argument("game")
    s.add_argument("name")
    s.add_argument("--macro", help="arquivo .txt ou texto inline com ';' separando linhas")
    s.add_argument("--frames", type=int)
    s.add_argument("--from-state")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_state_boot)

    s = sub.add_parser("run", help="roda um cenário headless e gera frames/vídeo/folha/traço")
    s.add_argument("game")
    s.add_argument("--state")
    s.add_argument("--macro")
    s.add_argument("--frames", type=int)
    s.add_argument("--watch", action="append", help="nome=7E:0096:2s (repetível)")
    s.add_argument("--probe", action="append", help="write:7E:007D | read:… | exec:80:A420 (repetível)")
    s.add_argument("--every", type=int, default=2, help="captura 1 frame a cada N (0 = sem frames)")
    s.add_argument("--wram-every", type=int)
    s.add_argument("--rom")
    s.add_argument("--mod", help="usa a ROM montada do mod")
    s.add_argument("--label")
    s.add_argument("--no-video", action="store_true")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("probe", help="sonda dinâmica: quem escreve/lê um endereço ou o que executa nele (M/X reais)")
    s.add_argument("kind", choices=["writes", "reads", "exec", "write", "read"])
    s.add_argument("game")
    s.add_argument("addr")
    s.add_argument("--end")
    s.add_argument("--state")
    s.add_argument("--macro")
    s.add_argument("--frames", type=int, default=300)
    s.add_argument("--rom")
    s.add_argument("--max-hits", type=int, default=4000)
    s.set_defaults(fn=cmd_probe)

    ram = sub.add_parser("ram", help="busca de RAM por diferenças entre frames").add_subparsers(dest="ram_cmd", required=True)
    s = ram.add_parser("search", help="roda o cenário gravando a WRAM a cada N frames")
    s.add_argument("game")
    s.add_argument("--state")
    s.add_argument("--macro")
    s.add_argument("--frames", type=int, default=120)
    s.add_argument("--every", type=int, default=1)
    s.add_argument("--rom")
    s.set_defaults(fn=cmd_ram_search)
    s = ram.add_parser("query", help="filtra candidatos: --changed A:B --unchanged A:B --increased/--decreased A:B --equals F=V")
    s.add_argument("run")
    s.add_argument("--game", help="registra como evidência do jogo")
    for flag in ("changed", "unchanged", "increased", "decreased", "equals"):
        s.add_argument(f"--{flag}", action="append")
    s.add_argument("--word", action="store_true", help="valores de 16 bits")
    s.add_argument("--limit", type=int, default=40)
    s.set_defaults(fn=cmd_ram_query)

    re_ = sub.add_parser("re", help="análise estática (Ghidra headless + ghidra-snes) com evidência").add_subparsers(dest="re_cmd", required=True)
    s = re_.add_parser("cdl", help="roda um cenário e acumula o Code/Data Log (sementes M/X para o Ghidra)")
    s.add_argument("game")
    s.add_argument("--state")
    s.add_argument("--macro")
    s.add_argument("--frames", type=int, default=1800)
    s.set_defaults(fn=cmd_re)
    s = re_.add_parser("analyze", help="importa + semeia + analisa + exporta")
    s.add_argument("game")
    s.set_defaults(fn=cmd_re)
    s = re_.add_parser("funcs")
    s.add_argument("game")
    s.add_argument("--pattern")
    s.add_argument("--limit", type=int, default=60)
    s.set_defaults(fn=cmd_re)
    s = re_.add_parser("func", help="função que contém o endereço: instruções com M/X, chamadores, chamadas")
    s.add_argument("game")
    s.add_argument("addr")
    s.set_defaults(fn=cmd_re)
    s = re_.add_parser("xrefs", help="referências a um endereço (WRAM com espelhos, MMIO, ROM)")
    s.add_argument("game")
    s.add_argument("addr")
    s.set_defaults(fn=cmd_re)
    s = re_.add_parser("search", help="regex sobre mnemónica+operandos da listagem")
    s.add_argument("game")
    s.add_argument("regex")
    s.add_argument("--limit", type=int, default=100)
    s.set_defaults(fn=cmd_re)
    s = re_.add_parser("decompile")
    s.add_argument("game")
    s.add_argument("addrs", nargs="+")
    s.set_defaults(fn=cmd_re)
    s = re_.add_parser("evidence", help="livro-razão de evidências do jogo (ou uma evidência por id)")
    s.add_argument("game")
    s.add_argument("id", nargs="?")
    s.add_argument("--limit", type=int, default=30)
    s.set_defaults(fn=cmd_re)

    mod = sub.add_parser("mod", help="criar/listar mods").add_subparsers(dest="mod_cmd", required=True)
    s = mod.add_parser("new")
    s.add_argument("id")
    s.add_argument("--game", required=True)
    s.add_argument("--title")
    s.add_argument("--goal")
    s.set_defaults(fn=cmd_mod)
    s = mod.add_parser("list")
    s.set_defaults(fn=cmd_mod)

    s = sub.add_parser("build", help="monta o mod com o Asar numa cópia da base limpa (+ verificação de hijack + BPS)")
    s.add_argument("mod")
    s.set_defaults(fn=cmd_build)

    cy = sub.add_parser("cycle", help="ciclo de evolução: build → baseline → mod → comparação → critérios → veredito").add_subparsers(dest="cycle_cmd", required=True)
    s = cy.add_parser("run")
    s.add_argument("mod")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_cycle)
    s = cy.add_parser("verdict", help="registra o veredito visual do agente para um ciclo")
    s.add_argument("mod")
    s.add_argument("verdict", choices=["evoluiu", "regrediu", "igual", "objetivo-cumprido", "inconclusivo"])
    s.add_argument("--cycle", type=int)
    s.add_argument("--notes")
    s.set_defaults(fn=cmd_cycle)
    s = cy.add_parser("status")
    s.add_argument("mod")
    s.set_defaults(fn=cmd_cycle)

    md = sub.add_parser("media", help="analisar vídeos/imagens gravados (ffmpeg → folhas de contato)").add_subparsers(dest="media_cmd", required=True)
    s = md.add_parser("analyze")
    s.add_argument("path")
    s.add_argument("--n", type=int, default=16, help="frames uniformes")
    s.add_argument("--scene", type=float, default=0.25, help="limiar de mudança de cena")
    s.add_argument("--at", help="instantes extra em segundos, ex.: 1.5,2.25")
    s.set_defaults(fn=cmd_media)
    s = md.add_parser("inbox", help="analisa os arquivos novos em media/inbox/")
    s.add_argument("--n", type=int, default=16)
    s.add_argument("--scene", type=float, default=0.25)
    s.set_defaults(fn=cmd_media)
    s = md.add_parser("compare", help="compara duas runs (frames + traços)")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--title")
    s.set_defaults(fn=cmd_media)

    s = sub.add_parser("bps", help="aplica um patch BPS a uma ROM (para quem recebe o mod)")
    s.add_argument("rom")
    s.add_argument("patch")
    s.add_argument("out")
    s.set_defaults(fn=cmd_bps)

    s = sub.add_parser("testbed", help="(re)monta a ROM homebrew de teste e o state 'parado'")
    s.set_defaults(fn=cmd_testbed)

    s = sub.add_parser("selftest", help="testes unitários + ponta a ponta (testbed)")
    s.add_argument("--quick", action="store_true", help="sem os testes e2e no emulador")
    s.set_defaults(fn=cmd_selftest)
    return p


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        rc = args.fn(args)
        return rc if isinstance(rc, int) else EXIT_OK
    except FabError as e:
        print(e.render(), file=sys.stderr)
        return e.code
    except KeyboardInterrupt:
        return 130
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"Erro: inesperado ({type(e).__name__}: {e}) — Solução: reporte com a stack acima", file=sys.stderr)
        return EXIT_FAIL
