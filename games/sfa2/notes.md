# STREET FIGHTER ALPHA2 (`sfa2`)

> Notas duráveis sobre este jogo. Cada fato leva a evidência (como foi verificado: sonda
> dinâmica, xref do Ghidra, teste no emulador). Nada de dumps de código comercial aqui.
> **Estado, decisões e como continuar: skill `rom-street-fighter-alpha`** (`.agents/rom-street-fighter-alpha/`).
> Prints dos avanços: `games/sfa2/prints/` (ignorada pelo git; índice em `LEIA-ME.txt`).

## Identificação
- Mapa: sdd1 · ROM: 4096 KiB · região: $01 (América do Norte)
- SHA-256 (base limpa): `910a29f834199c63c22beddc749baba746da9922196a553255deade59f4fc127`
- Cabeçalho SMC no original: não
- Chip S-DD1: só os gráficos são comprimidos (DMA com `$4800/$4801`); paletas ficam cruas na ROM.
- Mapa S-DD1: LoROM fixa nos 2 primeiros MiB (`$00-$3F/$80-$BF:8000-FFFF`), janelas HiROM de 1 MiB em
  `$C0-$FF`; o jogo nunca muda `$4804-$4807` (`ev-d1b78376344b`, `ev-33b9df93b71e`). Código roda em
  `$C0:xxxx` com DBR = `$BF`.

## Mapa de RAM (verificado)
| endereço | tam. | significado | evidência |
|---|---|---|---|
| `7E:0500-06FF` | 512 | buffer de paletas → CGRAM `$000-$1FF` (base inferida; trechos `$0600` e `$06C0` conferidos) | dumps de CGRAM × WRAM na luta |
| `7E:06C0-06DF` | 32 | paleta do lutador P1 → CGRAM pal 14 (P2: `$06E0` → pal 15) | `ev-221b88cc802b` |
| `7E:0600-061F` | 32 | paleta do golpe especial do P1 → CGRAM pal 8 (P2: `$0620` → pal 9) | carregador `C0:394B` + dump |
| `7E:07C8` | 1 | cor do uniforme do P1 (0 soco, 1 chute, …); P2 em `$0A48` | diff de WRAM soco × chute + `ev-1883e2cdf5b2` |
| `7E:07A2` | 1 | id do personagem do P1 (P2 em `$0A22`); Ken = 1 | código de seleção/carregador (inferido) |
| `7E:0709` | 2 | X do P1 | `fab ram search` andando →/← (`runs/20261025-002629-ramsearch-sfa2`) |
| `7E:073E` | 1 | vida do P1 (máx. 144); `$0740` = barra que desce animada | `runs/20261025-002810-ramsearch-sfa2` |
| `7E:0989` · `7E:09BE` | 2 · 1 | X · vida do P2 (estrutura do P2 = P1 + `$280`) | **inferido** |

## Rotinas
| endereço | o que faz | M/X à entrada | evidência |
|---|---|---|---|
| `C0:394B-39B1` | paleta do lutador no início do round: cor (`$C8,X`) × 32 + ponteiro `$BF:B6C8[id]` → `$06C0+lado`; paleta especial `$BF:B644[id]` → `$0600+lado` | m8,x16 (no laço) | `ev-dbaa2b8b4bf8` (lê `$DF:0260`) |
| `C0:3A60-3A9D` | copia paletas do bloco do lutador para `$06C0` (`LDA [$10],Y` em `C0:3A8F`, `STA $06C0,X` em `C0:3A91`): durante efeitos (choque, fogo) E como recarga da paleta a cada ~70 f e em transições de ação (parado: f136/207/271; andando 40 f: f40/110) | m8,x16 | `ev-221b88cc802b`, `ev-7d902d01f792`, `ev-d6cb5f0e50b5` |
| `C0:DECA` | seleção: conta socos/chutes apertados (`$AE/$AF`) → cor pela tabela `$C0:DF28` | m8,x8 | leitura estática (inferido) |
| `C0:DF74` | grava a cor do P1 em `$07C8`; em espelho troca pelo par (tabela `$C0:CEBC`: 0↔1, 2↔3, 4↔5) | m8,x8 | `ev-1883e2cdf5b2` |
| `C0:E0F8` | se `$1C41,X ≠ 0`, cor → 4/5 (tabela `$C0:DF2C`) | m8,x8 | leitura estática (gatilho desconhecido) |

## Dados (ROM, sem compressão)
| endereço | o quê | evidência |
|---|---|---|
| `$BF:B6C8` (PC `0x1FB6C8`) | ponteiros de 16 bits por personagem para os blocos de paletas no banco `$DF` | código `C0:3969` + leituras |
| `$DF:0260` = `$BE:8260` (PC `0x1F0260`) | Ken: 16 paletas de 32 B (0-5 cores do uniforme, 6 Hadouken, 7-15 efeitos); gi da cor 0 = cores 9-13 (`$011E $001B $0017 $0013 $0011` em `0x1F0272`); gi da cor 1 = `$5910 $488C $404A $3828 $3006` | `ev-dbaa2b8b4bf8` + CGRAM pal 14 + dump da base limpa |
| PC `0x1F4E60` = `$BE:CE60` | retratos do Ken (6 cores × 32 B); gi = cores 5-8 (`$113E $0C7B $0855 $000F` em `0x1F4E6A`), olhos usam a cor 8 | CGRAM na seleção (BG pal 6) e na tela VS (pal 8) |
| — | rosto, olhos, cabelo e bandana do lutador NÃO usam os tons 9-13 do gi (diff pixel a pixel do mod de cor: 0 px mudam na cabeça) | `runs/cycles/sfa2-ken-gi-azul/cycle-002-luta-soco` × baseline, frame 120 |

## Savestates (`games/sfa2/states/`)
| nome | o que mostra | criado como |
|---|---|---|
| `menu-titulo` | título (chamas), logo antes do menu | power-on + `700;1 Start;200;1 Start;500` |
| `selecao` | PLAYER SELECT, cursor no Ryu | `menu-titulo` + `30;1 Start;60;1 Start;60;1 A;60;1 Start;60;1 B;60;1 Start;300` |
| `luta-ken-rose` | começo da luta Ken (cor 0) × Rose | `selecao` + `10;1 Right;20;1 Right;20;1 Right;20;1 Right;40;1 Y;100;1 Y;100;1 Y;1184` |
| `luta-ken-rose-fight` | logo após o FIGHT! (controle liberado) | `luta-ken-rose` + `430` |
| `luta-ken-chute` | mesma luta com Ken de cor 1 (gi roxo) — regressão | `selecao` + a macro acima com o 1.º `Y` trocado por `B` |
| `luta-ken-chute-fight` | logo após o FIGHT! com o gi roxo | `luta-ken-chute` + `430` |

⚠ Todo savestate carrega a paleta do lutador já resolvida (feita na ROM limpa): ao carregar num mod de
cor, a CGRAM mostra as cores velhas até a rotina `C0:3A8F` recarregar da ROM (primeira transição de
ação ou ~70 frames). Medições de paleta usam `warmup` nos cenários (mod `sfa2-ken-gi-azul`: 40).

## Hijacks usados por mods
| endereço | bytes originais | mod | notas |
|---|---|---|---|
| — | — | `sfa2-ken-gi-azul` | só dados: `$BE:8272` (10 B, gi cor 0) + `$BE:CE6A` (8 B, retrato cor 0); nenhum hijack |

## Perguntas em aberto
- O que liga `$1C41,X` (cores 4/5)? A seleção com 2+ botões dá mesmo as cores 2/3?
- Tela de vitória e final do Ken usam a paleta de retrato `0x1F4E60`?
- X/vida do P2 inferidos — conferir.
- O que dispara a recarga de paleta da rotina `C0:3A8F` a cada ~70 frames (parado)? Só caracterizado
  por observação (`ev-7d902d01f792`/`ev-d6cb5f0e50b5`), sem leitura estática da chamada.
