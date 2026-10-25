---
name: rom-street-fighter-alpha
description: Skill do jogo Street Fighter Alpha 2 (USA, SNES, chip S-DD1; id `sfa2` na fábrica) — tudo o que já se descobriu (mapa S-DD1, sistema de paletas dos lutadores e retratos, RAM dos jogadores, rotinas, savestates e como recriá-los), o estado do mod "roupa do Ken" e o passo a passo para continuar. Use SEMPRE que o pedido mencionar Street Fighter Alpha 2, SFA2, `sfa2`, Ken, Rose, roupa/gi/cor/paleta de lutador desse jogo, ou "continua o mod do Ken". É o modelo do padrão "uma skill por jogo" da fábrica.
---

# Street Fighter Alpha 2 (`sfa2`) — skill do jogo

> **Padrão da fábrica: cada jogo analisado tem a sua skill `rom-<jogo>`** — esta é a do SFA2. É o diário
> vivo do jogo: o que se sabe (com evidência), o que se decidiu, em que pé está cada mod e **como
> continuar**. Aponta para a memória CoALA (fatos duráveis) e para a pasta de prints do jogo. Modelo e
> regras para os próximos jogos: `.agents/snes-mod-factory/references/skill-de-jogo.md`.
> Fluxo geral: skills `snes-mod-factory` → `snes-mod-cycle`, protocolo 65816 em `snes-rea-modder`.

## Comece por aqui (toda sessão)
1. `./fab doctor --quick` (Git Bash; no PowerShell `.\fab.ps1 doctor --quick`).
2. Memória: `python .agents/snes-mods-coala-agent-skill/scripts/coala.py recall "sfa2 street fighter alpha 2 ken paleta gi" --budget 1500`
   — chaves desta skill: `sfa2-paletas`, `sfa2-recarga-paleta`, `sdd1-mapa`, `skill-por-jogo`
   (`coala.py get <chave>`).
3. Leia **Estado** e **Como continuar** abaixo e `games/sfa2/notes.md` (tabelas de RAM/rotinas/states).
4. **Pasta de prints `games/sfa2/prints/`** (ignorada pelo git: frames de jogo comercial). Garanta que
   existe (`mkdir -p`), comece lendo o `LEIA-ME.txt` e, a cada avanço ou teste, salve um print com o
   próximo número (`NN-descricao.png`) e uma linha no índice. O usuário acompanha o trabalho por ela.
5. Clone novo, sem ROM/states? `fab rom add <sfa2.sfc> --id sfa2` (o usuário tem um `.zip`: extraia o
   `.sfc` numa pasta vazia própria antes) e recrie os states pela tabela **Savestates**.

## Identificação
- Arquivo do usuário: `Street Fighter Alpha 2 (USA).zip` → `Street Fighter Alpha 2 (USA).sfc`, 4 194 304 B,
  CRC32 `9c59ddff`, SHA-1 `f4ede150b5281f7f5d7e3188c6d9163c2bc66475`,
  SHA-256 `910a29f834199c63c22beddc749baba746da9922196a553255deade59f4fc127` (sem cabeçalho SMC).
- Cabeçalho `STREET FIGHTER ALPHA2`, código `AUZE`, mapa `$32` (LoROM + S-DD1, FastROM), chipset `$43`
  (ROM + S-DD1), 4 MiB, região `$01` (América do Norte), checksum `$DB9A` válido. Reset `$00:FF90`.
- **S-DD1 = descompressão de gráficos no DMA.** Paletas NÃO são comprimidas (lidas pela CPU) → mudar
  cores é patch de dados simples; mudar o *desenho* da roupa exigiria descomprimir/recomprimir S-DD1.
- O MesenCE 2.2.1 emula o S-DD1 corretamente (intro, menus e lutas renderizam; print 01).

## Mapa S-DD1 (armadilha — já corrigida no `snesfab/rom.py`)
- `$00-$3F/$80-$BF:8000-FFFF` = LoROM **fixa só dos 2 primeiros MiB**; `$C0-$FF` = janelas HiROM de
  1 MiB escolhidas por `$4804-$4807` (padrão 0/1/2/3). `$40-$7D` não mapeiam ROM.
- O SFA2 **não troca** as janelas: nenhuma escrita em `$4804-$4807` do power-on à luta
  (`ev-021fd69dbc74`, `ev-d1b78376344b`, `ev-33b9df93b71e`, `ev-6f5e50e992d4`); só `$4800`/`$4801` = 1.
- O jogo executa em `$C0:xxxx` com **DBR = `$BF`**: `STA $4801` cai em `$BF:4801`. Sondas de MMIO têm de
  olhar o banco `$BF` (`fab probe … BF:4800`), porque o `fab probe` só cobre `$00/$80` + espelho.
- Asar: `lorom` endereça certo os 2 primeiros MiB (`$BE:8260` = PC `0x1F0260`); código em `$C0+` que for
  montado precisa de `base` com o endereço real.

## Como chegar a cada momento (savestates em `games/sfa2/states/`, ignorados)
| state | origem + macro | mostra |
|---|---|---|
| `menu-titulo` | power-on + `700;1 Start;200;1 Start;500` (1402 f) | título (chamas), logo antes do menu |
| `selecao` | `menu-titulo` + `30;1 Start;60;1 Start;60;1 A;60;1 Start;60;1 B;60;1 Start;300` (636 f) | PLAYER SELECT, cursor 1P no Ryu |
| `luta-ken-rose` | `selecao` + `10;1 Right;20;1 Right;20;1 Right;20;1 Right;40;1 Y;100;1 Y;100;1 Y;1184` (1501 f) | começo da luta Arcade: Ken (cor 0, MANUAL, speed normal) × Rose, Itália |
| `luta-ken-rose-fight` | `luta-ken-rose` + `430` | logo depois do FIGHT!, controle liberado |
| `luta-ken-chute` | `selecao` + a macro do `luta-ken-rose` com o 1.º `Y` trocado por `B` (1501 f) | mesma luta com Ken de cor 1 (gi roxo) |
| `luta-ken-chute-fight` | `luta-ken-chute` + `430` | logo depois do FIGHT! com o gi roxo |
| `luta-ken-2socos` | `selecao` + a macro do `luta-ken-rose` com `Y+X` na seleção (1501 f) | mesma luta com Ken de cor 2 (gi branco) |
| `luta-ken-2socos-fight` | `luta-ken-2socos` + `430` | logo depois do FIGHT! com o gi branco |

Comando: `./fab state boot sfa2 <nome> [--from-state <origem>] --macro "<macro>" --note "…"` e abra a
`preview_sheet`. Grade da seleção, 1.ª linha: Ryu, Adon, Chun-Li, Guy, **Ken** (4× →). Depois do botão:
MANUAL/AUTO (Y = MANUAL) → SPEED (Y = normal) → mapa → "KEN VS ROSE" (~f990-1110) → luta (~f1410).
No `luta-ken-rose`, parado: ROUND 1 ~f90-150, FIGHT! ~f180-390, a Rose acerta um Soul Spark ~f567
(o Ken fica azul/elétrico até ~f638 — paletas de efeito, não do uniforme).

## Fatos verificados (dinâmico primeiro)
**Cor do uniforme (seleção).** 1 soco (Y/X/L) = cor 0, gi vermelho; 1 chute (B/A/R) = cor 1, gi roxo
(prints 10, 13). **2+ socos juntos = cor 2 (gi branco) — CONFIRMADO em jogo** (state `luta-ken-2socos`,
macro com `1 Y+X`; print do state). **2+ chutes juntos = cor 3 (gi verde-escuro) — CONFIRMADO em jogo**
(state `luta-ken-2chutes`, macro com `1 B+A`). Cores 4/5
(laranja / roxo-escuro) vêm de outro caminho (`C0:E0F8`, quando `$1C41,X ≠ 0`, tabela `$C0:DF2C`) —
gatilho desconhecido. A rotina `C0:DF74` grava a cor do P1 em `$7E:07C8`
(`ev-1883e2cdf5b2`) e, em espelho (mesmo personagem e mesma cor), troca pelo par (tabela `$C0:CEBC`:
0↔1, 2↔3, 4↔5).

**Grade de seleção e personagens.** `$7E:07A2` = id do personagem sob o cursor (varredura 2026-10-25).
Linhas 1-3 = 15 posições: Ryu(0), Adon(5), Chun-Li(4), Guy(7), Ken(1) | Dhalsim(15), Gen(17), Sakura(13),
Rolento(14), ?(16) | Charlie(3), Birdie(8), Rose(9), ?(6), Sagat(11). **4.ª linha (3 posições, oculta):
Akuma(2), M.Bison(10), Dan(12)** — só alcançável pelas colunas 1-2 (o `Down` noutras colunas dá a volta;
wrap horizontal na linha). **Dan = id 12**: gi rosa `$6ADC $521E $419C $311A $2098` (bloco `$DF:1E40`);
o retrato dele (`0x1F56A0`) usa outros significados nos índices 6-8 (marrons) — para retratos de outros
personagens, derivar do ramp do gi (simulação print 28).

**Paletas dos lutadores (ROM, sem compressão).** Tabela de ponteiros `$BF:B6C8` (PC `0x1FB6C8`), 16 bits
por personagem (índice = id do personagem), para o banco `$DF` (janela HiROM → PC `0x1F0000 + ptr`).
Cada lutador tem 16 paletas de 32 B: 0-5 = as 6 cores do uniforme, 6 = paleta do golpe especial (Ken:
Hadouken; vem pela segunda tabela `$BF:B644`), 7-15 = efeitos (fogo, choque, flashes).
Ryu = id 0 (`0x0060`), **Ken = id 1 (`0x0260`)**, Rose = id 9 (`0x1580`, confirmada na CGRAM).
- Ken cor 0: `$DF:0260` = PC `0x1F0260` = `$BE:8260`. Índices: 1 contorno/faixa, 2-8 pele/branco,
  **9-13 = gi** (`$011E $001B $0017 $0013 $0011`, do mais claro ao mais escuro), 14-15 cabelo.
  O recolor dos índices 9-13 cobre blusa, mangas e calça e deixa a faixa preta intacta (print 11).
  Rosto, olhos, cabelo e bandana **não** usam 9-13: no diff pixel a pixel do mod de cor, 0 px mudam na
  cabeça (print 24). Cor 1 (chute): `$5910 $488C $404A $3828 $3006` em `0x1F0292`.
- Quem lê (`ev-dbaa2b8b4bf8`, seleção → luta): carregador do início do round `C0:394B-39B1` (laço em
  `C0:3982`: cor = `$C8,X` × 32 + ponteiro → `$06C0+lado`; depois 32 B da paleta especial → `$0600+lado`;
  m8,x16), cópia de efeitos/recarga `C0:3A60-3A9D` (`LDA [$10],Y` em `C0:3A8F` → `STA $06C0,X` em
  `C0:3A91`, m8,x16 — `ev-221b88cc802b`) e a tela de seleção (leitura com PC seguinte `C0:DFCC`, todo
  frame, m16,x16).
- **Recarga da paleta em plena luta** (`ev-7d902d01f792` parado: f136/207/271; `ev-d6cb5f0e50b5` andando:
  f40/110): a rotina `C0:3A8F` relê o bloco do lutador na ROM e regrava `$06C0` — a cada ~70 f e em
  transições de ação. Consequência: **o savestate traz a paleta já resolvida da ROM limpa** e um mod de
  cor só aparece na CGRAM após a 1.ª recarga; os cenários de paleta usam `warmup` (ex.: 40 em
  `sfa2-ken-gi-azul`). O gatilho do ciclo de ~70 f não está mapeado (pergunta em aberto).

**Retratos (ROM, sem compressão).** Ken em PC `0x1F4E60` (= `$BE:CE60`), 6 paletas de 32 B na mesma ordem
das cores; Ryu em `0x1F4DA0` (passo de `0xC0` por personagem). Cor 0: **índices 5-8 = gi**
(`$113E $0C7B $0855 $000F`); 1-4 cabelo/munhequeira, 9-14 pele, 15 contorno. ⚠ Os **olhos** do retrato
usam o índice 8 (`$000F`) — trocar esse tom muda a cor dos olhos (print 15). No mod de gi azul a cor 8
virou `$3C20` (opção A) e os olhos continuam legíveis (print 23). A mesma paleta serve a
seleção (BG pal 6) e a tela VS (sprite pal 0) (dumps de CGRAM, print 14).

**WRAM / CGRAM.**
| endereço | tam. | significado | evidência |
|---|---|---|---|
| `7E:0500-06FF` | 512 | buffer de paletas espelhando a CGRAM `$000-$1FF` (base inferida; `$06C0`↔CGRAM `$1C0` e `$0600`↔`$100` conferidos) | dump de CGRAM × WRAM na luta |
| `7E:06C0-06DF` | 32 | paleta do lutador P1 (P2 em `$06E0`) → CGRAM pal 14 (P2: pal 15) | `ev-221b88cc802b` + dump |
| `7E:0600-061F` | 32 | paleta do golpe especial do P1 (P2 em `$0620`) → CGRAM pal 8 (P2: pal 9) | código do carregador + dump |
| `7E:07C8` | 1 | cor do P1 (0 soco, 1 chute…); P2 em `$0A48` | diff de WRAM soco × chute (único byte de lógica diferente) + `ev-1883e2cdf5b2` |
| `7E:07A2` | 1 | id do personagem do P1 (P2 em `$0A22`) | código `C0:DF85` e carregador (inferido) |
| `7E:0709` | 2 | X do P1 (201 → 306 andando 60 f para a frente, → 219 voltando) | `runs/20261025-002629-ramsearch-sfa2` |
| `7E:073E` | 1 | vida do P1 (máx. 144; caiu 144 → 130 em dois golpes); `$0740` = barra animada | `runs/20261025-002810-ramsearch-sfa2` |
| `7E:0989` / `7E:09BE` | 2 / 1 | X / vida do P2 (= P1 + `$280`) | **inferido — conferir** |

CGRAM: luta → pal 8 = especial do P1, pal 9 = especial do P2, **pal 14 (`$1C0-$1DF`) = Ken**, pal 15 =
Rose; tons do gi do Ken = cores 233-237 = bytes `$1D2,$1D4,$1D6,$1D8,$1DA`. Seleção → BG pal 6
(`$0C0`) = retrato grande, pal 14 = sprite pequeno. Tela VS → pal 8 (`$100`) = retrato do P1, pal 9 = P2.

## Estado (2026-10-25, fim do dia) — mods do Ken: **PRONTOS (objetivo-cumprido)**
- **Pedido 1:** "modificar as roupas do Ken" → mod **`sfa2-ken-gi-azul`** PRONTO (ciclo 2,
  `objetivo-cumprido`): cor 0 de gi vermelho a **azul royal** no sprite, retrato, sprite da seleção, mapa
  e VS; pele, cabelo, bandana, faixa preta, efeitos, cor de chute e os outros personagens intactos.
  BPS `build/sfa2-ken-gi-azul/` (137 B), 2 regiões de dados, 0 hijacks. Prints 17-24.
- **Pedido 2:** "rosa que nem o do Dan, em outra roupa dele" → mod **`sfa2-ken-azul-e-rosa`** PRONTO
  (ciclo 1, `objetivo-cumprido`, 29/29 checks): cor 0 **continua azul** e a cor 1 (chute) passou de roxa
  a **rosa como o do Dan** (cópia fiel dos tons do gi dele: `$6ADC $521E $419C $311A $2098`; retrato
  `$521E $419C $311A $2098`), luta + retratos + VS. Regressão na cor 2 (branco, 2 socos): 0 divergências.
  BPS `build/sfa2-ken-azul-e-rosa/` (163 B), 4 regiões de dados, 0 hijacks. Prints 25-29.
  ⚠ Os BPS não empilham (ambos nascem da ROM limpa): para ter as duas cores, use o `azul-e-rosa`.
- **Pedido 3:** "na terceira roupa do Ken preta, igual do Akuma" → o mesmo mod **`sfa2-ken-azul-e-rosa`**
  foi estendido e ficou PRONTO (ciclo 3, `objetivo-cumprido`, 42/42 checks): cor 2 (2+ socos) passou de
  branca a **preta como a do Akuma** (cópia fiel dos tons do gi dele: `$2908 $18C6 $14A5 $1084 $1084`;
  retrato `$2908 $18C6 $14A5 $1084` — com o realce, para o tecido não achatar). Regressão movida para a
  cor 3 (verde-escuro, 2 chutes): 0 divergências. BPS 185 B, 6 regiões de dados. Prints 30-33.
  ⚠ Lição do ciclo 2: o tom `$7BDE` (cor 2 do Ken) é igual ao gi do Ryu — checks de paleta guardam por
  2+ tons (o check `sprite-preta` foi corrigido no ciclo 3, sem enfraquecer).
- **Mod:** `mods/sfa2-ken-gi-azul/` (patch.asm só de dados; `mod.json` com `data[]`, 3 cenários, 16 checks).
  Build: `build/sfa2-ken-gi-azul/sfa2-ken-gi-azul.bps` (137 B), 2 regiões de dados (`$BE:8272` 10 B +
  `$BE:CE6A` 8 B), 0 hijacks, 0 avisos. Ciclo 2 = 16/16 checks ✅ + veredito visual `objetivo-cumprido`
  (regressão roxa com **0 frames divergentes**). Tons novos: `!gi_0..!gi_4 = $7E06 $7102 $60A1 $5060 $4440`;
  retrato `dw $7E06, $7102, $5881, $3C20` (cor 8 = olhos, **opção A `$3C20`** — conferida no print 23).
- **Decisões:** azul royal por contraste (não colide com o roxo da cor 1); cores 1-5, efeitos e os outros
  personagens intocados; retrato coerente com o sprite.
- **Ferramentas novas nesta sessão** (branch `feat/sfa2-roupa-ken`, **sem commit**): `mod.json → "data"`
  em `snesfab/build.py` (regiões de dados com evidência, fora de `hijacks`; testes
  `tests/test_unit.py::DataRegionTests`) e **`warmup`** de medição (`snesfab/emu.py`, `lua/harness.lua`,
  `fab run --warmup`, `mod.json → scenarios[].warmup`; testes `JobTests` e
  `tests/test_e2e.py::test_warmup_starts_measurement_late`).

## LUVAS PRETAS na roupa preta (cor 2) — mecanismo aprovado, EM CURSO (2026-10-25, sessão 2)

**Pedido do dono:** "na roupa preta quero SÓ as luvas do Ken pretas; o cabelo loiro fica" +
"analise na mudança de cores para mantermos o sombreado, não ficar mono cor" (→ skill `pixel-peep`).

**Fatos novos (todos medidos):**
- **A paleta de sprite é `p+8`**: o OAM diz paleta 6/7 (Ken/Rose) mas o render lê CGRAM 14/15.
  Medido: Ken (OAM 6) lê CGRAM `$1C0-$1DF` (pal 14 = bloco `0x1F0260+2*32` da ROM); Rose (OAM 7) lê
  `$1E0` (pal 15). Logo **sprite pal 3 → CGRAM 11 (`$160-$17F`)**, que o jogo deixa **toda a zeros**
  na luta → é a nossa **paleta espelho**. Evidência: pokes seletivos (`7E:06D2` → gi magenta,
  `7E:05D2` → só cenário) + dump das 256 cores da CGRAM + OAM dump × frame.
- **Cada pose tem a sua lista de cels** `[count][x,y,tile,flags]`; o Ken parado alterna entre
  PC `0x3C49A9` e `0x3C49F2`. Ponteiro em `$18,X`, banco em `$F5,X` (sonda em `C0:5C8E`: dbr=`$FC`
  p/ Ken, `$FF` p/ Rose). Motor `C0:5C60-5CE2`: attr = `(flags & $C2) ^ $0B`, bits 2-5 das flags livres.
- **O ouro (tons 14/15) é do cabelo E das luvas** — não há tom que separe; a separação é por TILE.
  Nas duas poses paradas os punhos são os tiles **`$0C`/`$0E`**; em poses de punho erguido o punho cai
  num tile do grupo da cabeça (`$2E`…) → **cobertura por tile é parcial** (lacuna conhecida).
- **Sombreado**: rampa de 2 tons para a luva (realce `$2908` + sombra `$1084`, os do gi preto), nunca
  preto único; contorno `$0842` fica de fora. Simulação em `games/sfa2/prints/34-luvas-rampas-sombreado.png`.

**Implementado em `mods/sfa2-ken-azul-e-rosa/patch.asm`** (3 hijacks, todos m8/x16 verificados no build;
121 B de freecode em `A7:FF31`; 0 avisos):
1. `C0:0312` (antes do DMA da CGRAM): copia `$06C0-$06DF` → `$0660-$067F` todo VBlank; **só se
   `7E:07C8 == 2`** sobrescreve os tons 14/15 com `$2908`/`$1084`. Outras cores = cópia fiel → luvas loiras.
2. `C0:5CA9`: se a paleta base é 6 (P1) **e** o tile final (`$0015C2,X`) é `$0C`/`$0E` → `attr ^= $0A`
   (paleta 6→3 = espelho). P2 (pal 7) fica intacto.
3. `C0:3A9A` (fim da recarga de paleta `C0:3A60-3A9D`): refaz o espelho para não ficar 1 frame atrasado.

**Validação válida (mesmo timing) — mod × mod com a regra desligada**, 530 frames:
18 609 px alterados, **destino sempre na rampa preta (0 erros)**, origem ouro em 95,6% (o resto são
frames do "flash" de dano, que escreve `$06C0` fora da rotina hookada). Prints 34-37.

**⚠ ARMADILHA GRANDE (custou o ciclo 4 vermelho):** os hooks **mudam o timing** e o RNG da CPU muda
com ele → a luta joga diferente já no frame 1 (`x1` 203 vs 201). Consequência: **checks alinhados ao
baseline da ROM limpa não valem para mod com código** (giram ❌ mesmo com o mod certo). Verificação
válida = mod × mod-com-regra-desligada, ou checks que não dependem do alinhamento de frame.

## Como continuar
0. **Luvas pretas (em curso):** o mecanismo está implementado e medido; falta **cobrir as poses em que
   o punho é desenhado por um tile do grupo da cabeça** (ex.: `$2E` no punho erguido). Caminho: rodar o
   macro, colher OAM+buffer do espelho por frame, e para cada tile que tenha ouro *abaixo da linha da
   cabeça* acrescentar o tile na regra do hook `C0:5CA9` (hoje `$0C`/`$0E`), validando sempre por
   "mod × mod-com-regra-desligada" (o baseline limpo não serve — ver armadilha do timing). Depois
   disso, rever os checks do `mod.json` para não compararem luta-alinhada ao baseline limpo.
1. **Entrega pendente do repositório:** commitar as mudanças de ferramenta + mod + docs (`feat/…` → PR →
   squash, governança `opensource-project`) — **só a pedido do usuário**.
2. **Outra cor para o gi, se pedido:** trocar só as 5 constantes da cor no `patch.asm` (+ as 4 do
   retrato) e rodar `fab cycle run` de novo. Feito até agora: cor 0 azul, cor 1 rosa do Dan, cor 2 preta
   do Akuma; cor 3 = verde-escuro (intocada, states `luta-ken-2chutes(-fight)`).
3. **Olhos do retrato:** opção A (`$3C20`) aplicada e legível (print 23); opção B (`$2C21`) documentada no
   print 15 — trocar é patch de dados, não precisa de novo ciclo para montar.
4. **Fora de escopo, só se pedido:** tela de vitória/final do Ken (paleta não verificada), cores 4/5,
   mudar o *desenho* da roupa (exigiria descomprimir/recomprimir S-DD1).

## Perguntas em aberto
- O que liga `$1C41,X` (cores 4/5)? ~~2+ socos/chutes = cores 2/3?~~ **ambos confirmados** (cor 2
  branca com `1 Y+X`, cor 3 verde-escuro com `1 B+A`).
- Tela de vitória / final do Ken: usam a paleta de retrato `0x1F4E60`? (não verificado)
- X/vida do P2 (`$0989`/`$09BE`) — inferidos pela estrutura, conferir no primeiro baseline.
- O que dispara a recarga de paleta da rotina `C0:3A8F` a cada ~70 frames em plena luta? (caracterizado
  só por observação: `ev-7d902d01f792`, `ev-d6cb5f0e50b5`)
- Ids 6 e 16 da grade (nomes não capturados na varredura).
- Lane estático (`fab re analyze`) ainda não rodou; o loader do ghidra-snes provavelmente vê o S-DD1 como
  LoROM e não cobre o código que roda em `$C0-$FF` (o `ghidra_addr` também devolve LoROM para `sdd1`).

## Avanços (diário — acrescente embaixo, com data)
- **2026-10-25** — ROM registrada (`fab rom add … --id sfa2`). Navegação headless até a luta e 4 states.
  Paleta do Ken achada por cor (frame → BGR555 → busca na ROM), confirmada por sondas de leitura/escrita,
  dumps de CGRAM e diff de WRAM. Mapa S-DD1 do `snesfab` corrigido; watch de CGRAM criado. Cor escolhida
  (azul royal) por simulação; patch + checks desenhados. Prints 01-16 em `games/sfa2/prints/`.
  Parado a pedido do usuário; criado o padrão "uma skill por jogo + pasta de prints" (CLAUDE.md,
  AGENTS.md, snes-mod-factory, CoALA).
- **2026-10-25 (tarde)** — Mod `sfa2-ken-gi-azul` criado e **PRONTO**: `data[]` implementado no
  `build.py` (2 regiões de dados, 0 hijacks, 0 avisos), states de regressão `luta-ken-chute(-fight)`
  criados e conferidos, ciclo 1 (15/16 — os 40 frames iniciais mediam a paleta velha embutida no state)
  e ciclo 2 (**16/16, veredito `objetivo-cumprido`**, regressão 0 divergências). Recarga de paleta pela
  rotina `C0:3A8F` caracterizada (`ev-7d902d01f792`, `ev-d6cb5f0e50b5`) → feature **`warmup`** de
  medição no harness/emu/CLI. Diff pixel a pixel: só os 5 tons do gi mudam; cabeça intacta (print 24);
  olhos do retrato legíveis com `$3C20` (print 23). Prints 17-24. Ferramentas ainda **sem commit**.
- **2026-10-25 (noite)** — Mod **`sfa2-ken-azul-e-rosa`** PRONTO (ciclo 1, 29/29 checks,
  `objetivo-cumprido`): cor 1 do Ken de roxa a **rosa como o do Dan** (cópia fiel dos tons do gi dele),
  cor 0 continua azul; regressão na cor 2 (branco) com 0 divergências. Dan = **id 12** achado pela
  grade (`$7E:07A2` segue o cursor; nomes na tela confirmam AKUMA=2, M.BISON=10, DAN=12); hipótese
  "2+ socos = cor 2 (branco)" **confirmada** (state `luta-ken-2socos`); retrato do Dan usa índices
  próprios (3 rampas simuladas, print 28). Prints 25-29. O trabalho da tarde foi commitado em 3 commits
  e submetido no PR #9 (ferramentas + mod azul + docs).
- **2026-10-25 (madrugada)** — Terceira roupa: cor 2 do Ken de branca a **preta do Akuma** (cópia fiel
  do gi dele, id 2, `$2908 $18C6 $14A5 $1084 $1084`; retrato com o realce — simulação print 33) no mod
  `sfa2-ken-azul-e-rosa` (ciclo 3, **42/42 checks, `objetivo-cumprido`**). Hipótese "2+ chutes = cor 3"
  **confirmada** (gi verde-escuro; states `luta-ken-2chutes(-fight)`); regressão movida para a cor 3 com
  0 divergências. Lição: `$7BDE` é comum ao gi do Ryu e à cor 2 do Ken → checks de paleta guardam por
  2+ tons (check `sprite-preta` corrigido no ciclo 3). Prints 30-33. Memória CoALA consolidada (notas
  #225 paletas, #226 recarga, #227 receita de recolor + lição das guardas).
- **2026-10-25 (sessão 2, luvas)** — Investigação das luvas pretas: descoberto que a **paleta de sprite
  é `p+8`** (OAM 6/7 → CGRAM 14/15; sprite pal 3 → CGRAM 11, livre), que **cada pose tem a sua lista de
  cels** (`0x3C49A9`/`0x3C49F2` na pose parada) e que o ouro é do cabelo **e** das luvas (separação só
  por tile). Implementados **3 hooks** (espelho `C0:0312`, atributo `C0:5CA9`, recarga `C0:3A9A`) no
  `sfa2-ken-azul-e-rosa`, com rampa preta de 2 tons (`$2908`/`$1084`) a pedido do dono (sombreado).
  Validação por "mod × mod com a regra desligada": só o ouro muda (0 destinos fora da rampa).
  Ferramentas: `fab run --poke` (`Poke` em `snesfab/emu.py`, testes) e `build` aceitando o endereço de
  execução S-DD1 (`C0:xxxx`) além do canônico LoROM. **Descoberta crítica:** os hooks deslocam o RNG
  da CPU → a luta joga diferente do frame 1; o ciclo 4 deu 21/46 por isso (checks alinhados ao baseline
  limpo não servem). Prints 34-37. Falta: cobrir as poses em que o punho cai em tile da cabeça.

