# Ciclo 1 — Ken de gi azul e rosa (Dan)

- quando: 2026-10-25T02:37:09-03:00 · nota: ciclo 1: cor 1 (BE:8292 lutador + BE:CE8A retrato) de roxa para rosa do Dan (id 12, tons 6ADC 521E 419C 311A 2098; retrato 521E 419C 311A 2098); cor 0 continua azul; regressao cor 2 branca
- objetivo: A cor 0 do Ken continua de gi azul royal e a cor 1 (escolhida com chute) passa de roxa para rosa como o do Dan (cores copiadas da paleta dele na ROM), no sprite da luta e nos retratos (seleção e tela VS); pele, cabelo, faixas, efeitos, as cores 2-5 do Ken e os outros personagens ficam iguais e a lógica da luta não muda.
- estado: **ok** · pontuação: **1.0** (anterior: None) · veredito automático: **primeiro**

## Build
- ROM: `build/sfa2-ken-azul-e-rosa/sfa2-ken-azul-e-rosa.sfc` · BPS: `build/sfa2-ken-azul-e-rosa/sfa2-ken-azul-e-rosa.bps` (163 bytes)
- avisos do Asar: 0
- dados BE:8272–BE:827B (10 B, declarado em 'data[]'): gi cor 0 do lutador (cores 9-13) — azul royal (ev-dbaa2b8b4bf8)
- dados BE:8292–BE:829B (10 B, declarado em 'data[]'): gi cor 1 do lutador (cores 9-13) — rosa do Dan, id 12, bloco 0x1F1E40 (nome DAN + 7E:07A2=12 na grade)
- dados BE:CE6A–BE:CE71 (8 B, declarado em 'data[]'): retrato cor 0 (cores 5-8) — azul (dump de CGRAM na seleção/VS)
- dados BE:CE8A–BE:CE91 (8 B, declarado em 'data[]'): retrato cor 1 (cores 5-8) — rosa do Dan (rampa sem o realce; simulação de 3 rampas)

## Cenário `luta-soco` — pontuação 1.0
- state: `games/sfa2/states/luta-ken-rose-fight.mss` · baseline: `runs/baselines/sfa2/luta-soco-f0f2e9b3e626a2bd` (cache) · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-001-luta-soco`
- divergência visual: 139/140 frames (primeira f44, pico 1.908% em f300)

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.gi1 != 0x011E) | ((gi1 == 0x7E06) & (gi2 == 0x7102) & (gi3 == 0x60A1) & (gi4 == 0x5060) & (gi5 == 0x4440)))` | ✅ | True | cor 0: onde o original mostra o gi vermelho, o mod mostra os 5 tons azuis |
| `count(baseline.gi1 == 0x011E) >= 0.8 * len(gi1)` | ✅ | 560 vs 448.0 | sanidade: o cenário mostra a cor 0 na maior parte do tempo |
| `all((baseline.gi1 == 0x011E) | (gi1 == baseline.gi1))` | ✅ | True | nas paletas de efeito o mod é igual ao original |
| `all(pele == baseline.pele) and all(cabelo == baseline.cabelo) and all(contorno == baseline.contorno)` | ✅ | True | o resto da paleta do Ken não muda |
| `all(hadouken == baseline.hadouken) and all(rose == baseline.rose)` | ✅ | True | Hadouken e Rose intactos |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ✅ | True | a luta transcorre igual (só muda cor) |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-001/luta-soco/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-001/luta-soco/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-001/luta-soco/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-001-luta-soco/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-001-luta-soco/video.mp4`

## Cenário `luta-rosa` — pontuação 1.0
- state: `games/sfa2/states/luta-ken-chute-fight.mss` · baseline: `runs/baselines/sfa2/luta-rosa-02880959176e9369` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-001-luta-rosa`
- divergência visual: 139/140 frames (primeira f44, pico 1.908% em f300)

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.gi1 != 0x5910) | ((gi1 == 0x6ADC) & (gi2 == 0x521E) & (gi3 == 0x419C) & (gi4 == 0x311A) & (gi5 == 0x2098)))` | ✅ | True | cor 1: onde o original mostra o gi roxo, o mod mostra os 5 tons do Dan |
| `count(baseline.gi1 == 0x5910) >= 0.8 * len(gi1)` | ✅ | 560 vs 448.0 | sanidade: o cenário mostra mesmo a cor 1 |
| `all((baseline.gi1 == 0x5910) | (gi1 == baseline.gi1))` | ✅ | True | nas paletas de efeito o mod é igual ao original |
| `all(pele == baseline.pele) and all(cabelo == baseline.cabelo) and all(contorno == baseline.contorno)` | ✅ | True | o resto da paleta do Ken não muda |
| `all(hadouken == baseline.hadouken) and all(rose == baseline.rose)` | ✅ | True | Hadouken e Rose intactos |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ✅ | True | a luta transcorre igual (só muda cor) |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-001/luta-rosa/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-001/luta-rosa/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-001/luta-rosa/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-001-luta-rosa/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-001-luta-rosa/video.mp4`

## Cenário `selecao-e-vs` — pontuação 1.0
- state: `games/sfa2/states/selecao.mss` · baseline: `runs/baselines/sfa2/selecao-e-vs-772fe8929a721d3e` (cache) · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-001-selecao-e-vs`
- divergência visual: 88/110 frames (primeira f80, pico 5.824% em f80)

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.ret1 != 0x113E) | ((ret1 == 0x7E06) & (ret2 == 0x7102) & (ret3 == 0x5881) & (ret4 == 0x3C20)))` | ✅ | True | retrato da seleção com gi azul |
| `all((baseline.ret1 == 0x113E) | (ret1 == baseline.ret1))` | ✅ | True | Ryu, Adon, Chun-Li e Guy iguais ao original |
| `all((baseline.vs1 != 0x113E) | ((vs1 == 0x7E06) & (vs2 == 0x7102) & (vs3 == 0x5881) & (vs4 == 0x3C20)))` | ✅ | True | retrato da tela VS com gi azul |
| `all((baseline.spr1 != 0x011E) | (spr1 == 0x7E06))` | ✅ | True | o sprite pequeno da seleção também |
| `count(baseline.ret1 == 0x113E) >= 20 and count(baseline.vs1 == 0x113E) >= 20` | ✅ | True | sanidade: o Ken aparece na seleção e na VS |
| `all(retpele == baseline.retpele)` | ✅ | True | a pele do retrato não muda |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-001/selecao-e-vs/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-001/selecao-e-vs/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-001/selecao-e-vs/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-001-selecao-e-vs/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-001-selecao-e-vs/video.mp4`

## Cenário `selecao-e-vs-rosa` — pontuação 1.0
- state: `games/sfa2/states/selecao.mss` · baseline: `runs/baselines/sfa2/selecao-e-vs-rosa-8d805d31399a1640` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-001-selecao-e-vs-rosa`
- divergência visual: 88/110 frames (primeira f80, pico 5.824% em f80)

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.ret1 != 0x6952) | ((ret1 == 0x521E) & (ret2 == 0x419C) & (ret3 == 0x311A) & (ret4 == 0x2098)))` | ✅ | True | retrato da seleção (cor 1) com rosa do Dan |
| `all((baseline.ret1 != 0x113E) | ((ret1 == 0x7E06) & (ret2 == 0x7102) & (ret3 == 0x5881) & (ret4 == 0x3C20)))` | ✅ | True | o preview antes do botão (cor 0) fica azul |
| `all((baseline.vs1 != 0x6952) | ((vs1 == 0x521E) & (vs2 == 0x419C) & (vs3 == 0x311A) & (vs4 == 0x2098)))` | ✅ | True | retrato da tela VS (cor 1) com rosa do Dan |
| `all((baseline.spr1 != 0x5910) | (spr1 == 0x6ADC))` | ✅ | True | o sprite pequeno da seleção (cor 1) também |
| `all((baseline.ret1 == 0x6952) | (baseline.ret1 == 0x113E) | (ret1 == baseline.ret1))` | ✅ | True | Ryu, Adon, Chun-Li e Guy iguais ao original |
| `count(baseline.ret1 == 0x6952) >= 20 and count(baseline.vs1 == 0x6952) >= 20` | ✅ | True | sanidade: o Ken de cor 1 aparece na seleção e na VS |
| `all(retpele == baseline.retpele)` | ✅ | True | a pele do retrato não muda |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-001/selecao-e-vs-rosa/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-001/selecao-e-vs-rosa/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-001/selecao-e-vs-rosa/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-001-selecao-e-vs-rosa/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-001-selecao-e-vs-rosa/video.mp4`

## Cenário `regressao-branco` — pontuação 1.0
- state: `games/sfa2/states/luta-ken-2socos-fight.mss` · baseline: `runs/baselines/sfa2/regressao-branco-d3c12b39ab793d81` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-001-regressao-branco`
- divergência visual: 0/140 frames (primeira fNone, pico 0.0% em f40)

| check | resultado | valores | descrição |
|---|---|---|---|
| `count(baseline.gi1 == 0x7BDE) >= 0.8 * len(gi1)` | ✅ | 560 vs 448.0 | sanidade: é mesmo o uniforme branco (cor 2) |
| `all(gi1 == baseline.gi1) and all(gi2 == baseline.gi2) and all(gi3 == baseline.gi3) and all(gi4 == baseline.gi4) and all(gi5 == baseline.gi5)` | ✅ | True | a paleta branca (cor 2) fica intacta |
| `all(pele == baseline.pele) and all(rose == baseline.rose) and all(hadouken == baseline.hadouken)` | ✅ | True | nada mais muda |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ✅ | True | a luta transcorre igual |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-001/regressao-branco/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-001/regressao-branco/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-001/regressao-branco/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-001-regressao-branco/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-001-regressao-branco/video.mp4`

## Próximo passo
1. Ver as imagens acima e decidir o veredito visual: `fab cycle verdict mods/sfa2-ken-azul-e-rosa --cycle 1 <evoluiu|regrediu|igual|objetivo-cumprido|inconclusivo> --notes "…"`
2. Se não cumpriu: ajustar `patch.asm` (com evidência nova) e correr outro ciclo.
