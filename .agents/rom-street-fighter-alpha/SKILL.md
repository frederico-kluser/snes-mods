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
   — chaves desta skill: `sfa2-paletas`, `sdd1-mapa`, `skill-por-jogo` (`coala.py get <chave>`).
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

Comando: `./fab state boot sfa2 <nome> [--from-state <origem>] --macro "<macro>" --note "…"` e abra a
`preview_sheet`. Grade da seleção, 1.ª linha: Ryu, Adon, Chun-Li, Guy, **Ken** (4× →). Depois do botão:
MANUAL/AUTO (Y = MANUAL) → SPEED (Y = normal) → mapa → "KEN VS ROSE" (~f990-1110) → luta (~f1410).
No `luta-ken-rose`, parado: ROUND 1 ~f90-150, FIGHT! ~f180-390, a Rose acerta um Soul Spark ~f567
(o Ken fica azul/elétrico até ~f638 — paletas de efeito, não do uniforme).

## Fatos verificados (dinâmico primeiro)
**Cor do uniforme (seleção).** 1 soco (Y/X/L) = cor 0, gi vermelho; 1 chute (B/A/R) = cor 1, gi roxo
(prints 10, 13). Leitura estática da rotina de seleção (`C0:DECA`, conta os botões em `$AE/$AF` e usa a
tabela `$C0:DF28`): 2+ socos juntos = cor 2 (gi branco), 2+ chutes = cor 3 (gi verde-escuro) — **inferido,
não testado**. Cores 4/5 (laranja / roxo-escuro) vêm de outro caminho (`C0:E0F8`, quando `$1C41,X ≠ 0`,
tabela `$C0:DF2C`) — gatilho desconhecido. A rotina `C0:DF74` grava a cor do P1 em `$7E:07C8`
(`ev-1883e2cdf5b2`) e, em espelho (mesmo personagem e mesma cor), troca pelo par (tabela `$C0:CEBC`:
0↔1, 2↔3, 4↔5).

**Paletas dos lutadores (ROM, sem compressão).** Tabela de ponteiros `$BF:B6C8` (PC `0x1FB6C8`), 16 bits
por personagem (índice = id do personagem), para o banco `$DF` (janela HiROM → PC `0x1F0000 + ptr`).
Cada lutador tem 16 paletas de 32 B: 0-5 = as 6 cores do uniforme, 6 = paleta do golpe especial (Ken:
Hadouken; vem pela segunda tabela `$BF:B644`), 7-15 = efeitos (fogo, choque, flashes).
Ryu = id 0 (`0x0060`), **Ken = id 1 (`0x0260`)**, Rose = id 9 (`0x1580`, confirmada na CGRAM).
- Ken cor 0: `$DF:0260` = PC `0x1F0260` = `$BE:8260`. Índices: 1 contorno/faixa, 2-8 pele/branco,
  **9-13 = gi** (`$011E $001B $0017 $0013 $0011`, do mais claro ao mais escuro), 14-15 cabelo.
  O recolor dos índices 9-13 cobre blusa, mangas e calça e deixa a faixa preta intacta (print 11).
- Quem lê (`ev-dbaa2b8b4bf8`, seleção → luta): carregador do início do round `C0:394B-39B1` (laço em
  `C0:3982`: cor = `$C8,X` × 32 + ponteiro → `$06C0+lado`; depois 32 B da paleta especial → `$0600+lado`;
  m8,x16), cópia de efeitos `C0:3A60-3A9D` (escreve `$06C0,X` em `C0:3A91` só durante efeitos, m8,x16 —
  `ev-221b88cc802b`) e a tela de seleção (leitura com PC seguinte `C0:DFCC`, todo frame, m16,x16).

**Retratos (ROM, sem compressão).** Ken em PC `0x1F4E60` (= `$BE:CE60`), 6 paletas de 32 B na mesma ordem
das cores; Ryu em `0x1F4DA0` (passo de `0xC0` por personagem). Cor 0: **índices 5-8 = gi**
(`$113E $0C7B $0855 $000F`); 1-4 cabelo/munhequeira, 9-14 pele, 15 contorno. ⚠ Os **olhos** do retrato
usam o índice 8 (`$000F`) — trocar esse tom muda a cor dos olhos (print 15). A mesma paleta serve a
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

## Estado (2026-10-25) — mod "roupa do Ken"
- **Pedido do usuário:** "modificar as roupas do Ken no jogo". **Parado a pedido do usuário** antes de
  criar o mod (nenhum `fab cycle run` ainda).
- **Decidido (pelo agente, registrado):** trocar o uniforme padrão (cor 0) de vermelho para **azul royal**
  — contraste forte, a faixa preta continua visível e não colide com o roxo da cor 1 (print 11; o usuário
  pode pedir outra cor: são 5 + 4 valores no topo do patch). Mudar também o retrato (seleção e VS) para a
  roupa ficar coerente. Cores 1-5, efeitos e os outros personagens ficam iguais.
- **Patch e mod.json desenhados:** `references/rascunho-mod.md` (só dados, sem hijack, sem M/X).
- **Ferramentas ajustadas nesta sessão** (branch `feat/sfa2-roupa-ken`, **sem commit**):
  `snesfab/rom.py` (mapa S-DD1 + `test_sdd1_mmc_padrao`), `snesfab/emu.py` (watch `cgram:`/`vram:`/`oam:`
  + `test_watch_ppu`), `snesfab/setup_tools.py` (o doctor acusa prints versionados), `.gitignore`
  (`games/*/prints/`).

## Como continuar (em ordem)
1. **Regiões de dados no build** (pendente, necessário): hoje `snesfab/build.py` trata toda região alterada
   que não era zero como *hijack* (desmonta, avisa "padrão m8,x8 sem evidência") e o ciclo põe uma sonda
   `exec` nela. Implementar `mod.json → "data": [{"addr": "BE:8272", "length": 10, "evidence": "…"}]`:
   regiões cobertas viram `kind: "data"` (sem `_hijack_report`, fora de `build["hijacks"]`) e uma região
   não declarada continua sendo tratada como hijack. Teste unitário + rodar `fab selftest --quick`.
2. **State da regressão:** `luta-ken-chute` = `selecao` + a macro do `luta-ken-rose` trocando o 1.º `Y` por
   `B`; depois `luta-ken-chute-fight` = `+430`. Confira na folha que o Ken está de gi roxo.
3. `./fab mod new sfa2-ken-gi-azul --game sfa2 --title "Ken de gi azul" --goal "<do rascunho>"` e copie
   `patch.asm`, `mod.json` e as macros de `references/rascunho-mod.md`.
4. `./fab build mods/sfa2-ken-gi-azul`: esperar 2 regiões de dados (`$BE:8272`, 10 B; `$BE:CE6A`, 8 B)
   + o checksum do cabeçalho, zero avisos.
5. `./fab cycle run mods/sfa2-ken-gi-azul --note "gi azul: lutador (cores 9-13) + retrato (5-8)"` → ler o
   `report.md`, olhar `compare.png`/`trace_compare.png` de cada cenário, **copiar para
   `games/sfa2/prints/`** com o próximo número e registrar `fab cycle verdict`.
6. Iterar (uma hipótese por ciclo): olhos do retrato (manter `$000F`? usar um tom neutro?), sprite da
   luta (conferir se o rosto usa tons 9-13 — print 16), cores 2-5 (fora do escopo, a não ser que o
   usuário peça).
7. Pronto quando: todos os checks ✅, imagens conferidas, regressão com 0 frames divergentes →
   `objetivo-cumprido`, BPS em `build/sfa2-ken-gi-azul/`, `notes.md` e CoALA atualizados e o **Estado**
   desta skill reescrito.

## Perguntas em aberto
- O que liga `$1C41,X` (cores 4/5)? A seleção com 2+ botões dá mesmo as cores 2/3?
- Tela de vitória / final do Ken: usam a paleta de retrato `0x1F4E60`? (não verificado)
- X/vida do P2 (`$0989`/`$09BE`) — inferidos pela estrutura, conferir no primeiro baseline.
- Lane estático (`fab re analyze`) ainda não rodou; o loader do ghidra-snes provavelmente vê o S-DD1 como
  LoROM e não cobre o código que roda em `$C0-$FF` (o `ghidra_addr` também devolve LoROM para `sdd1`).

## Avanços (diário — acrescente embaixo, com data)
- **2026-10-25** — ROM registrada (`fab rom add … --id sfa2`). Navegação headless até a luta e 4 states.
  Paleta do Ken achada por cor (frame → BGR555 → busca na ROM), confirmada por sondas de leitura/escrita,
  dumps de CGRAM e diff de WRAM. Mapa S-DD1 do `snesfab` corrigido; watch de CGRAM criado. Cor escolhida
  (azul royal) por simulação; patch + checks desenhados. Prints 01-16 em `games/sfa2/prints/`.
  Parado a pedido do usuário; criado o padrão "uma skill por jogo + pasta de prints" (CLAUDE.md,
  AGENTS.md, snes-mod-factory, CoALA).
