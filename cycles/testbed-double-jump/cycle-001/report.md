# Ciclo 1 — Pulo duplo (patch do guia REA/Asar)

- quando: 2026-10-24T18:49:34-03:00 · nota: patch do guia, literal (capturas alinhadas)
- objetivo: Permitir um segundo pulo no ar (B outra vez durante o voo), uma só vez por voo, sem alterar o pulo simples.
- estado: **ok** · pontuação: **1.0** (anterior: None) · veredito automático: **primeiro**

## Build
- ROM: `build/testbed-double-jump/testbed-double-jump.sfc` · BPS: `build/testbed-double-jump/testbed-double-jump.bps` (165 bytes)
- avisos do Asar: 0
- hijack 80:A420 (4 B, m8,x16, mod.json hijacks[]): OK 
  - original: A5 72        LDA $72                ; m8,x16 | D0 14        BNE $A438              ; m8,x16 | A5 16        LDA $16                ; m8,x16
  - patch:    5C 08 80 90  JML $908008            ; m8,x16 | A5 16        LDA $16                ; m8,x16
- freespace 90:8000–90:802F (RATS 40 B, código em 90:8008)

## Cenário `pulo-duplo` — pontuação 1.0
- state: `games/testbed/states/parado.mss` · baseline: `runs/baselines/testbed/pulo-duplo-066853562145b6fa` · mod: `runs/cycles/testbed-double-jump/cycle-001-pulo-duplo`
- divergência visual: 31/70 frames (primeira f40, pico 0.893% em f44)
- M/X dinâmico no hijack 80:A420 (baseline): 140 execuções, {'m8,x16': 140}

| check | resultado | valores | descrição |
|---|---|---|---|
| `min(y) < baseline.min(y) - 320` | ✅ | 1294 vs 1725 | o ápice sobe pelo menos 20 px a mais que o pulo original |
| `count(edges(vy < -60)) >= 2` | ✅ | 2 vs 2 | há dois impulsos de subida no mesmo voo |
| `count(edges(baseline.vy < -60)) == 1` | ✅ | 1 vs 1 | sanidade: o original só dá um impulso |
| `last(air) == 0` | ✅ | 0 vs 0 | aterra antes do fim do cenário (sem softlock) |
| `max(dj) == 1 and last(dj) == 0` | ✅ | True | a flag de salto duplo é usada e reiniciada no chão |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/testbed-double-jump/cycle-001/pulo-duplo/compare.png`
- RAM mod × baseline: `cycles/testbed-double-jump/cycle-001/pulo-duplo/trace_compare.png`
- divergência: `cycles/testbed-double-jump/cycle-001/pulo-duplo/divergence.png`
- folha do mod: `runs/cycles/testbed-double-jump/cycle-001-pulo-duplo/sheet.png` · vídeo: `runs/cycles/testbed-double-jump/cycle-001-pulo-duplo/video.mp4`

## Cenário `pulo-simples` — pontuação 1.0
- state: `games/testbed/states/parado.mss` · baseline: `runs/baselines/testbed/pulo-simples-d2815540c7d54476` · mod: `runs/cycles/testbed-double-jump/cycle-001-pulo-simples`
- divergência visual: 0/35 frames (primeira fNone, pico 0.0% em f0)
- M/X dinâmico no hijack 80:A420 (baseline): 140 execuções, {'m8,x16': 140}

| check | resultado | valores | descrição |
|---|---|---|---|
| `all(y == baseline.y) and all(x == baseline.x)` | ✅ | True | o pulo simples não muda |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/testbed-double-jump/cycle-001/pulo-simples/compare.png`
- RAM mod × baseline: `cycles/testbed-double-jump/cycle-001/pulo-simples/trace_compare.png`
- divergência: `cycles/testbed-double-jump/cycle-001/pulo-simples/divergence.png`
- folha do mod: `runs/cycles/testbed-double-jump/cycle-001-pulo-simples/sheet.png` · vídeo: `runs/cycles/testbed-double-jump/cycle-001-pulo-simples/video.mp4`

## Próximo passo
1. Ver as imagens acima e decidir o veredito visual: `fab cycle verdict mods/testbed-double-jump --cycle 1 <evoluiu|regrediu|igual|objetivo-cumprido|inconclusivo> --notes "…"`
2. Se não cumpriu: ajustar `patch.asm` (com evidência nova) e correr outro ciclo.
