"""Critérios de aceitação de um mod, avaliados sobre os traços de RAM (mod vs baseline).

Expressões Python restritas (AST com lista branca), com séries numpy:
    min(y) < baseline.min(y) - 200           ← o ápice do pulo fica 12,5 px mais alto
    count(edges(vy < -60)) >= 2              ← dois impulsos de subida no mesmo voo
    at(lives, 300) == at(lives, 0)           ← não perdeu vidas
    any(pressed('B') & (air == 1))           ← B pressionado no ar
Variáveis: nomes dos watches (série do mod), `baseline.<nome>`, `frame`, `input`.
Funções: min max mean sum abs len first last at window delta changes count any all
         edges falls argmin argmax pressed(botão) clip.
"""

from __future__ import annotations

import ast
import operator as op

import numpy as np

from .macro import BUTTON_BITS
from .util import FabError


class _NS:
    def __init__(self, data: dict[str, np.ndarray]):
        self._data = data

    def get(self, name):
        if name not in self._data:
            raise FabError(f"série desconhecida: {name}", f"disponíveis: {', '.join(sorted(self._data))}")
        return self._data[name]


def _edges(c):
    c = np.asarray(c).astype(bool)
    return np.concatenate([[c[0]], c[1:] & ~c[:-1]]) if c.size else c


def _falls(c):
    c = np.asarray(c).astype(bool)
    return np.concatenate([[False], ~c[1:] & c[:-1]]) if c.size else c


def _num(x):
    if isinstance(x, np.ndarray) and x.ndim == 0:
        return x.item()
    if isinstance(x, np.generic):
        return x.item()
    return x


FUNCS = {
    "min": lambda s: _num(np.min(s)), "max": lambda s: _num(np.max(s)), "mean": lambda s: float(np.mean(s)),
    "sum": lambda s: _num(np.sum(s)), "abs": np.abs, "len": len, "clip": np.clip,
    "first": lambda s: _num(np.asarray(s)[0]), "last": lambda s: _num(np.asarray(s)[-1]),
    "at": lambda s, f: _num(np.asarray(s)[int(f)]),
    "window": lambda s, a, b: np.asarray(s)[int(a):int(b)],
    "delta": lambda s: np.diff(np.asarray(s)),
    "changes": lambda s: int(np.count_nonzero(np.diff(np.asarray(s)))),
    "count": lambda c: int(np.count_nonzero(c)),
    "any": lambda c: bool(np.any(c)), "all": lambda c: bool(np.all(c)),
    "edges": _edges, "falls": _falls,
    "argmin": lambda s: int(np.argmin(s)), "argmax": lambda s: int(np.argmax(s)),
}

# Inteiros Python maiores que isto só saem de expressões patológicas: 9**9**9 ou 1 << 10**10 travariam o ciclo
# (as séries numpy dão a volta em 64 bits e não precisam de limite).
MAX_INT_BITS = 4096


def _pow(a, b):
    if isinstance(a, int) and isinstance(b, int) and b > 0 and max(abs(a).bit_length(), 1) * b > MAX_INT_BITS:
        raise FabError(f"potência grande demais (passa de {MAX_INT_BITS} bits)")
    return op.pow(a, b)


def _lshift(a, b):
    if isinstance(a, int) and isinstance(b, int) and b > MAX_INT_BITS:
        raise FabError(f"deslocamento grande demais (passa de {MAX_INT_BITS} bits)")
    return op.lshift(a, b)


def _numeric(fn):
    def run(a, b):
        # 'a' * 10**10 ou [0] * 10**9 estourariam a memória; texto só serve de argumento, ex.: pressed('B')
        if isinstance(a, (str, list, tuple)) or isinstance(b, (str, list, tuple)):
            raise FabError("aritmética só com números e séries", "texto entre aspas só serve em pressed('B')")
        return fn(a, b)
    return run


BIN = {k: _numeric(f) for k, f in {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.FloorDiv: op.floordiv,
    ast.Mod: op.mod, ast.Pow: _pow, ast.BitAnd: op.and_, ast.BitOr: op.or_, ast.BitXor: op.xor,
    ast.LShift: _lshift, ast.RShift: op.rshift}.items()}
CMP = {ast.Lt: op.lt, ast.LtE: op.le, ast.Gt: op.gt, ast.GtE: op.ge, ast.Eq: op.eq, ast.NotEq: op.ne}


class Evaluator:
    def __init__(self, mod: dict[str, list], baseline: dict[str, list] | None = None):
        self.mod = {k: np.asarray(v, dtype=np.int64) for k, v in mod.items()}
        self.base = {k: np.asarray(v, dtype=np.int64) for k, v in (baseline or {}).items()}
        inp = self.mod.get("input", np.zeros(len(next(iter(self.mod.values()), [])), dtype=np.int64))
        self.funcs = dict(FUNCS)
        self.funcs["pressed"] = lambda b: (inp & BUTTON_BITS[str(b).lower()]) != 0

    def eval(self, expr: str):
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as e:
            raise FabError(f"expressão inválida: {expr!r} ({e.msg})") from e
        return self._ev(tree.body)

    def _ev(self, n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float, bool, str)):
            return n.value
        if isinstance(n, ast.Name):
            if n.id in ("True", "False"):
                return n.id == "True"
            if n.id == "frame":
                return self.mod.get("frame", np.arange(len(next(iter(self.mod.values())))))
            if n.id in self.mod:
                return self.mod[n.id]
            raise FabError(f"nome desconhecido na expressão: {n.id}",
                           f"séries: {', '.join(sorted(self.mod))}; use baseline.<nome> para a baseline")
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in ("baseline", "mod"):
            src = self.base if n.value.id == "baseline" else self.mod
            if n.attr not in src:
                raise FabError(f"{n.value.id}.{n.attr} não existe", "o cenário vigia esse endereço nas duas runs?")
            return src[n.attr]
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) \
                and n.func.value.id == "baseline" and n.func.attr in FUNCS:
            # baseline.min(y) ≡ min(baseline.y)
            args = [self.base[a.id] if isinstance(a, ast.Name) and a.id in self.base else self._ev(a) for a in n.args]
            return FUNCS[n.func.attr](*args)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in self.funcs and not n.keywords:
            return self.funcs[n.func.id](*[self._ev(a) for a in n.args])
        if isinstance(n, ast.BinOp) and type(n.op) in BIN:
            return BIN[type(n.op)](self._ev(n.left), self._ev(n.right))
        if isinstance(n, ast.UnaryOp):
            v = self._ev(n.operand)
            if isinstance(n.op, ast.USub):
                return -v
            if isinstance(n.op, ast.UAdd):
                return +v
            if isinstance(n.op, ast.Not):
                return np.logical_not(v) if isinstance(v, np.ndarray) else (not v)
            if isinstance(n.op, ast.Invert):
                return ~v
        if isinstance(n, ast.BoolOp):
            vals = [self._ev(v) for v in n.values]
            if any(isinstance(v, np.ndarray) for v in vals):
                f = np.logical_and if isinstance(n.op, ast.And) else np.logical_or
                out = vals[0]
                for v in vals[1:]:
                    out = f(out, v)
                return out
            return all(vals) if isinstance(n.op, ast.And) else any(vals)
        if isinstance(n, ast.Compare):
            left = self._ev(n.left)
            result = None
            for o, comp in zip(n.ops, n.comparators):
                right = self._ev(comp)
                if type(o) not in CMP:
                    raise FabError("comparador não suportado")
                r = CMP[type(o)](left, right)
                result = r if result is None else (np.logical_and(result, r) if isinstance(r, np.ndarray) else (result and r))
                left = right
            return result
        if isinstance(n, ast.Subscript):
            v = self._ev(n.value)
            s = n.slice
            if isinstance(s, ast.Slice):
                lo = self._ev(s.lower) if s.lower else None
                hi = self._ev(s.upper) if s.upper else None
                return v[lo:hi]
            return _num(v[int(self._ev(s))])
        if isinstance(n, (ast.Tuple, ast.List)):
            return [self._ev(e) for e in n.elts]
        raise FabError(f"construção não permitida na expressão: {type(n).__name__}")


def _fmt(v):
    """Valor para o relatório: sempre serializável em JSON (o ciclo grava no ledger)."""
    if isinstance(v, np.ndarray):
        if v.size <= 6:
            return _fmt(v.tolist())
        return f"série[{v.size}] min={v.min()} max={v.max()}"
    if isinstance(v, (list, tuple)):
        return [_fmt(x) for x in v]
    v = _num(v)
    if isinstance(v, int) and not isinstance(v, bool) and v.bit_length() > 64:
        return f"<inteiro de {v.bit_length()} bits>"
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    return str(v)


def evaluate_checks(checks: list[dict], mod_trace: dict, base_trace: dict | None) -> list[dict]:
    ev = Evaluator(mod_trace, base_trace)
    results = []
    for c in checks:
        expr = c["expr"]
        rec = {"id": c.get("id", expr[:24]), "expr": expr, "desc": c.get("desc", ""), "weight": c.get("weight", 1)}
        try:
            tree = ast.parse(expr, mode="eval").body
            value = ev.eval(expr)
            passed = bool(np.all(value)) if isinstance(value, np.ndarray) else bool(value)
            rec["passed"] = passed
            if isinstance(tree, ast.Compare):
                rec["lhs"] = _fmt(ev._ev(tree.left))
                rec["rhs"] = _fmt(ev._ev(tree.comparators[-1]))
            else:
                rec["value"] = _fmt(value)
        except FabError as e:
            rec["passed"] = False
            rec["error"] = e.what
        except Exception as e:  # noqa: BLE001 — erro do usuário na expressão
            rec["passed"] = False
            rec["error"] = f"{type(e).__name__}: {e}"
        results.append(rec)
    return results


def score(results: list[dict]) -> float:
    total = sum(r.get("weight", 1) for r in results)
    if not total:
        return 0.0
    return round(sum(r.get("weight", 1) for r in results if r.get("passed")) / total, 4)
