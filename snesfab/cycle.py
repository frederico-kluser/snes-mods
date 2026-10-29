"""Ciclo de evolução de um mod: build → baseline (cache) → run do mod → comparação visual e de RAM →
critérios → pontuação → veredito automático (evoluiu / regrediu / igual) → ledger + relatório.

O veredito VISUAL fica a cargo do agente (olha as folhas) e é registrado com `fab cycle verdict`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import HARNESS_VERSION
from .build import build_mod, variant_safety
from .checks import evaluate_checks, score
from .compare import compare_runs
from .emu import Probe, job_from_scenario, read_probes, read_trace, run_job
from .game import clean_rom, game_dir, load_game, state_path
from .media import postprocess_run
from .mods import load_mod
from .paths import CYCLES, ROOT, RUNS
from .rom import load_rom, parse_addr
from .util import FabError, append_jsonl, now_iso, read_json, read_jsonl, rel, slugify, write_json


def _resolve_state(game: str, sc: dict, mod_dir: Path) -> dict:
    sc = dict(sc)
    st = sc.get("state")
    if st and not str(st).lower().endswith(".mss"):
        sc["state"] = str(state_path(game, st))
    elif st and not Path(st).is_absolute():
        for base in (mod_dir, game_dir(game), ROOT):
            if (base / st).exists():
                sc["state"] = str((base / st).resolve())
                break
    return sc


def _scenario_key(game_sha: str, sc: dict, probes: list[dict]) -> str:
    material = {k: v for k, v in sc.items() if k not in ("checks", "id", "desc")}
    blob = json.dumps({"rom": game_sha, "sc": material, "probes": probes, "h": HARNESS_VERSION}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _macro_digest(sc: dict, mod_dir: Path) -> str:
    src = sc.get("input", sc.get("macro"))
    if isinstance(src, str) and (mod_dir / src).exists():
        return hashlib.sha256((mod_dir / src).read_bytes()).hexdigest()[:16]
    return hashlib.sha256(json.dumps(src, default=str).encode()).hexdigest()[:16]


def run_scenario(rom_path: Path, sc: dict, mod_dir: Path, game: str, out_dir: Path, title: str,
                 extra_probes: list[Probe] | None = None) -> dict:
    img = load_rom(rom_path)
    job = job_from_scenario(sc, mod_dir, game_dir(game))
    if extra_probes:
        job.probes.extend(extra_probes)
    result = run_job(rom_path, job, out_dir, rom_image=img)
    media = postprocess_run(out_dir, title=title)
    return {"run_dir": out_dir, "result": result, "media": media, "trace": read_trace(out_dir), "probes": read_probes(out_dir)}


def _mx_from_probes(probes: list[dict], sites: list[str]) -> dict:
    out = {}
    for site in sites:
        hits = [p for p in probes if p.get("label") == f"hijack {site}"]
        dist: dict[str, int] = {}
        for p in hits:
            key = ("m8" if p["ps"] & 0x20 else "m16") + "," + ("x8" if p["ps"] & 0x10 else "x16") + (",emu" if p.get("emu") else "")
            dist[key] = dist.get(key, 0) + 1
        out[site] = {"executions": len(hits), "flags": dist,
                     "consistent": len(dist) == 1 if dist else None}
    return out


def _wram_sync(base_dir: Path, mod_dir: Path, limit: int = 1024) -> dict:
    """Sincronia mod × variante: quantos bytes da WRAM diferem nos frames amostrados. Em sincronia só diferem
    buffers de paleta (dezenas de bytes); com o timing descolado, centenas/milhares (lógica do jogo)."""
    from .emu import read_wram
    a, b = read_wram(base_dir), read_wram(mod_dir)
    rows = []
    for f in sorted(set(a) & set(b)):
        x, y = a[f], b[f]
        diff = [i for i in range(min(len(x), len(y))) if x[i] != y[i]]
        spans = []
        for i in diff:
            if spans and i - spans[-1][1] <= 16:
                spans[-1][1] = i
            else:
                spans.append([i, i])
        rows.append({"frame": f, "bytes": len(diff),
                     "faixas": [f"7E:{s:04X}-{e:04X}" if e < 0x10000 else f"7F:{s - 0x10000:04X}-{e - 0x10000:04X}"
                                for s, e in spans[:8]]})
    ok = bool(rows) and all(r["bytes"] <= limit for r in rows)
    return {"ok": ok, "frames": rows, "limite": limit,
            "leitura": "em sincronia (só buffers mudam)" if ok else "FORA de sincronia: a variante não serve de base"}


def run_cycle(mod_ref: str | Path, note: str = "") -> dict:
    mod = load_mod(mod_ref)
    mod_dir = Path(mod["_dir"])
    mid, game = mod["id"], mod["game"]
    g = load_game(game)
    cdir = CYCLES / mid
    ledger_path = cdir / "ledger.jsonl"
    history = [r for r in read_jsonl(ledger_path) if r.get("type") == "cycle"]
    n = len(history) + 1
    cyc_dir = cdir / f"cycle-{n:03d}"
    cyc_dir.mkdir(parents=True, exist_ok=True)
    record: dict = {"type": "cycle", "cycle": n, "time": now_iso(), "note": note, "mod": mid, "game": game,
                    "patch_sha": {p: hashlib.sha256((mod_dir / p).read_bytes()).hexdigest()[:16]
                                  for p in mod.get("patches", ["patch.asm"]) if (mod_dir / p).exists()}}
    try:
        build = build_mod(mod_dir)
    except FabError as e:
        record.update({"status": "build_failed", "error": e.what, "score": 0.0})
        prev = next((r for r in reversed(history) if r.get("status") == "ok"), None)
        record["verdict_auto"] = "regrediu" if prev else "falhou"
        append_jsonl(ledger_path, record)
        _write_report(cyc_dir, record, mod, [], None)
        return record

    built_rom = ROOT / build["rom"]
    sites = [h["addr"] for h in build.get("hijacks", [])]
    hijack_probes = [Probe("exec", parse_addr(s), max_hits=300, label=f"hijack {s}") for s in sites]
    base_rom, base_sha = clean_rom(game), g["hashes"]["clean_sha256"]
    variant_cfg = (mod.get("baseline") or {}).get("variant")
    if variant_cfg:
        # mod com CÓDIGO: a base é o mesmo patch com a pintura desligada por VALORES (mesmo timing, mesmo RNG).
        # Contra a ROM limpa a luta descola no frame 1 e os checks alinhados nunca passam.
        try:
            var = build_mod(mod_dir, variant={"name": variant_cfg.get("name", "off"),
                                              "defines": variant_cfg.get("defines", {})})
        except FabError as e:
            record.update({"status": "build_failed", "error": f"variante da base: {e.what}", "score": 0.0,
                           "verdict_auto": "falhou"})
            append_jsonl(ledger_path, record)
            _write_report(cyc_dir, record, mod, [], build)
            return record
        safety = variant_safety(build, var)
        record["baseline"] = {"kind": "variante", "rom": var["rom"], "defines": variant_cfg.get("defines", {}),
                              "safety": safety}
        base_rom, base_sha = ROOT / var["rom"], var["sha256"]
    scen_reports = []
    for sc in mod["scenarios"]:
        sc_res = _resolve_state(game, sc, mod_dir)
        sc_id = sc["id"]
        if variant_cfg:
            n_fr = int(sc_res.get("frames") or 0) or 60
            w0 = int(sc_res.get("warmup", 0))
            sc_res["wram_frames"] = sorted({w0, (w0 + n_fr) // 2, max(w0, n_fr - 1)})
        probe_dicts = [{"kind": p.kind, "addr": p.addr} for p in hijack_probes]
        key = _scenario_key(base_sha, {**sc_res, "_macro": _macro_digest(sc, mod_dir)}, probe_dicts)
        base_dir = RUNS / "baselines" / game / f"{slugify(sc_id)}-{key}"
        if (base_dir / "result.json").exists() and read_json(base_dir / "result.json").get("status") == "ok":
            base = {"run_dir": base_dir, "trace": read_trace(base_dir), "probes": read_probes(base_dir), "cached": True}
        else:
            if base_dir.exists():
                import shutil
                shutil.rmtree(base_dir, ignore_errors=True)
            base_dir.mkdir(parents=True)
            base = run_scenario(base_rom, sc_res, mod_dir, game, base_dir,
                                f"{game} · {sc_id} · BASELINE" + (" (variante)" if variant_cfg else ""), hijack_probes)
            base["cached"] = False
        mod_run_dir = RUNS / "cycles" / mid / f"cycle-{n:03d}-{slugify(sc_id)}"
        if mod_run_dir.exists():
            import shutil
            shutil.rmtree(mod_run_dir, ignore_errors=True)
        mod_run_dir.mkdir(parents=True)
        modrun = run_scenario(built_rom, sc_res, mod_dir, game, mod_run_dir, f"{mid} · {sc_id} · ciclo {n}")
        cmp = compare_runs(base["run_dir"], mod_run_dir, cyc_dir / slugify(sc_id), f"{mid}/{sc_id} ciclo {n}",
                           base_trace=base["trace"], mod_trace=modrun["trace"])
        checks = evaluate_checks(sc.get("checks", []), modrun["trace"], base["trace"])
        mx = _mx_from_probes(base["probes"], sites) if sites else {}
        sync = _wram_sync(base["run_dir"], mod_run_dir) if variant_cfg else None
        scen_reports.append({
            "sync": sync,
            "id": sc_id,
            "state": rel(Path(sc_res["state"])) if sc_res.get("state") else None,
            "baseline_run": rel(base["run_dir"]), "baseline_cached": base.get("cached", False),
            "mod_run": rel(mod_run_dir),
            "mod_sheet": modrun["media"].get("sheets", [None])[0],
            "mod_video": modrun["media"].get("video"),
            "compare": cmp,
            "checks": checks,
            "score": score(checks) if checks else None,
            "hijack_mx_dynamic": mx,
        })

    scored = [s["score"] for s in scen_reports if s["score"] is not None]
    total = round(sum(scored) / len(scored), 4) if scored else 0.0
    prev = next((r for r in reversed(history) if r.get("status") == "ok"), None)
    if prev is None:
        verdict = "primeiro"
    elif total > prev["score"] + 1e-9:
        verdict = "evoluiu"
    elif total < prev["score"] - 1e-9:
        verdict = "regrediu"
    else:
        verdict = "igual"
    passed = sum(1 for s in scen_reports for c in s["checks"] if c.get("passed"))
    count = sum(len(s["checks"]) for s in scen_reports)
    record.update({
        "status": "ok", "score": total, "prev_score": prev["score"] if prev else None,
        "verdict_auto": verdict, "checks_passed": passed, "checks_total": count,
        "goal_met_by_checks": count > 0 and passed == count,
        "visual_change": any((s["compare"].get("frames_divergent") or 0) > 0 for s in scen_reports),
        "build": {"rom": build["rom"], "sha256": build["sha256"][:16], "warnings": build["warnings"],
                  "hijacks_ok": all(h["ok"] for h in build.get("hijacks", [])),
                  "data_ok": all(d.get("ok", True) for d in build.get("data", [])),
                  "data_regions": len(build.get("data", [])), "bps": build.get("bps")},
        "report": rel(cyc_dir / "report.md"),
    })
    append_jsonl(ledger_path, record)
    _write_report(cyc_dir, record, mod, scen_reports, build)
    write_json(cyc_dir / "cycle.json", {**record, "scenarios": scen_reports})
    return {**record, "scenarios": scen_reports}


def record_verdict(mod_ref: str | Path, cycle: int | None, verdict: str, notes: str) -> dict:
    mod = load_mod(mod_ref)
    ledger_path = CYCLES / mod["id"] / "ledger.jsonl"
    cycles = [r for r in read_jsonl(ledger_path) if r.get("type") == "cycle"]
    if not cycles:
        raise FabError("ainda não há ciclos para este mod", f"rode `fab cycle run mods/{mod['id']}`")
    cycle = cycle or cycles[-1]["cycle"]
    allowed = {"evoluiu", "regrediu", "igual", "objetivo-cumprido", "inconclusivo"}
    if verdict not in allowed:
        raise FabError(f"veredito inválido: {verdict}", f"use um de: {', '.join(sorted(allowed))}")
    rec = {"type": "visual_verdict", "cycle": cycle, "time": now_iso(), "verdict": verdict, "notes": notes}
    append_jsonl(ledger_path, rec)
    return rec


def ledger_status(mod_ref: str | Path) -> dict:
    mod = load_mod(mod_ref)
    recs = read_jsonl(CYCLES / mod["id"] / "ledger.jsonl")
    cycles = [r for r in recs if r.get("type") == "cycle"]
    visual = {r["cycle"]: r for r in recs if r.get("type") == "visual_verdict"}
    rows = []
    for c in cycles:
        v = visual.get(c["cycle"])
        rows.append({"cycle": c["cycle"], "time": c["time"], "status": c.get("status"), "score": c.get("score"),
                     "auto": c.get("verdict_auto"), "checks": f"{c.get('checks_passed', 0)}/{c.get('checks_total', 0)}",
                     "visual": v["verdict"] if v else None, "note": c.get("note", "")})
    best = max((c for c in cycles if c.get("status") == "ok"), key=lambda c: c.get("score", 0), default=None)
    return {"mod": mod["id"], "cycles": rows, "best_cycle": best["cycle"] if best else None,
            "max_cycles": mod.get("max_cycles", 8)}


def _write_report(cyc_dir: Path, rec: dict, mod: dict, scens: list[dict], build: dict | None) -> None:
    L = [f"# Ciclo {rec['cycle']} — {mod.get('title', mod['id'])}", "",
         f"- quando: {rec['time']} · nota: {rec.get('note') or '—'}",
         f"- objetivo: {mod['goal']}",
         f"- estado: **{rec.get('status')}** · pontuação: **{rec.get('score')}** (anterior: {rec.get('prev_score')}) "
         f"· veredito automático: **{rec.get('verdict_auto')}**"]
    if rec.get("status") == "build_failed":
        L += ["", "## Build falhou", "```", rec.get("error", ""), "```"]
    if build:
        L += ["", "## Build", f"- ROM: `{build['rom']}` · BPS: `{build.get('bps')}` ({build.get('bps_size')} bytes)",
              f"- avisos do Asar: {len(build['warnings'])}" + (" ⚠ freespace_leaked" if build.get("leak_warning") else "")]
        cc = build.get("code_check") or {}
        if cc.get("instructions_checked"):
            L.append(f"- tamanho das instruções × M/X: {cc['instructions_checked']} conferidas, "
                     f"{len(cc.get('issues', []))} problema(s)")
    bl = rec.get("baseline")
    if bl:
        sf = bl["safety"]
        L += ["", "## Base A/B (variante do próprio mod)",
              f"- ROM da base: `{bl['rom']}` · defines: `{bl['defines']}`",
              f"- variante muda só valores? {'✅ sim' if sf['ok'] else '❌ NÃO'} ({sf['bytes_diferentes']} bytes diferentes)"
              + ("" if sf["ok"] else " — " + "; ".join(sf["issues"])),
              "- por que: mod com código desloca o timing/RNG; contra a ROM limpa a cena descola e os checks alinhados "
              "não valem. A variante tem o MESMO código: só a cor muda."]
        for h in build.get("hijacks", []):
            L.append(f"- hijack {h['addr']} ({h['length']} B, {h['assumed_flags']}, {h['flags_source']}): "
                     f"{'OK' if h['ok'] else 'PROBLEMA'} {'; '.join(h['issues'])}")
            L.append("  - original: " + " | ".join(x.split('  ', 1)[-1].strip() for x in h['original'][:3]))
            L.append("  - patch:    " + " | ".join(x.split('  ', 1)[-1].strip() for x in h['patched'][:2]))
        for r in build.get("regions", []):
            if r.get("kind") == "data":
                L.append(f"- dados {r['start']}–{r['end']} ({r['length']} B, declarado em 'data[]'): {r['evidence']}")
            if r.get("rats"):
                L.append(f"- freespace {r['start']}–{r['end']} (RATS {r['rats']['size']} B, código em {r['rats']['code_start']})")
        for d in build.get("data", []):
            if not d.get("ok"):
                L.append(f"- ⚠ dados {d['addr']} ({d['length']} B): {d.get('issue', '')}")
    for s in scens:
        c = s["compare"]
        L += ["", f"## Cenário `{s['id']}` — pontuação {s['score']}",
              f"- state: `{s['state']}` · baseline: `{s['baseline_run']}`{' (cache)' if s['baseline_cached'] else ''} · mod: `{s['mod_run']}`",
              f"- divergência visual: {c.get('frames_divergent', '?')}/{c.get('frames_compared', '?')} frames "
              f"(primeira f{c.get('first_divergence_frame')}, pico {c.get('max_changed_pct')}% em f{c.get('max_changed_frame')})"]
        if s.get("sync"):
            sy = s["sync"]
            L.append(f"- sincronia mod × variante (WRAM): {'✅' if sy['ok'] else '❌'} {sy['leitura']} — "
                     + ", ".join(f"f{r['frame']}: {r['bytes']} B" for r in sy["frames"]))
        for site, mx in (s.get("hijack_mx_dynamic") or {}).items():
            L.append(f"- M/X dinâmico no hijack {site} (baseline): {mx['executions']} execuções, {mx['flags']}"
                     + ("" if mx["executions"] else " — ⚠ o cenário não passa pelo hijack"))
        L += ["", "| check | resultado | valores | descrição |", "|---|---|---|---|"]
        for ch in s["checks"]:
            vals = ch.get("error") or (f"{ch.get('lhs')} vs {ch.get('rhs')}" if "lhs" in ch else str(ch.get("value")))
            L.append(f"| `{ch['expr']}` | {'✅' if ch['passed'] else '❌'} | {vals} | {ch.get('desc', '')} |")
        L += ["", "**Olhar (ferramenta de leitura de imagens):**",
              f"- lado a lado: `{c.get('compare_sheet')}`", f"- RAM mod × baseline: `{c.get('trace_plot')}`",
              f"- divergência: `{c.get('divergence_plot')}`", f"- folha do mod: `{s['mod_sheet']}` · vídeo: `{s['mod_video']}`"]
    L += ["", "## Próximo passo",
          "1. Ver as imagens acima e decidir o veredito visual: "
          f"`fab cycle verdict mods/{mod['id']} --cycle {rec['cycle']} <evoluiu|regrediu|igual|objetivo-cumprido|inconclusivo> --notes \"…\"`",
          "2. Se não cumpriu: ajustar `patch.asm` (com evidência nova) e correr outro ciclo."]
    (cyc_dir / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
