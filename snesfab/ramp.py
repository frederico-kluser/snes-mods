"""Rampas de cor que preservam o SOMBREADO (a regra da skill pixel-peep, em código).

Trocar a cor de uma peça de sprite é trocar uma RAMPA (realce → sombra), não um tom. Este módulo
gera candidatas a partir da rampa original e de uma cor-alvo, no espaço OKLab (perceptual):
- o brilho relativo de cada tom é mantido (o realce continua mais claro, a sombra mais escura);
- matiz/saturação vêm da cor-alvo;
- rampas escuras (preto, azul-marinho) são comprimidas acima do CONTORNO, para a peça não derreter
  na linha de contorno;
e confere cada candidata: ordem de brilho, tons distintos, contraste entre vizinhos, distância ao
contorno. Tudo em BGR555 (o formato da CGRAM).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .ppu import bgr555_to_rgb, fmt_color, parse_color

# nomes comuns → cor-alvo (BGR555 via #rrggbb); o agente pode sempre passar um #hex
NAMED = {
    "preto": "#202024", "black": "#202024", "branco": "#f0f0f0", "white": "#f0f0f0", "cinza": "#808088",
    "gray": "#808088", "grey": "#808088", "vermelho": "#d02020", "red": "#d02020", "azul": "#2040e0",
    "blue": "#2040e0", "azul-royal": "#2848f0", "azul-marinho": "#182868", "navy": "#182868", "azul-claro": "#58a8f8",
    "ciano": "#20c8d8", "cyan": "#20c8d8", "verde": "#20a030", "green": "#20a030", "verde-escuro": "#185020",
    "amarelo": "#f0d020", "yellow": "#f0d020", "dourado": "#d8a020", "gold": "#d8a020", "laranja": "#f07818",
    "orange": "#f07818", "roxo": "#7830c0", "purple": "#7830c0", "violeta": "#9050e0", "rosa": "#f070b0",
    "pink": "#f070b0", "magenta": "#e020c0", "marrom": "#704020", "brown": "#704020", "bege": "#d8c090",
}


def parse_target(text: str) -> int:
    t = str(text).strip().lower()
    if t in NAMED:
        return parse_color(NAMED[t])
    return parse_color(text)


# ── OKLab (Björn Ottosson) ───────────────────────────────────────────────────────

def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def rgb_to_oklab(rgb) -> tuple[float, float, float]:
    r, g, b = (_lin(v / 255) for v in rgb)
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def oklab_to_linear(L: float, a: float, b: float) -> tuple[float, float, float]:
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
            -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
            -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)


def oklch_to_bgr555(L: float, C: float, h: float) -> int:
    """OKLCh → BGR555, reduzindo o croma até caber no gamut sRGB."""
    L = min(max(L, 0.0), 1.0)
    for _ in range(40):
        lin = oklab_to_linear(L, C * math.cos(h), C * math.sin(h))
        if all(-1e-4 <= v <= 1 + 1e-4 for v in lin):
            break
        C *= 0.9
    rgb = [min(max(_gam(min(max(v, 0.0), 1.0)), 0.0), 1.0) for v in lin]
    r5, g5, b5 = (min(31, max(0, round(v * 31))) for v in rgb)
    return r5 | (g5 << 5) | (b5 << 10)


def lch(value: int) -> tuple[float, float, float]:
    L, a, b = rgb_to_oklab(bgr555_to_rgb(value))
    return L, math.hypot(a, b), math.atan2(b, a)


# ── candidatas ─────────────────────────────────────────────────────────────────

@dataclass
class Ramp:
    name: str
    colors: list[int]
    why: str
    checks: list[str] = field(default_factory=list)
    ok: bool = True

    def to_dict(self) -> dict:
        return {"nome": self.name, "cores": [fmt_color(c) for c in self.colors], "por_que": self.why,
                "conferencias": self.checks, "ok": self.ok}


def check_ramp(orig: list[int], new: list[int], outline: list[int] | None = None, min_dl: float = 0.025) -> tuple[bool, list[str]]:
    """Confere se a rampa nova preserva o sombreado da original."""
    msgs, ok = [], True
    Lo = [lch(c)[0] for c in orig]
    Ln = [lch(c)[0] for c in new]
    order_o = sorted(range(len(orig)), key=lambda i: Lo[i])
    bad_order = [(i, j) for a, i in enumerate(order_o) for j in order_o[a + 1:] if Lo[j] - Lo[i] > 0.01 and Ln[j] <= Ln[i]]
    if bad_order:
        ok = False
        msgs.append(f"✗ ordem de brilho invertida em {len(bad_order)} par(es) (o realce tem de continuar mais claro)")
    else:
        msgs.append("✓ ordem de brilho preservada")
    # tons distintos: só conta como erro se eram distintos na original
    collide = [(i, j) for i in range(len(new)) for j in range(i + 1, len(new)) if new[i] == new[j] and orig[i] != orig[j]]
    if collide:
        ok = False
        msgs.append(f"✗ {len(collide)} par(es) de tons que eram diferentes viraram IGUAIS (achata a peça)")
    else:
        msgs.append("✓ tons distintos")
    srt = sorted(Ln)
    gaps = [b - a for a, b in zip(srt, srt[1:])]
    if gaps and min(gaps) < min_dl and len(set(orig)) == len(orig):
        msgs.append(f"⚠ dois tons vizinhos quase iguais (ΔL={min(gaps):.3f}); a 1x podem parecer um só")
    else:
        msgs.append("✓ contraste entre vizinhos")
    if outline:
        Lc = max(lch(c)[0] for c in outline)
        darkest = min(Ln)
        if any(c in outline for c in new):
            ok = False
            msgs.append("✗ um tom é IGUAL ao contorno (a peça derrete na linha de contorno)")
        elif darkest - Lc < 0.04:
            msgs.append(f"⚠ a sombra está colada ao contorno (ΔL={darkest - Lc:.3f}); prefira uma rampa mais clara")
        else:
            msgs.append("✓ sombra acima do contorno")
    return ok, msgs


def make_ramps(orig: list[int], target: int, outline: list[int] | None = None, weights: list[int] | None = None) -> list[Ramp]:
    """Candidatas a partir da rampa original e de uma cor-alvo (a âncora vira a cor-alvo, os outros tons
    mantêm a distância de brilho relativa a ela)."""
    L0 = [lch(c) for c in orig]
    Lt, Ct, ht = lch(target)
    n = len(orig)
    if weights and len(weights) == n and sum(weights) > 0:
        anchor = max(range(n), key=lambda i: weights[i])
    else:
        anchor = sorted(range(n), key=lambda i: L0[i][0])[n // 2]
    La, Ca = L0[anchor][0], max(L0[anchor][1], 1e-3)
    floor = (max(lch(c)[0] for c in outline) + 0.06) if outline else 0.08
    out = []
    variants = [("A · fiel", 1.0, 0.0, "mesmas distâncias de brilho da original, matiz da cor-alvo"),
                ("B · mais contraste", 1.3, 0.0, "distâncias 30% maiores: volume mais marcado"),
                ("C · mais suave", 0.75, 0.0, "distâncias 25% menores: tecido mais liso"),
                ("D · artística", 1.1, 0.35, "sombras puxam para azul/roxo e realces para amarelo (como pintor)")]
    for name, s, shift, why in variants:
        Ls = [Lt + (L0[i][0] - La) * s for i in range(n)]
        lo, hi = min(Ls), max(Ls)
        if lo < floor:                      # rampa escura: comprime acima do contorno
            span = max(hi - lo, 1e-6)
            top = max(hi, floor + span * 0.6)
            Ls = [floor + (v - lo) / span * (top - floor) for v in Ls]
        if max(Ls) > 0.97:
            over = max(Ls) - 0.97
            Ls = [v - over for v in Ls]
        cols = []
        for i in range(n):
            C = Ct * min(2.0, max(0.3, L0[i][1] / Ca)) if Ca > 0.02 else Ct
            h = ht + shift * (La - L0[i][0])     # mais escuro → gira para o azul; mais claro → para o amarelo
            cols.append(oklch_to_bgr555(Ls[i], C, h))
        cols = _separate(cols, orig)
        ok, msgs = check_ramp(orig, cols, outline)
        out.append(Ramp(name, cols, why, msgs, ok))
    return out


def _separate(cols: list[int], orig: list[int]) -> list[int]:
    """Desfaz colisões criadas pela quantização para 5 bits (dois tons diferentes que caíram no mesmo valor)."""
    cols = list(cols)
    for _ in range(4):
        changed = False
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                if cols[i] == cols[j] and orig[i] != orig[j]:
                    k = j if lch(orig[j])[0] < lch(orig[i])[0] else i   # escurece o que era mais escuro
                    v = cols[k]
                    r, g, b = v & 31, (v >> 5) & 31, (v >> 10) & 31
                    cols[k] = max(r - 1, 0) | (max(g - 1, 0) << 5) | (max(b - 1, 0) << 10)
                    if cols[k] == v:                                    # já era preto: clareia o outro
                        o = i if k == j else j
                        w = cols[o]
                        cols[o] = min((w & 31) + 1, 31) | (min(((w >> 5) & 31) + 1, 31) << 5) | (min(((w >> 10) & 31) + 1, 31) << 10)
                    changed = True
        if not changed:
            break
    return cols


def explicit_ramp(orig: list[int], colors: list[int], name: str, why: str, outline: list[int] | None = None) -> Ramp:
    ok, msgs = check_ramp(orig, colors, outline)
    return Ramp(name, list(colors), why, msgs, ok)
