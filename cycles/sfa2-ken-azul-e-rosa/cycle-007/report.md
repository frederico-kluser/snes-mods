# Ciclo 7 — Ken de gi azul, rosa (Dan) e preta (Akuma), com luvas pretas

- quando: 2026-10-28T14:00:51-03:00 · nota: luvas pretas pelo desenho (14:1,15:13) + base A/B; warmup 230 na luta livre
- objetivo: As três primeiras roupas do Ken ganham novas cores: cor 0 (soco) continua de gi azul royal, cor 1 (chute) passa de roxa para rosa como o do Dan e cor 2 (2+ socos) passa de branca para preta como a do Akuma (tons copiados das paletas deles na ROM), no sprite da luta e nos retratos (seleção e tela VS); e as LUVAS do sprite de luta passam a PRETAS em todas as cores de uniforme (só os píxeis rotulados 'luva' dos tiles mudam de índice 14:1,15:13 — o CABELO continua loiro, intacto). Pele, faixas, efeitos, o gi das cores 3-5 do Ken e os outros personagens ficam iguais e a lógica da luta não muda.
- estado: **ok** · pontuação: **1.0** (anterior: 0.9688) · veredito automático: **evoluiu**

## Build
- ROM: `build/sfa2-ken-azul-e-rosa/sfa2-ken-azul-e-rosa.sfc` · BPS: `build/sfa2-ken-azul-e-rosa/sfa2-ken-azul-e-rosa.bps` (1049182 bytes)
- avisos do Asar: 0
- tamanho das instruções × M/X: 170 conferidas, 0 problema(s)

## Base A/B (variante do próprio mod)
- ROM da base: `build/sfa2-ken-azul-e-rosa/sfa2-ken-azul-e-rosa.off.sfc` · defines: `{'SEM_PINTURA': 1}`
- variante muda só valores? ✅ sim (2640 bytes diferentes)
- por que: mod com código desloca o timing/RNG; contra a ROM limpa a cena descola e os checks alinhados não valem. A variante tem o MESMO código: só a cor muda.
- hijack 80:8487 (5 B, m8,x8, mod.json hijacks[] (m/x verificados)): OK 
  - original: A4 00        LDY $00                ; m8,x8 | 8D 0B 42     STA $420B              ; m8,x8 | 8A           TXA                    ; m8,x8
  - patch:    5C 49 FF A7  JML $A7FF49            ; m8,x8 | EA           NOP                    ; m8,x8
- freespace A7:FF31–A7:FFCF (RATS 151 B, código em A7:FF39)
- freespace A9:FF51–A9:FFCF (RATS 119 B, código em A9:FF59)
- freespace AB:FF2E–AB:FF96 (RATS 97 B, código em AB:FF36)
- dados BE:8272–BE:827B (10 B, declarado em 'data[]'): gi cor 0 do lutador (cores 9-13) — azul royal (ev-dbaa2b8b4bf8)
- dados BE:8292–BE:829B (10 B, declarado em 'data[]'): gi cor 1 do lutador (cores 9-13) — rosa do Dan, id 12, bloco 0x1F1E40 (nome DAN + 7E:07A2=12 na grade)
- dados BE:82B2–BE:82BB (10 B, declarado em 'data[]'): gi cor 2 do lutador (cores 9-13) — preta do Akuma, id 2, bloco 0x1F0460 (nome AKUMA + 7E:07A2=2 na grade)
- dados BE:CE6A–BE:CE71 (8 B, declarado em 'data[]'): retrato cor 0 (cores 5-8) — azul (dump de CGRAM na seleção/VS)
- dados BE:CE8A–BE:CE91 (8 B, declarado em 'data[]'): retrato cor 1 (cores 5-8) — rosa do Dan (rampa sem o realce; simulação de 3 rampas)
- dados BE:CEAA–BE:CEB1 (8 B, declarado em 'data[]'): retrato cor 2 (cores 5-8) — preta do Akuma (rampa do gi COM o realce; simulação)
- dados PC 0x400000–PC 0x40B317 (45848 B, declarado em 'data[]'): tabela + 30 cópia(s) editada(s) do gfx override: área nova da ROM expandida (PC 0x400000+, vazia na base)

## Cenário `luta-soco` — pontuação 1.0
- state: `games/sfa2/states/luta-ken-rose-fight.mss` · baseline: `runs/baselines/sfa2/luta-soco-d2d985572a16b6cd` (cache) · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-luta-soco`
- divergência visual: 140/140 frames (primeira f40, pico 2.093% em f300)
- sincronia mod × variante (WRAM): ✅ em sincronia (só buffers mudam) — f40: 10 B, f320: 10 B, f599: 10 B
- M/X dinâmico no hijack 80:8487 (baseline): 300 execuções, {'m8,x8': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.gi1 != 0x011E) | ((gi1 == 0x7E06) & (gi2 == 0x7102) & (gi3 == 0x60A1) & (gi4 == 0x5060) & (gi5 == 0x4440)))` | ✅ | True | cor 0: onde o original mostra o gi vermelho, o mod mostra os 5 tons azuis |
| `count(baseline.gi1 == 0x011E) >= 0.8 * len(gi1)` | ✅ | 560 vs 448.0 | sanidade: o cenário mostra a cor 0 na maior parte do tempo |
| `all((baseline.gi1 == 0x011E) | (gi1 == baseline.gi1))` | ✅ | True | nas paletas de efeito o mod é igual ao original |
| `all(pele == baseline.pele) and all(cabelo == baseline.cabelo) and all(contorno == baseline.contorno)` | ✅ | True | o resto da paleta do Ken não muda |
| `all(hadouken == baseline.hadouken) and all(rose == baseline.rose)` | ✅ | True | Hadouken e Rose intactos |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ✅ | True | a luta transcorre igual (só muda cor) |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-007/luta-soco/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-007/luta-soco/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-007/luta-soco/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-luta-soco/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-luta-soco/video.mp4`

## Cenário `luta-rosa` — pontuação 1.0
- state: `games/sfa2/states/luta-ken-chute-fight.mss` · baseline: `runs/baselines/sfa2/luta-rosa-aeed715a545258f2` (cache) · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-luta-rosa`
- divergência visual: 140/140 frames (primeira f40, pico 2.093% em f300)
- sincronia mod × variante (WRAM): ✅ em sincronia (só buffers mudam) — f40: 10 B, f320: 10 B, f599: 10 B
- M/X dinâmico no hijack 80:8487 (baseline): 300 execuções, {'m8,x8': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.gi1 != 0x5910) | ((gi1 == 0x6ADC) & (gi2 == 0x521E) & (gi3 == 0x419C) & (gi4 == 0x311A) & (gi5 == 0x2098)))` | ✅ | True | cor 1: onde o original mostra o gi roxo, o mod mostra os 5 tons do Dan |
| `count(baseline.gi1 == 0x5910) >= 0.8 * len(gi1)` | ✅ | 560 vs 448.0 | sanidade: o cenário mostra mesmo a cor 1 |
| `all((baseline.gi1 == 0x5910) | (gi1 == baseline.gi1))` | ✅ | True | nas paletas de efeito o mod é igual ao original |
| `all(pele == baseline.pele) and all(cabelo == baseline.cabelo) and all(contorno == baseline.contorno)` | ✅ | True | o resto da paleta do Ken não muda |
| `all(hadouken == baseline.hadouken) and all(rose == baseline.rose)` | ✅ | True | Hadouken e Rose intactos |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ✅ | True | a luta transcorre igual (só muda cor) |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-007/luta-rosa/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-007/luta-rosa/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-007/luta-rosa/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-luta-rosa/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-luta-rosa/video.mp4`

## Cenário `luta-preta` — pontuação 1.0
- state: `games/sfa2/states/luta-ken-2socos-fight.mss` · baseline: `runs/baselines/sfa2/luta-preta-faee16cd109770ab` (cache) · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-luta-preta`
- divergência visual: 140/140 frames (primeira f40, pico 2.093% em f300)
- sincronia mod × variante (WRAM): ✅ em sincronia (só buffers mudam) — f40: 10 B, f320: 10 B, f599: 10 B
- M/X dinâmico no hijack 80:8487 (baseline): 300 execuções, {'m8,x8': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.gi1 != 0x7BDE) | ((gi1 == 0x2908) & (gi2 == 0x18C6) & (gi3 == 0x14A5) & (gi4 == 0x1084) & (gi5 == 0x1084)))` | ✅ | True | cor 2: onde o original mostra o gi branco, o mod mostra os 5 tons do Akuma |
| `count(baseline.gi1 == 0x7BDE) >= 0.8 * len(gi1)` | ✅ | 560 vs 448.0 | sanidade: o cenário mostra mesmo a cor 2 |
| `all(cabelo == 0x339E)` | ✅ | True | o cabelo do sprite continua loiro: as luvas viram preto pelo DESENHO (índices 1/13), a paleta 14 não é tocada |
| `all((baseline.gi1 == 0x7BDE) | (gi1 == baseline.gi1))` | ✅ | True | nas paletas de efeito o mod é igual ao original |
| `all(pele == baseline.pele) and all(cabelo == baseline.cabelo) and all(contorno == baseline.contorno)` | ✅ | True | o resto da paleta do Ken não muda |
| `all(hadouken == baseline.hadouken) and all(rose == baseline.rose)` | ✅ | True | Hadouken e Rose intactos |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ✅ | True | a luta transcorre igual (só muda cor) |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-007/luta-preta/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-007/luta-preta/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-007/luta-preta/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-luta-preta/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-luta-preta/video.mp4`

## Cenário `luta-livre` — pontuação 1.0
- state: `games/sfa2/states/luta-ken-rose-fight.mss` · baseline: `runs/baselines/sfa2/luta-livre-aa30d7d301215297` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-luta-livre`
- divergência visual: 90/92 frames (primeira f232, pico 1.929% em f308)
- sincronia mod × variante (WRAM): ✅ em sincronia (só buffers mudam) — f230: 10 B, f415: 10 B, f599: 10 B
- M/X dinâmico no hijack 80:8487 (baseline): 300 execuções, {'m8,x8': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.gi1 != 0x011E) | ((gi1 == 0x7E06) & (gi2 == 0x7102) & (gi3 == 0x60A1) & (gi4 == 0x5060) & (gi5 == 0x4440)))` | ✅ | True | cor 0: onde o original mostra o gi vermelho, o mod mostra os 5 tons azuis (inclusive nas poses de dano) |
| `all(pele == baseline.pele) and all(cabelo == baseline.cabelo) and all(contorno == baseline.contorno)` | ✅ | True | o resto da paleta do Ken não muda — o cabelo continua loiro nas poses de queda |
| `all(rose == baseline.rose)` | ✅ | True | Rose intacta |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ✅ | True | a luta transcorre igual (só muda o desenho das luvas) |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-007/luta-livre/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-007/luta-livre/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-007/luta-livre/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-luta-livre/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-luta-livre/video.mp4`

## Cenário `selecao-e-vs` — pontuação 1.0
- state: `games/sfa2/states/selecao.mss` · baseline: `runs/baselines/sfa2/selecao-e-vs-44c59627d0a8a149` (cache) · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-selecao-e-vs`
- divergência visual: 89/110 frames (primeira f10, pico 5.966% em f80)
- sincronia mod × variante (WRAM): ✅ em sincronia (só buffers mudam) — f0: 0 B, f550: 10 B, f1099: 8 B
- M/X dinâmico no hijack 80:8487 (baseline): 165 execuções, {'m8,x8': 165}

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.ret1 != 0x113E) | ((ret1 == 0x7E06) & (ret2 == 0x7102) & (ret3 == 0x5881) & (ret4 == 0x3C20)))` | ✅ | True | retrato da seleção com gi azul |
| `all((baseline.ret1 == 0x113E) | (ret1 == baseline.ret1))` | ✅ | True | Ryu, Adon, Chun-Li e Guy iguais ao original |
| `all((baseline.vs1 != 0x113E) | ((vs1 == 0x7E06) & (vs2 == 0x7102) & (vs3 == 0x5881) & (vs4 == 0x3C20)))` | ✅ | True | retrato da tela VS com gi azul |
| `all((baseline.spr1 != 0x011E) | (spr1 == 0x7E06))` | ✅ | True | o sprite pequeno da seleção também |
| `count(baseline.ret1 == 0x113E) >= 20 and count(baseline.vs1 == 0x113E) >= 20` | ✅ | True | sanidade: o Ken aparece na seleção e na VS |
| `all(retpele == baseline.retpele)` | ✅ | True | a pele do retrato não muda |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-007/selecao-e-vs/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-007/selecao-e-vs/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-007/selecao-e-vs/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-selecao-e-vs/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-selecao-e-vs/video.mp4`

## Cenário `selecao-e-vs-rosa` — pontuação 1.0
- state: `games/sfa2/states/selecao.mss` · baseline: `runs/baselines/sfa2/selecao-e-vs-rosa-5e9e01c4811b8947` (cache) · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-selecao-e-vs-rosa`
- divergência visual: 89/110 frames (primeira f10, pico 5.966% em f80)
- sincronia mod × variante (WRAM): ✅ em sincronia (só buffers mudam) — f0: 0 B, f550: 10 B, f1099: 8 B
- M/X dinâmico no hijack 80:8487 (baseline): 165 execuções, {'m8,x8': 165}

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
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-007/selecao-e-vs-rosa/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-007/selecao-e-vs-rosa/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-007/selecao-e-vs-rosa/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-selecao-e-vs-rosa/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-selecao-e-vs-rosa/video.mp4`

## Cenário `selecao-e-vs-preta` — pontuação 1.0
- state: `games/sfa2/states/selecao.mss` · baseline: `runs/baselines/sfa2/selecao-e-vs-preta-8ce4369f014b5b2e` (cache) · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-selecao-e-vs-preta`
- divergência visual: 89/110 frames (primeira f10, pico 5.966% em f80)
- sincronia mod × variante (WRAM): ✅ em sincronia (só buffers mudam) — f0: 0 B, f550: 10 B, f1099: 8 B
- M/X dinâmico no hijack 80:8487 (baseline): 165 execuções, {'m8,x8': 165}

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.ret1 != 0x7B58) | ((ret1 == 0x2908) & (ret2 == 0x18C6) & (ret3 == 0x14A5) & (ret4 == 0x1084)))` | ✅ | True | retrato da seleção (cor 2) com preto do Akuma |
| `all((baseline.ret1 != 0x113E) | ((ret1 == 0x7E06) & (ret2 == 0x7102) & (ret3 == 0x5881) & (ret4 == 0x3C20)))` | ✅ | True | o preview antes do botão (cor 0) fica azul |
| `all((baseline.vs1 != 0x7B58) | ((vs1 == 0x2908) & (vs2 == 0x18C6) & (vs3 == 0x14A5) & (vs4 == 0x1084)))` | ✅ | True | retrato da tela VS (cor 2) com preto do Akuma |
| `all((baseline.spr1 != 0x7BDE) | (baseline.spr2 != 0x7B58) | ((spr1 == 0x2908) & (spr2 == 0x18C6)))` | ✅ | True | sprite pequeno da seleção (cor 2) — guarda por 2 tons: o branco 0x7BDE é igual ao do Ryu (corrigido no ciclo 2) |
| `all((baseline.ret1 == 0x7B58) | (baseline.ret1 == 0x113E) | (ret1 == baseline.ret1))` | ✅ | True | Ryu, Adon, Chun-Li e Guy iguais ao original |
| `count(baseline.ret1 == 0x7B58) >= 20 and count(baseline.vs1 == 0x7B58) >= 20` | ✅ | True | sanidade: o Ken de cor 2 aparece na seleção e na VS |
| `all(retpele == baseline.retpele)` | ✅ | True | a pele do retrato não muda |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-007/selecao-e-vs-preta/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-007/selecao-e-vs-preta/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-007/selecao-e-vs-preta/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-selecao-e-vs-preta/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-selecao-e-vs-preta/video.mp4`

## Cenário `regressao-verde` — pontuação 1.0
- state: `games/sfa2/states/luta-ken-2chutes-fight.mss` · baseline: `runs/baselines/sfa2/regressao-verde-9bee1b656d31dbd1` (cache) · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-regressao-verde`
- divergência visual: 129/140 frames (primeira f40, pico 0.206% em f256)
- sincronia mod × variante (WRAM): ✅ em sincronia (só buffers mudam) — f40: 0 B, f320: 0 B, f599: 0 B
- M/X dinâmico no hijack 80:8487 (baseline): 300 execuções, {'m8,x8': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `count(baseline.gi1 == 0x39C8) >= 0.8 * len(gi1)` | ✅ | 560 vs 448.0 | sanidade: é mesmo o uniforme verde-escuro (cor 3) |
| `all(gi1 == baseline.gi1) and all(gi2 == baseline.gi2) and all(gi3 == baseline.gi3) and all(gi4 == baseline.gi4) and all(gi5 == baseline.gi5)` | ✅ | True | a paleta verde (cor 3) fica intacta |
| `all(pele == baseline.pele) and all(rose == baseline.rose) and all(hadouken == baseline.hadouken)` | ✅ | True | nada mais muda |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ✅ | True | a luta transcorre igual |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-007/regressao-verde/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-007/regressao-verde/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-007/regressao-verde/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-regressao-verde/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-007-regressao-verde/video.mp4`

## Próximo passo
1. Ver as imagens acima e decidir o veredito visual: `fab cycle verdict mods/sfa2-ken-azul-e-rosa --cycle 7 <evoluiu|regrediu|igual|objetivo-cumprido|inconclusivo> --notes "…"`
2. Se não cumpriu: ajustar `patch.asm` (com evidência nova) e correr outro ciclo.
