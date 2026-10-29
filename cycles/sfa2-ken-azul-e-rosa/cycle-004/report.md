# Ciclo 4 — Ken de gi azul, rosa (Dan) e preta (Akuma)

- quando: 2026-10-25T15:31:40-03:00 · nota: —
- objetivo: As três primeiras roupas do Ken ganham novas cores: cor 0 (soco) continua de gi azul royal, cor 1 (chute) passa de roxa para rosa como o do Dan e cor 2 (2+ socos) passa de branca para preta como a do Akuma (tons copiados das paletas deles na ROM), no sprite da luta e nos retratos (seleção e tela VS); pele, cabelo, faixas, efeitos, as cores 3-5 do Ken e os outros personagens ficam iguais e a lógica da luta não muda.
- estado: **ok** · pontuação: **0.4461** (anterior: 1.0) · veredito automático: **regrediu**

## Build
- ROM: `build/sfa2-ken-azul-e-rosa/sfa2-ken-azul-e-rosa.sfc` · BPS: `build/sfa2-ken-azul-e-rosa/sfa2-ken-azul-e-rosa.bps` (339 bytes)
- avisos do Asar: 0
- hijack 80:8312 (6 B, m8,x16, mod.json hijacks[] (m/x verificados)): OK 
  - original: A0 00 05     LDY #$0500             ; m8,x16 | 8C 02 43     STY $4302              ; m8,x16 | A0 00 02     LDY #$0200             ; m8,x16
  - patch:    5C 68 FF A7  JML $A7FF68            ; m8,x16 | EA           NOP                    ; m8,x16
- hijack 80:BA9A (4 B, m8,x16, mod.json hijacks[] (m/x verificados)): OK 
  - original: E6 A2        INC $A2                ; m8,x16 | FA           PLX                    ; m8,x16 | 6B           RTL                    ; m8,x16
  - patch:    5C 75 FF A7  JML $A7FF75            ; m8,x16 | 08           PHP                    ; m8,x16
- hijack 80:DCA9 (6 B, m8,x16, mod.json hijacks[] (m/x verificados)): OK 
  - original: 45 0B        EOR $0B                ; m8,x16 | 9F C3 15 00  STA $0015C3,X          ; m8,x16 | E8           INX                    ; m8,x16
  - patch:    5C 7C FF A7  JML $A7FF7C            ; m8,x16 | EA           NOP                    ; m8,x16
- freespace A7:FF31–A7:FFA9 (RATS 113 B, código em A7:FF39)
- dados BE:8272–BE:827B (10 B, declarado em 'data[]'): gi cor 0 do lutador (cores 9-13) — azul royal (ev-dbaa2b8b4bf8)
- dados BE:8292–BE:829B (10 B, declarado em 'data[]'): gi cor 1 do lutador (cores 9-13) — rosa do Dan, id 12, bloco 0x1F1E40 (nome DAN + 7E:07A2=12 na grade)
- dados BE:82B2–BE:82BB (10 B, declarado em 'data[]'): gi cor 2 do lutador (cores 9-13) — preta do Akuma, id 2, bloco 0x1F0460 (nome AKUMA + 7E:07A2=2 na grade)
- dados BE:CE6A–BE:CE71 (8 B, declarado em 'data[]'): retrato cor 0 (cores 5-8) — azul (dump de CGRAM na seleção/VS)
- dados BE:CE8A–BE:CE91 (8 B, declarado em 'data[]'): retrato cor 1 (cores 5-8) — rosa do Dan (rampa sem o realce; simulação de 3 rampas)
- dados BE:CEAA–BE:CEB1 (8 B, declarado em 'data[]'): retrato cor 2 (cores 5-8) — preta do Akuma (rampa do gi COM o realce; simulação)

## Cenário `luta-soco` — pontuação 0.4286
- state: `games/sfa2/states/luta-ken-rose-fight.mss` · baseline: `runs/baselines/sfa2/luta-soco-f94113050f5a3fec` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-luta-soco`
- divergência visual: 140/140 frames (primeira f40, pico 68.363% em f544)
- M/X dinâmico no hijack 80:8312 (baseline): 300 execuções, {'m8,x16': 300}
- M/X dinâmico no hijack 80:BA9A (baseline): 31 execuções, {'m8,x16': 31}
- M/X dinâmico no hijack 80:DCA9 (baseline): 300 execuções, {'m8,x16': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.gi1 != 0x011E) | ((gi1 == 0x7E06) & (gi2 == 0x7102) & (gi3 == 0x60A1) & (gi4 == 0x5060) & (gi5 == 0x4440)))` | ❌ | False | cor 0: onde o original mostra o gi vermelho, o mod mostra os 5 tons azuis |
| `count(baseline.gi1 == 0x011E) >= 0.8 * len(gi1)` | ✅ | 560 vs 448.0 | sanidade: o cenário mostra a cor 0 na maior parte do tempo |
| `all((baseline.gi1 == 0x011E) | (gi1 == baseline.gi1))` | ✅ | True | nas paletas de efeito o mod é igual ao original |
| `all(esp14 == 0x339E) and all(esp15 == 0x029C) and all(esp1 == gi1)` | ❌ | False | cor 0 (azul): o espelho é cópia fiel — as luvas continuam LOIRAS, só a roupa preta perde o ouro |
| `all(pele == baseline.pele) and all(cabelo == baseline.cabelo) and all(contorno == baseline.contorno)` | ❌ | False | o resto da paleta do Ken não muda |
| `all(hadouken == baseline.hadouken) and all(rose == baseline.rose)` | ✅ | True | Hadouken e Rose intactos |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ❌ | False | a luta transcorre igual (só muda cor) |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-004/luta-soco/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-004/luta-soco/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-004/luta-soco/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-luta-soco/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-luta-soco/video.mp4`

## Cenário `luta-rosa` — pontuação 0.5
- state: `games/sfa2/states/luta-ken-chute-fight.mss` · baseline: `runs/baselines/sfa2/luta-rosa-0c34dbbbcb988d71` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-luta-rosa`
- divergência visual: 140/140 frames (primeira f40, pico 68.363% em f544)
- M/X dinâmico no hijack 80:8312 (baseline): 300 execuções, {'m8,x16': 300}
- M/X dinâmico no hijack 80:BA9A (baseline): 31 execuções, {'m8,x16': 31}
- M/X dinâmico no hijack 80:DCA9 (baseline): 300 execuções, {'m8,x16': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.gi1 != 0x5910) | ((gi1 == 0x6ADC) & (gi2 == 0x521E) & (gi3 == 0x419C) & (gi4 == 0x311A) & (gi5 == 0x2098)))` | ❌ | False | cor 1: onde o original mostra o gi roxo, o mod mostra os 5 tons do Dan |
| `count(baseline.gi1 == 0x5910) >= 0.8 * len(gi1)` | ✅ | 560 vs 448.0 | sanidade: o cenário mostra mesmo a cor 1 |
| `all((baseline.gi1 == 0x5910) | (gi1 == baseline.gi1))` | ✅ | True | nas paletas de efeito o mod é igual ao original |
| `all(pele == baseline.pele) and all(cabelo == baseline.cabelo) and all(contorno == baseline.contorno)` | ❌ | False | o resto da paleta do Ken não muda |
| `all(hadouken == baseline.hadouken) and all(rose == baseline.rose)` | ✅ | True | Hadouken e Rose intactos |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ❌ | False | a luta transcorre igual (só muda cor) |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-004/luta-rosa/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-004/luta-rosa/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-004/luta-rosa/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-luta-rosa/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-luta-rosa/video.mp4`

## Cenário `luta-preta` — pontuação 0.4444
- state: `games/sfa2/states/luta-ken-2socos-fight.mss` · baseline: `runs/baselines/sfa2/luta-preta-343fb8c5c6f72052` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-luta-preta`
- divergência visual: 140/140 frames (primeira f40, pico 68.312% em f544)
- M/X dinâmico no hijack 80:8312 (baseline): 300 execuções, {'m8,x16': 300}
- M/X dinâmico no hijack 80:BA9A (baseline): 31 execuções, {'m8,x16': 31}
- M/X dinâmico no hijack 80:DCA9 (baseline): 300 execuções, {'m8,x16': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.gi1 != 0x7BDE) | ((gi1 == 0x2908) & (gi2 == 0x18C6) & (gi3 == 0x14A5) & (gi4 == 0x1084) & (gi5 == 0x1084)))` | ❌ | False | cor 2: onde o original mostra o gi branco, o mod mostra os 5 tons do Akuma |
| `count(baseline.gi1 == 0x7BDE) >= 0.8 * len(gi1)` | ✅ | 560 vs 448.0 | sanidade: o cenário mostra mesmo a cor 2 |
| `all(esp1 == gi1) and all(esp2 == gi2) and all(esp3 == gi3) and all(esp4 == gi4) and all(esp5 == gi5)` | ❌ | False | o espelho (pal 11) é cópia fiel da paleta do Ken: pele/manga/contorno não mudam por construção |
| `all(esp14 == 0x2908) and all(esp15 == 0x1084)` | ✅ | True | na roupa preta os tons 14/15 do espelho são a rampa PRETA de 2 tons (realce 2908 + sombra 1084) — sombreado preservado, não tom único |
| `all(cabelo == 0x339E)` | ❌ | False | o cabelo do sprite continua loiro: a paleta real (pal 14) não é tocada |
| `all((baseline.gi1 == 0x7BDE) | (gi1 == baseline.gi1))` | ✅ | True | nas paletas de efeito o mod é igual ao original |
| `all(pele == baseline.pele) and all(cabelo == baseline.cabelo) and all(contorno == baseline.contorno)` | ❌ | False | o resto da paleta do Ken não muda |
| `all(hadouken == baseline.hadouken) and all(rose == baseline.rose)` | ✅ | True | Hadouken e Rose intactos |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ❌ | False | a luta transcorre igual (só muda cor) |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-004/luta-preta/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-004/luta-preta/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-004/luta-preta/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-luta-preta/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-luta-preta/video.mp4`

## Cenário `selecao-e-vs` — pontuação 0.5
- state: `games/sfa2/states/selecao.mss` · baseline: `runs/baselines/sfa2/selecao-e-vs-ffe98bbf210fb787` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-selecao-e-vs`
- divergência visual: 102/110 frames (primeira f0, pico 79.729% em f970)
- M/X dinâmico no hijack 80:8312 (baseline): 300 execuções, {'m8,x16': 300}
- M/X dinâmico no hijack 80:BA9A (baseline): 9 execuções, {'m8,x16': 9}
- M/X dinâmico no hijack 80:DCA9 (baseline): 300 execuções, {'m8,x16': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.ret1 != 0x113E) | ((ret1 == 0x7E06) & (ret2 == 0x7102) & (ret3 == 0x5881) & (ret4 == 0x3C20)))` | ✅ | True | retrato da seleção com gi azul |
| `all((baseline.ret1 == 0x113E) | (ret1 == baseline.ret1))` | ❌ | False | Ryu, Adon, Chun-Li e Guy iguais ao original |
| `all((baseline.vs1 != 0x113E) | ((vs1 == 0x7E06) & (vs2 == 0x7102) & (vs3 == 0x5881) & (vs4 == 0x3C20)))` | ❌ | False | retrato da tela VS com gi azul |
| `all((baseline.spr1 != 0x011E) | (spr1 == 0x7E06))` | ✅ | True | o sprite pequeno da seleção também |
| `count(baseline.ret1 == 0x113E) >= 20 and count(baseline.vs1 == 0x113E) >= 20` | ✅ | True | sanidade: o Ken aparece na seleção e na VS |
| `all(retpele == baseline.retpele)` | ❌ | False | a pele do retrato não muda |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-004/selecao-e-vs/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-004/selecao-e-vs/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-004/selecao-e-vs/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-selecao-e-vs/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-selecao-e-vs/video.mp4`

## Cenário `selecao-e-vs-rosa` — pontuação 0.5714
- state: `games/sfa2/states/selecao.mss` · baseline: `runs/baselines/sfa2/selecao-e-vs-rosa-02fbfbfaed17e50d` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-selecao-e-vs-rosa`
- divergência visual: 102/110 frames (primeira f0, pico 79.729% em f970)
- M/X dinâmico no hijack 80:8312 (baseline): 300 execuções, {'m8,x16': 300}
- M/X dinâmico no hijack 80:BA9A (baseline): 9 execuções, {'m8,x16': 9}
- M/X dinâmico no hijack 80:DCA9 (baseline): 300 execuções, {'m8,x16': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.ret1 != 0x6952) | ((ret1 == 0x521E) & (ret2 == 0x419C) & (ret3 == 0x311A) & (ret4 == 0x2098)))` | ✅ | True | retrato da seleção (cor 1) com rosa do Dan |
| `all((baseline.ret1 != 0x113E) | ((ret1 == 0x7E06) & (ret2 == 0x7102) & (ret3 == 0x5881) & (ret4 == 0x3C20)))` | ✅ | True | o preview antes do botão (cor 0) fica azul |
| `all((baseline.vs1 != 0x6952) | ((vs1 == 0x521E) & (vs2 == 0x419C) & (vs3 == 0x311A) & (vs4 == 0x2098)))` | ❌ | False | retrato da tela VS (cor 1) com rosa do Dan |
| `all((baseline.spr1 != 0x5910) | (spr1 == 0x6ADC))` | ✅ | True | o sprite pequeno da seleção (cor 1) também |
| `all((baseline.ret1 == 0x6952) | (baseline.ret1 == 0x113E) | (ret1 == baseline.ret1))` | ❌ | False | Ryu, Adon, Chun-Li e Guy iguais ao original |
| `count(baseline.ret1 == 0x6952) >= 20 and count(baseline.vs1 == 0x6952) >= 20` | ✅ | True | sanidade: o Ken de cor 1 aparece na seleção e na VS |
| `all(retpele == baseline.retpele)` | ❌ | False | a pele do retrato não muda |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-004/selecao-e-vs-rosa/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-004/selecao-e-vs-rosa/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-004/selecao-e-vs-rosa/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-selecao-e-vs-rosa/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-selecao-e-vs-rosa/video.mp4`

## Cenário `selecao-e-vs-preta` — pontuação 0.4286
- state: `games/sfa2/states/selecao.mss` · baseline: `runs/baselines/sfa2/selecao-e-vs-preta-205e9ccd30e14379` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-selecao-e-vs-preta`
- divergência visual: 102/110 frames (primeira f0, pico 79.715% em f960)
- M/X dinâmico no hijack 80:8312 (baseline): 300 execuções, {'m8,x16': 300}
- M/X dinâmico no hijack 80:BA9A (baseline): 9 execuções, {'m8,x16': 9}
- M/X dinâmico no hijack 80:DCA9 (baseline): 300 execuções, {'m8,x16': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `all((baseline.ret1 != 0x7B58) | ((ret1 == 0x2908) & (ret2 == 0x18C6) & (ret3 == 0x14A5) & (ret4 == 0x1084)))` | ✅ | True | retrato da seleção (cor 2) com preto do Akuma |
| `all((baseline.ret1 != 0x113E) | ((ret1 == 0x7E06) & (ret2 == 0x7102) & (ret3 == 0x5881) & (ret4 == 0x3C20)))` | ✅ | True | o preview antes do botão (cor 0) fica azul |
| `all((baseline.vs1 != 0x7B58) | ((vs1 == 0x2908) & (vs2 == 0x18C6) & (vs3 == 0x14A5) & (vs4 == 0x1084)))` | ❌ | False | retrato da tela VS (cor 2) com preto do Akuma |
| `all((baseline.spr1 != 0x7BDE) | (baseline.spr2 != 0x7B58) | ((spr1 == 0x2908) & (spr2 == 0x18C6)))` | ❌ | False | sprite pequeno da seleção (cor 2) — guarda por 2 tons: o branco 0x7BDE é igual ao do Ryu (corrigido no ciclo 2) |
| `all((baseline.ret1 == 0x7B58) | (baseline.ret1 == 0x113E) | (ret1 == baseline.ret1))` | ❌ | False | Ryu, Adon, Chun-Li e Guy iguais ao original |
| `count(baseline.ret1 == 0x7B58) >= 20 and count(baseline.vs1 == 0x7B58) >= 20` | ✅ | True | sanidade: o Ken de cor 2 aparece na seleção e na VS |
| `all(retpele == baseline.retpele)` | ❌ | False | a pele do retrato não muda |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-004/selecao-e-vs-preta/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-004/selecao-e-vs-preta/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-004/selecao-e-vs-preta/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-selecao-e-vs-preta/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-selecao-e-vs-preta/video.mp4`

## Cenário `regressao-verde` — pontuação 0.25
- state: `games/sfa2/states/luta-ken-2chutes-fight.mss` · baseline: `runs/baselines/sfa2/regressao-verde-03d9fd4d446f1e33` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-regressao-verde`
- divergência visual: 140/140 frames (primeira f40, pico 68.352% em f544)
- M/X dinâmico no hijack 80:8312 (baseline): 300 execuções, {'m8,x16': 300}
- M/X dinâmico no hijack 80:BA9A (baseline): 31 execuções, {'m8,x16': 31}
- M/X dinâmico no hijack 80:DCA9 (baseline): 300 execuções, {'m8,x16': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `count(baseline.gi1 == 0x39C8) >= 0.8 * len(gi1)` | ✅ | 560 vs 448.0 | sanidade: é mesmo o uniforme verde-escuro (cor 3) |
| `all(gi1 == baseline.gi1) and all(gi2 == baseline.gi2) and all(gi3 == baseline.gi3) and all(gi4 == baseline.gi4) and all(gi5 == baseline.gi5)` | ❌ | False | a paleta verde (cor 3) fica intacta |
| `all(pele == baseline.pele) and all(rose == baseline.rose) and all(hadouken == baseline.hadouken)` | ❌ | False | nada mais muda |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ❌ | False | a luta transcorre igual |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-004/regressao-verde/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-004/regressao-verde/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-004/regressao-verde/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-regressao-verde/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-004-regressao-verde/video.mp4`

## Próximo passo
1. Ver as imagens acima e decidir o veredito visual: `fab cycle verdict mods/sfa2-ken-azul-e-rosa --cycle 4 <evoluiu|regrediu|igual|objetivo-cumprido|inconclusivo> --notes "…"`
2. Se não cumpriu: ajustar `patch.asm` (com evidência nova) e correr outro ciclo.
