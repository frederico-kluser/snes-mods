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
| `$DF:0260` = `$BE:8260` (PC `0x1F0260`) | Ken: 16 paletas de 32 B (0-5 cores do uniforme, 6 Hadouken, 7-15 efeitos); gi da cor 0 = cores 9-13 (`$011E $001B $0017 $0013 $0011` em `0x1F0272`); gi da cor 1 = `$5910 $488C $404A $3828 $3006`; cor 2 = `$7BDE $7B58 $7AD4 $6A50 $518C` (branco); cor 3 = `$39C8 $2946 $2104 $1CE4 $18C2` (verde-escuro) | `ev-dbaa2b8b4bf8` + CGRAM pal 14 + dump da base limpa |
| PC `0x1F4E60` = `$BE:CE60` | retratos do Ken (6 cores × 32 B); gi = cores 5-8 (`$113E $0C7B $0855 $000F` em `0x1F4E6A`), olhos usam a cor 8 | CGRAM na seleção (BG pal 6) e na tela VS (pal 8) |
| `$DF:1E40` (PC `0x1F1E40`) = `$BE:9E40` | **Dan = id 12**: gi = cores 9-13 (`$6ADC $521E $419C $311A $2098`, rosa); retrato dele em `0x1F56A0` usa outros significados nos índices 6-8 (marrons) — para retratos, derivar do ramp do gi | grade de seleção (nome "DAN" + `$7E:07A2=12`) + dump da ROM |
| `$DF:0460` (PC `0x1F0460`) = `$BE:8460` | **Akuma = id 2**: gi = cores 9-13 (`$2908 $18C6 $14A5 $1084 $1084`, preto/ cinza-escuro); retrato dele em `0x1F4F20` tem índices 5-8 avermelhados (cabelo/faixa, não o gi) | grade (nome "AKUMA" + `$7E:07A2=2`) + dump da ROM |
| — | rosto, olhos, cabelo e bandana do lutador NÃO usam os tons 9-13 do gi (diff pixel a pixel do mod de cor: 0 px mudam na cabeça) | `runs/cycles/sfa2-ken-gi-azul/cycle-002-luta-soco` × baseline, frame 120 |
| — | ⚠ tons de gi **coincidem entre personagens**: `$7BDE` = gi do Ryu (cor 0) E da cor 2 do Ken → checks de paleta por um só tom falsificam; guardar por 2+ tons (lição do ciclo 2 do mod azul-e-rosa) | trace `selecao-e-vs-preta` f0-9 (cursor no Ryu) |

## Sprites dos lutadores (2026-10-25, sessão das luvas)
| facto | evidência |
|---|---|
| **Paleta de sprite = índice do OAM + 8 paletas** (Ken OAM 6 → CGRAM 14; Rose OAM 7 → CGRAM 15) | pokes seletivos: `7E:06D2`→gi magenta (só Ken), `7E:05D2`→só cenário, `7E:05E2`→só Rose; dump das 256 cores da CGRAM; OAM × frame |
| CGRAM pal 11 (`$160-$17F`, cores 176-191) fica **toda a zeros** na luta → livre para paleta espelho (sprite pal 3) | dump completo da CGRAM no frame da luta |
| Cada **pose** tem a sua lista de cels `[count][x,y,tile,flags]`; a pose parada alterna entre PC `0x3C49A9` e `0x3C49F2` | sonda exec em `C0:5C8E` (dbr=`$FC`, y=`$49A9`) + leitura da ROM; OAM do frame 24 tem os tiles de `0x3C49F2` |
| Atributo do sprite = `(flags & $C2) ^ $0B`; `$0B` = `$6D` (Ken) e `$2F` (Rose); bits 2-5 das flags são **livres** | desmontagem `C0:5CA4-5CAB` + OAM dump (attrs `$6D`/`$2F`) |
| Tons 14/15 do sprite = **cabelo E luvas** (ouro). A separação é por **CEL**: 217 cels marcados em 28 poses (`marks.asm`; bit 2 das flags, livres no motor) + `GloveTable` de 14 tiles como rede. O nº de tile sozinho é ambíguo entre poses (o mesmo tile é luva numa e cabelo noutra) | poke dos tons 14/15 → magenta nos dois punhos + na cabeça; OAM por frame |
| ⚠ **hooks de código deslocam o RNG da CPU** (a luta joga diferente do frame 1: `x1` 203 vs 201) | `fab run` limpa × mod com os 3 hooks, traces de `7E:0709`/`7E:073E` |


## Grade de seleção (varredura 2026-10-25; `$7E:07A2` = id do personagem sob o cursor)
- Linhas 1-3 (15 posições): Ryu(0), Adon(5), Chun-Li(4), Guy(7), Ken(1) · Dhalsim(15), Gen(17),
  Sakura(13), Rolento(14), Charlie(3)?? · Charlie(3), Birdie(8), Rose(9), ?, Sagat(11)
  ⚠ ordem exata de ids por posição nas linhas 1-2: ver runs de varredura; a 4.ª linha só é
  alcançável pelas colunas 1-2 (o `Down` nas outras colunas dá a volta).
- 4.ª linha (3 posições, só acessível): **Akuma(2), M.Bison(10), Dan(12)** — com wrap horizontal.
- **2+ botões de soco juntos na seleção = cor 2 (gi branco)** e **2+ chutes = cor 3 (gi verde-escuro)**
  — ambos confirmados em jogo (states `luta-ken-2socos` e `luta-ken-2chutes`).

## Savestates (`games/sfa2/states/`)
| nome | o que mostra | criado como |
|---|---|---|
| `menu-titulo` | título (chamas), logo antes do menu | power-on + `700;1 Start;200;1 Start;500` |
| `selecao` | PLAYER SELECT, cursor no Ryu | `menu-titulo` + `30;1 Start;60;1 Start;60;1 A;60;1 Start;60;1 B;60;1 Start;300` |
| `luta-ken-rose` | começo da luta Ken (cor 0) × Rose | `selecao` + `10;1 Right;20;1 Right;20;1 Right;20;1 Right;40;1 Y;100;1 Y;100;1 Y;1184` |
| `luta-ken-rose-fight` | logo após o FIGHT! (controle liberado) | `luta-ken-rose` + `430` |
| `luta-ken-chute` | mesma luta com Ken de cor 1 (gi roxo) — regressão | `selecao` + a macro acima com o 1.º `Y` trocado por `B` |
| `luta-ken-chute-fight` | logo após o FIGHT! com o gi roxo | `luta-ken-chute` + `430` |
| `luta-ken-2socos` | mesma luta com Ken de cor 2 (gi branco) | `selecao` + a macro do `luta-ken-rose` com `Y+X` na seleção |
| `luta-ken-2socos-fight` | logo após o FIGHT! com o gi branco | `luta-ken-2socos` + `430` |
| `luta-ken-2chutes` | mesma luta com Ken de cor 3 (gi verde-escuro) | `selecao` + a macro do `luta-ken-rose` com `B+A` na seleção |
| `luta-ken-2chutes-fight` | logo após o FIGHT! com o gi verde-escuro | `luta-ken-2chutes` + `430` |

⚠ Todo savestate carrega a paleta do lutador já resolvida (feita na ROM limpa): ao carregar num mod de
cor, a CGRAM mostra as cores velhas até a rotina `C0:3A8F` recarregar da ROM (primeira transição de
ação ou ~70 frames). Medições de paleta usam `warmup` nos cenários (mod `sfa2-ken-gi-azul`: 40).

## Hijacks usados por mods
| endereço | bytes originais | mod | notas |
|---|---|---|---|
| — | — | `sfa2-ken-gi-azul` | só dados: `$BE:8272` (10 B, gi cor 0) + `$BE:CE6A` (8 B, retrato cor 0); nenhum hijack |
| — | — | `sfa2-ken-azul-e-rosa` | só dados: cor 0 azul (`$BE:8272` + `$BE:CE6A`), cor 1 rosa do Dan (`$BE:8292` + `$BE:CE8A`) e cor 2 preta do Akuma (`$BE:82B2` + `$BE:CEAA`); nenhum hijack |

## Perguntas em aberto
- O que liga `$1C41,X` (cores 4/5)? ~~2+ botões = cores 2/3?~~ **cor 2 (2+ socos, branco) e cor 3
  (2+ chutes, verde-escuro) confirmadas**.
- Tela de vitória e final do Ken usam a paleta de retrato `0x1F4E60`?
- X/vida do P2 inferidos — conferir.
- O que dispara a recarga de paleta da rotina `C0:3A8F` a cada ~70 frames (parado)? Só caracterizado
  por observação (`ev-7d902d01f792`/`ev-d6cb5f0e50b5`), sem leitura estática da chamada.
