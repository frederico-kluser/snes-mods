# Ciclo 2 — Ken de gi azul

- quando: 2026-10-25T01:21:01-03:00 · nota: ciclo 2: patch igual; medicao da luta com warmup 40 (state traz paleta velha da ROM limpa; C0:3A8F recarrega em f40, ev-d6cb5f0e50b5/ev-7d902d01f792)
- objetivo: O uniforme padrão do Ken (cor 0, escolhida com soco) passa de gi vermelho a gi azul royal na luta, no sprite e no retrato da seleção e na tela VS; pele, cabelo, faixa, efeitos, a cor de chute (roxa) e os outros personagens ficam iguais e a lógica da luta não muda.
- estado: **ok** · pontuação: **1.0** (anterior: 0.9444) · veredito automático: **evoluiu**

## Build
- ROM: `build/sfa2-ken-gi-azul/sfa2-ken-gi-azul.sfc` · BPS: `build/sfa2-ken-gi-azul/sfa2-ken-gi-azul.bps` (137 bytes)
- avisos do Asar: 0
- dados BE:8272–BE:827B (10 B, declarado em 'data[]'): paleta do lutador Ken cor 0, cores 9-13 (ev-dbaa2b8b4bf8)
- dados BE:CE6A–BE:CE71 (8 B, declarado em 'data[]'): paleta do retrato do Ken cor 0, cores 5-8 (dump de CGRAM na seleção/VS)

## Cenário `luta-soco` — pontuação 1.0
- state: `games/sfa2/states/luta-ken-rose-fight.mss` · baseline: `runs/baselines/sfa2/luta-soco-f0f2e9b3e626a2bd` · mod: `runs/cycles/sfa2-ken-gi-azul/cycle-002-luta-soco`
- divergência visual: 139/140 frames (primeira f44, pico 1.908% em f300)

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.gi1 != 0x011E) | ((gi1 == 0x7E06) & (gi2 == 0x7102) & (gi3 == 0x60A1) & (gi4 == 0x5060) & (gi5 == 0x4440)))` | ✅ | True | sempre que a ROM original mostra o gi vermelho, o mod mostra os 5 tons azuis |
| `count(baseline.gi1 == 0x011E) >= 0.8 * len(gi1)` | ✅ | 560 vs 448.0 | sanidade: o cenário mostra o uniforme normal na maior parte do tempo |
| `all((baseline.gi1 == 0x011E) | (gi1 == baseline.gi1))` | ✅ | True | nas paletas de efeito (choque, fogo) o mod é igual ao original |
| `all(pele == baseline.pele) and all(cabelo == baseline.cabelo) and all(contorno == baseline.contorno)` | ✅ | True | o resto da paleta do Ken não muda |
| `all(hadouken == baseline.hadouken) and all(rose == baseline.rose)` | ✅ | True | Hadouken e Rose intactos |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ✅ | True | a luta transcorre igual (só muda cor) |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-gi-azul/cycle-002/luta-soco/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-gi-azul/cycle-002/luta-soco/trace_compare.png`
- divergência: `cycles/sfa2-ken-gi-azul/cycle-002/luta-soco/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-gi-azul/cycle-002-luta-soco/sheet.png` · vídeo: `runs/cycles/sfa2-ken-gi-azul/cycle-002-luta-soco/video.mp4`

## Cenário `selecao-e-vs` — pontuação 1.0
- state: `games/sfa2/states/selecao.mss` · baseline: `runs/baselines/sfa2/selecao-e-vs-772fe8929a721d3e` (cache) · mod: `runs/cycles/sfa2-ken-gi-azul/cycle-002-selecao-e-vs`
- divergência visual: 88/110 frames (primeira f80, pico 5.824% em f80)

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.ret1 != 0x113E) | ((ret1 == 0x7E06) & (ret2 == 0x7102) & (ret3 == 0x5881) & (ret4 == 0x3C20)))` | ✅ | True | retrato da seleção com gi azul |
| `all((baseline.ret1 == 0x113E) | (ret1 == baseline.ret1))` | ✅ | True | Ryu, Adon, Chun-Li e Guy iguais ao original |
| `all((baseline.vs1 != 0x113E) | ((vs1 == 0x7E06) & (vs2 == 0x7102) & (vs3 == 0x5881) & (vs4 == 0x3C20)))` | ✅ | True | retrato da tela VS com gi azul |
| `all((baseline.spr1 != 0x011E) | (spr1 == 0x7E06))` | ✅ | True | o sprite pequeno da seleção também |
| `count(baseline.ret1 == 0x113E) >= 20 and count(baseline.vs1 == 0x113E) >= 20` | ✅ | True | sanidade: o Ken aparece na seleção e na VS (ajuste os números ao 1.º baseline) |
| `all(retpele == baseline.retpele)` | ✅ | True | a pele do retrato não muda |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-gi-azul/cycle-002/selecao-e-vs/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-gi-azul/cycle-002/selecao-e-vs/trace_compare.png`
- divergência: `cycles/sfa2-ken-gi-azul/cycle-002/selecao-e-vs/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-gi-azul/cycle-002-selecao-e-vs/sheet.png` · vídeo: `runs/cycles/sfa2-ken-gi-azul/cycle-002-selecao-e-vs/video.mp4`

## Cenário `regressao-chute` — pontuação 1.0
- state: `games/sfa2/states/luta-ken-chute-fight.mss` · baseline: `runs/baselines/sfa2/regressao-chute-6f8ae9c7d0d2c25d` (cache) · mod: `runs/cycles/sfa2-ken-gi-azul/cycle-002-regressao-chute`
- divergência visual: 0/150 frames (primeira fNone, pico 0.0% em f0)

| check | resultado | valores | descrição |
|---|---|---|---|
| `count(baseline.gi1 == 0x5910) >= 0.8 * len(gi1)` | ✅ | 600 vs 480.0 | sanidade: é mesmo o uniforme roxo (cor 1) |
| `all(gi1 == baseline.gi1) and all(gi2 == baseline.gi2) and all(gi3 == baseline.gi3) and all(gi4 == baseline.gi4) and all(gi5 == baseline.gi5)` | ✅ | True | a paleta roxa (vizinha na ROM) fica intacta |
| `all(pele == baseline.pele) and all(rose == baseline.rose) and all(hadouken == baseline.hadouken)` | ✅ | True | nada mais muda |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ✅ | True | a luta transcorre igual |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-gi-azul/cycle-002/regressao-chute/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-gi-azul/cycle-002/regressao-chute/trace_compare.png`
- divergência: `cycles/sfa2-ken-gi-azul/cycle-002/regressao-chute/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-gi-azul/cycle-002-regressao-chute/sheet.png` · vídeo: `runs/cycles/sfa2-ken-gi-azul/cycle-002-regressao-chute/video.mp4`

## Próximo passo
1. Ver as imagens acima e decidir o veredito visual: `fab cycle verdict mods/sfa2-ken-gi-azul --cycle 2 <evoluiu|regrediu|igual|objetivo-cumprido|inconclusivo> --notes "…"`
2. Se não cumpriu: ajustar `patch.asm` (com evidência nova) e correr outro ciclo.
