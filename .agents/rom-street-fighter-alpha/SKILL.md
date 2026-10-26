---
name: rom-street-fighter-alpha
description: Skill do jogo Street Fighter Alpha 2 (USA, SNES, chip S-DD1; id `sfa2` na fábrica) — tudo o que já se descobriu (mapa S-DD1, paletas dos lutadores e retratos, RAM dos jogadores, rotinas, gráficos comprimidos e como trocá-los sem codec, savestates e como recriá-los), o estado dos mods do Ken e o passo a passo para continuar. Use SEMPRE que o pedido mencionar Street Fighter Alpha 2, SFA2, `sfa2`, Ken, Rose, roupa/gi/cor/paleta/desenho de lutador desse jogo, ou "continua o mod do Ken". É o modelo do padrão "uma skill por jogo" da fábrica.
---

# Street Fighter Alpha 2 (`sfa2`) — skill do jogo

> Diário vivo do jogo (padrão `rom-<jogo>`: `.agents/snes-mod-factory/references/skill-de-jogo.md`). Fluxo geral:
> **snes-mod-factory** → **snes-mod-cycle**; cor/sprite/desenho: **snes-sprite-paint**.

## Comece por aqui (toda sessão)
1. `./fab doctor --quick`.
2. `python .agents/snes-mods-coala-agent-skill/scripts/coala.py recall "sfa2 ken paleta gi luvas s-dd1" --budget 1500`
   — chaves: `sfa2-paletas`, `sfa2-recarga-paleta`, `sdd1-mapa`, `skill-por-jogo`, `gfx-override` (`coala.py get <chave>`).
3. Leia **Estado** e **Como continuar** e `games/sfa2/notes.md` (RAM, rotinas, as 16 dificuldades).
4. Prints em `games/sfa2/prints/` (ignorada pelo git): leia o `LEIA-ME.txt`; cada avanço = próximo número + linha.
5. Clone novo? `fab rom add <sfa2.sfc> --id sfa2` (o usuário tem um `.zip`: extraia numa pasta vazia) e recrie os
   states pela tabela abaixo.

## Identificação
- `Street Fighter Alpha 2 (USA).sfc`, 4 194 304 B, CRC32 `9c59ddff`, SHA-1 `f4ede150b5281f7f5d7e3188c6d9163c2bc66475`,
  SHA-256 `910a29f834199c63c22beddc749baba746da9922196a553255deade59f4fc127` (sem cabeçalho SMC).
- Cabeçalho `STREET FIGHTER ALPHA2`, código `AUZE`, mapa `$32` (LoROM + S-DD1, FastROM), chipset `$43`, 4 MiB,
  região `$01`, checksum `$DB9A` válido, reset `$00:FF90`. O MesenCE 2.2.1 emula o S-DD1 corretamente (print 01).
- Paletas NÃO são comprimidas (cor = patch de dados). Gráficos dos lutadores são (S-DD1): o desenho muda sem codec
  com `fab gfx override --expand` (validado, print 50).

## Mapa S-DD1
- `$00-$3F/$80-$BF:8000-FFFF` = LoROM fixa dos 2 primeiros MiB; `$C0-$FF` = janelas de 1 MiB (`$4804-$4807`, padrão
  0/1/2/3); `$40-$7D` não mapeiam ROM.
- O jogo **não troca** as janelas (nenhuma escrita em `$4804-$4807` do power-on à luta: `ev-021fd69dbc74`,
  `ev-d1b78376344b`, `ev-33b9df93b71e`, `ev-6f5e50e992d4`); só `$4800`/`$4801` = 1.
- Executa em `$C0:xxxx` com **DBR = `$BF`**: sondas de MMIO no banco `$BF` (`fab probe … BF:4800`).
- Asar `lorom` endereça certo os 2 primeiros MiB (`$BE:8260` = PC `0x1F0260`).

## Como chegar a cada momento (states em `games/sfa2/states/`, ignorados)
| state | origem + macro | mostra |
|---|---|---|
| `menu-titulo` | power-on + `700;1 Start;200;1 Start;500` (1402 f) | título, logo antes do menu |
| `selecao` | `menu-titulo` + `30;1 Start;60;1 Start;60;1 A;60;1 Start;60;1 B;60;1 Start;300` (636 f) | PLAYER SELECT, cursor 1P no Ryu |
| `luta-ken-rose` | `selecao` + `10;1 Right;20;1 Right;20;1 Right;20;1 Right;40;1 Y;100;1 Y;100;1 Y;1184` (1501 f) | começo da luta Arcade: Ken (cor 0) × Rose, Itália |
| `luta-ken-rose-fight` | `luta-ken-rose` + `430` | logo depois do FIGHT! |
| `luta-ken-chute(-fight)` | idem com o 1.º `Y` → `B` | Ken cor 1 (gi roxo) |
| `luta-ken-2socos(-fight)` | idem com `Y+X` na seleção | Ken cor 2 (gi branco) |
| `luta-ken-2chutes(-fight)` | idem com `B+A` na seleção | Ken cor 3 (gi verde-escuro) |

`./fab state boot sfa2 <nome> [--from-state <origem>] --macro "<macro>"` e abra a `preview_sheet`. Seleção, 1.ª linha:
Ryu, Adon, Chun-Li, Guy, **Ken** (4× →); depois MANUAL (Y) → SPEED normal (Y) → mapa → "KEN VS ROSE" (~f990-1110) →
luta (~f1410). No `luta-ken-rose` parado: ROUND 1 ~f90-150, FIGHT! ~f180-390, Soul Spark da Rose ~f567 (Ken azul até ~f638).

## Fatos verificados
**Cor do uniforme.** 1 soco = cor 0 (vermelho), 1 chute = cor 1 (roxo), 2+ socos = cor 2 (branco), 2+ chutes = cor 3
(verde-escuro) — todos confirmados em jogo. Cores 4/5 (laranja/roxo-escuro): `C0:E0F8` quando `$1C41,X ≠ 0`, tabela
`$C0:DF2C` (gatilho desconhecido). `C0:DF74` grava a cor do P1 em `$7E:07C8` (`ev-1883e2cdf5b2`); em espelho (mesmo
lutador e cor) troca pelo par (tabela `$C0:CEBC`: 0↔1, 2↔3, 4↔5).

**Grade e ids.** `$7E:07A2` = id sob o cursor. Linhas 1-3: Ryu(0) Adon(5) Chun-Li(4) Guy(7) Ken(1) | Dhalsim(15) Gen(17)
Sakura(13) Rolento(14) ?(16) | Charlie(3) Birdie(8) Rose(9) ?(6) Sagat(11). Linha 4 oculta (colunas 1-2): Akuma(2),
M.Bison(10), Dan(12). Gi do Dan `$6ADC $521E $419C $311A $2098` (`$DF:1E40`); retrato do Dan (`0x1F56A0`) usa 6-8 como
marrons (derive do ramp do gi; print 28).

**Paletas dos lutadores (ROM, sem compressão).** Ponteiros em `$BF:B6C8` (PC `0x1FB6C8`), 16 bits por id, para o banco
`$DF` (PC `0x1F0000 + ptr`). 16 paletas de 32 B por lutador: 0-5 = cores do uniforme, 6 = golpe especial (via `$BF:B644`),
7-15 = efeitos. Ryu `0x0060`, **Ken `0x0260`**, Rose `0x1580`.
- Ken cor 0: PC `0x1F0260` (`$BE:8260`). Índices: 1 contorno/faixa, 2-8 pele/branco, **9-13 = gi** (`$011E $001B $0017
  $0013 $0011`), 14-15 cabelo **e** luvas. Cor 1: `$5910 $488C $404A $3828 $3006` em `0x1F0292`. O recolor de 9-13
  cobre blusa, mangas e calça; cabeça intacta (print 24).
- Quem lê (`ev-dbaa2b8b4bf8`): carregador do round `C0:394B-39B1` (laço `C0:3982` → `$06C0+lado`; especial → `$0600+lado`;
  m8,x16); recarga `C0:3A60-3A9D` (`LDA [$10],Y` em `C0:3A8F` → `STA $06C0,X` em `C0:3A91`, m8,x16 — `ev-221b88cc802b`);
  seleção (PC seguinte `C0:DFCC`, m16,x16).
- **Recarga em plena luta** (`ev-7d902d01f792`, `ev-d6cb5f0e50b5`): `C0:3A8F` regrava `$06C0` a cada ~70 f e nas
  transições → o state traz a paleta da ROM limpa; cenários de cor usam `warmup` (ex.: 40).

**Retratos (ROM).** Ken em `0x1F4E60` (`$BE:CE60`), 6 paletas na ordem das cores (Ryu `0x1F4DA0`, passo `0xC0`).
Cor 0: **5-8 = gi** (`$113E $0C7B $0855 $000F`), 1-4 cabelo/munhequeira, 9-14 pele, 15 contorno. ⚠ Os **olhos** usam o
índice 8 (print 15); com `$3C20` continuam legíveis (print 23). Mesma paleta na seleção (BG pal 6) e no VS (sprite pal 0).

**WRAM / CGRAM.**
| endereço | tam. | significado | evidência |
|---|---|---|---|
| `7E:0500-06FF` | 512 | buffer de paletas = CGRAM `$000-$1FF` (vai para a CGRAM pelo DMA disparado em `C0:0320`, m8,x16) | dump CGRAM × WRAM + `fab ppu dma` |
| `7E:06C0` / `06E0` | 32 | paleta do P1 / P2 → CGRAM pal 14 / 15 | `ev-221b88cc802b` + dump |
| `7E:0600` / `0620` | 32 | golpe especial P1 / P2 → CGRAM pal 8 / 9 | carregador + dump |
| `7E:07C8` / `0A48` | 1 | cor do P1 / P2 | diff de WRAM + `ev-1883e2cdf5b2` |
| `7E:07A2` / `0A22` | 1 | id do P1 / P2 | `C0:DF85` (inferido) |
| `7E:0709` | 2 | X do P1 | `runs/20261025-002629-ramsearch-sfa2` |
| `7E:073E` | 1 | vida do P1 (máx. 144; `$0740` = barra) | `runs/20261025-002810-ramsearch-sfa2` |
| `7E:0989` / `09BE` | 2 / 1 | X / vida do P2 | **inferido** |
| `7E:15C0` | 544 | sombra do OAM (DMA disparado em `C0:0305`) | `fab ppu dma` |

CGRAM na luta: pal 8/9 especiais, **pal 14 = Ken** (gi = bytes `$1D2-$1DA`), pal 15 = Rose; sprite usa **p+8** (OAM 6
→ CGRAM 14; OAM 3 → CGRAM 11, toda a zeros = livre para espelho). Seleção: BG pal 6 = retrato, pal 14 = sprite pequeno.
VS: pal 8 = retrato do P1, pal 9 = P2. Display ligado só nas linhas ~24-215 (IRQs em 21/24/215).

**Gráficos (S-DD1, medido 2026-10-25 com `fab gfx dump`, `runs/20261025-200722-gfx-chip2`).** Na luta, todo upload
comprimido sai de **um disparo** (`C0:048C`, canal 0, fonte fixa `DMAP $09`, m8,x8; hijack de 5 B `LDY $00 | STA
$420B`); cada fonte dá sempre o mesmo desenho. `E0:0427` (1600 B → VRAM `$E000`, a cada ~14 f) = Ken parado.
O jogo escreve o DMAP **uma vez só** (o override devolve o DMAP depois do DMA); `$4801` arma o canal
(`--chip-disarm 00:4801=00`). LoROM livre: trechos de até 210 B → tabela e cópias vão na área expandida (`--expand`, 5 MiB).

**Sprites do Ken (motor de cels).** Cada pose tem lista `[count][x,y,tile,flags]` (parado alterna `0x3C49A9`/`0x3C49F2`;
ponteiro `$18,X`, banco `$F5,X`, sonda em `C0:5C8E`). Motor `C0:5C60-5CE2`: attr = `(flags & $C2) ^ $0B`, bits 2-5 livres.
O mesmo nº de tile é luva numa pose e cabelo noutra. Rótulos luva × cabelo por conteúdo: `games/sfa2/parts/ken-ouro.json`
(cobertura 99,7%, 300 frames do macro `luta.txt`) → **nível 4** (66 sprites com as duas peças).

## Estado (2026-10-25, fim da sessão 4)
| pedido | mod | resultado |
|---|---|---|
| gi azul (cor 0) | `sfa2-ken-gi-azul` | PRONTO: ciclo 2, 16/16, `objetivo-cumprido`; BPS 137 B, 2 regiões de dados (`$BE:8272`, `$BE:CE6A`); tons `$7E06 $7102 $60A1 $5060 $4440`, retrato `$7E06 $7102 $5881 $3C20`. Prints 17-24 |
| rosa do Dan (cor 1) + azul | `sfa2-ken-azul-e-rosa` | PRONTO: ciclo 1, 29/29. Prints 25-29 |
| preta do Akuma (cor 2) | `sfa2-ken-azul-e-rosa` | PRONTO: ciclo 3, 42/42 (`$2908 $18C6 $14A5 $1084 $1084`; retrato com realce). Regressão na cor 3: 0 divergências. Prints 30-33 |
| só as luvas pretas na roupa preta | `sfa2-ken-azul-e-rosa` (3 hooks) | EM CURSO: espelho de paleta + marcas por cel; resíduo no nível 4; ver Como continuar |

⚠ Os BPS não empilham (nascem da ROM limpa): o `azul-e-rosa` tem as duas cores. ⚠ `$7BDE` (cor 2) = gi do Ryu: checks de
paleta guardam por 2+ tons. Kit genérico de pintura (sessões 3-4) testado aqui: **snes-sprite-paint**, prints 40-50.

**Luvas (detalhe).** Rampa de 2 tons (`$2908` realce + `$1084` sombra; contorno `$0842` fora; print 34). Hooks no
`patch.asm`: `C0:0312` (antes do DMA da CGRAM: copia `$06C0-$06DF` → `$0660-$067F`; se `$07C8 == 2` troca 14/15),
`C0:5CA9` (paleta 6 + cel marcado → `attr ^= $0A` = espelho), `C0:3A9A` (refaz o espelho na recarga). 284 cels marcados
em 28 poses (bit 2 das flags). Medido mod × mod-desligado: 119/140 frames limpos, 0 destinos fora da rampa.
⚠ Todo hook muda o RNG (luta diferente desde o f1): verificação com base variante (A/B), nunca contra a ROM limpa.

## Como continuar
0. **Luvas 100% (se o dono pedir):** agora dá para separar luva e cabelo DENTRO do tile, mesmo comprimido:
   `fab sprite snap` na roupa preta → `fab paint remap mods/<id> --capture … --object <Ken> --map 14:<sombra>,15:<realce>
   --part luva --store games/sfa2/parts/ken-ouro.json` (tiles comprimidos vão para `vram_tiles`) → `fab gfx dump sfa2`
   com states/macros que mostrem as poses (`luta.txt`) → `fab gfx override mods/<id> --dump <dir> --expand
   --chip-disarm 00:4801=00` → `fab build` → `fab gfx check` → `fab paint check`. ⚠ O desenho é o mesmo em TODAS as
   roupas: a luva fica preta nas 6 cores (decisão do dono) — ou combine com o espelho só na cor 2.
1. **Entrega no repositório:** tudo commitado no branch `feat/sfa2-roupa-ken` → PR #9 (CI verde em 2026-10-25);
   falta o squash merge, só a pedido do usuário (governança no `CLAUDE.md`).
2. **Outra cor de gi:** trocar as 5 constantes da cor (+ 4 do retrato) e `fab cycle run`.
3. **Fora de escopo, só se pedido:** vitória/final do Ken, cores 4/5.

## Perguntas em aberto
- O que liga `$1C41,X` (cores 4/5)? Vitória/final usam o retrato `0x1F4E60`? X/vida do P2 (`$0989`/`$09BE`) a conferir.
- O que dispara a recarga de `C0:3A8F` a cada ~70 f? Ids 6 e 16 da grade.
- `fab re analyze` não rodou: o loader do ghidra-snes vê o S-DD1 como LoROM e não cobre `$C0-$FF`.

## Avanços (diário)
- **2026-10-25 (manhã)** — ROM registrada, navegação headless até a luta, paleta do Ken achada (sondas, dumps de CGRAM,
  diff de WRAM), mapa S-DD1 corrigido no `snesfab`. Padrão "uma skill por jogo + prints". Prints 01-16.
- **(tarde)** — `sfa2-ken-gi-azul` PRONTO (16/16); `data[]` no build; `warmup` de medição; recarga `C0:3A8F`. Prints 17-24.
- **(noite)** — `sfa2-ken-azul-e-rosa`: rosa do Dan (29/29), Dan = id 12, "2+ socos = cor 2" confirmada. PR #9. Prints 25-29.
- **(madrugada)** — preta do Akuma (42/42), "2+ chutes = cor 3" confirmada; notas CoALA #225-#227. Prints 30-33.
- **(sessão 2, luvas)** — paleta `p+8`, listas de cels por pose, ouro compartilhado; 3 hooks; `--poke`; RNG muda
  com hooks (ciclo 4: 21/46 por isso). Prints 34-37.
- **(sessão 3, kit de pintura)** — ferramentas genéricas (snapshot do PPU + falsa cor, `fab sprite/palette/paint/ppu`,
  portões do build, base variante); luvas = nível 4; experimento A/B (ciclo 5); o mod voltou ao estado anterior. Prints 40-49.
- **(sessão 4, gráfico comprimido)** — `fab gfx dump` + `gfx override` + `gfx check` (sem codec) validados aqui como ROM
  de teste: bloco `E0:0427` (Ken parado) com o gi redesenhado, ROM expandida para 5 MiB, 35 tiles, 0 colaterais
  (o 1.º teste quebrou o stream seguinte porque o jogo conta com o DMAP: virou a devolução do DMAP no hook). Pesquisa
  de emuladores para ROM expandida (`rom_expandida` no build). Skills fundidas (`snes-mod-cycle`). Print 50.
