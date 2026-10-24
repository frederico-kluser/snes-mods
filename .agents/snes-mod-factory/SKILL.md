---
name: snes-mod-factory
description: Fábrica de mods (ROM hacks) de Super Nintendo deste repositório — do "aqui está a ROM, quero X" até o patch BPS verificado. Registra a ROM (cabeçalho SMC, LoROM/HiROM), cria/importa savestates, descobre RAM e código com o MesenCE headless (sondas, busca de RAM, CDL) e o Ghidra+ghidra-snes, escreve o patch Asar, roda o ciclo de evolução com vídeo/frames/RAM e entrega. Use SEMPRE que o pedido envolver ROM de SNES/Super Nintendo/Super Famicom (.sfc/.smc), mod, hack, patch, cheat, "quero que o personagem…", savestate, emulador, análise de vídeo/imagens de gameplay ou o comando `fab`.
---

# SNES mod factory (`fab`)

Tudo passa pela CLI `fab` na raiz do repo: `./fab …` (Git Bash), `.\fab.ps1 …` (PowerShell) ou
`fab.cmd …`. A saída é JSON (ou registros de evidência). `./fab <cmd> --help` mostra as opções.
Protocolo de engenharia reversa e de patch 65816: skill **snes-rea-modder**. Ciclo autônomo: skill
**snes-mod-cycle**. Memória do projeto: skill **snes-mods-coala-agent-skill**.

## Fluxo padrão: "ROM + o que eu quero"

0. **Saúde**: `./fab doctor --quick` (falhou → `./fab setup`, que é idempotente).
1. **Memória**: `python .agents/snes-mods-coala-agent-skill/scripts/coala.py recall "<jogo> <pedido>" --budget 1500`
   e leia `games/<jogo>/notes.md` se o jogo já existir.
2. **Registrar a ROM** (nunca modifique a ROM nem a copie para lugares versionados):
   `./fab rom add "<caminho>" --id <slug>` → `roms/<id>/<id>.sfc` (base limpa, só leitura, sem cabeçalho SMC),
   `games/<id>/game.json` (mapa, chipset, checksum, vetores) e `games/<id>/notes.md`.
   Coprocessador (SA-1, SuperFX, Cx4…) → avise o usuário das limitações antes de prometer.
3. **Savestate no momento certo** (o ciclo sempre parte de um state):
   - O usuário deu um `.mss` do Mesen/MesenCE → `./fab state import <jogo> <nome> --file <caminho>`.
   - Senão, tente sozinho: `./fab state boot <jogo> <nome> --macro "120;1 Start;90;1 Start;240"` e abra a
     folha `preview_sheet` com Read; ajuste o macro até o último frame mostrar o momento pedido
     (`--from-state` encadeia a partir de outro state). Sintaxe de macro: `references/cli.md`.
   - Só se for inviável (jogo longo, menus aleatórios): peça ao usuário `./fab play <jogo>`,
     Shift+F1 no momento certo e depois rode `./fab state import <jogo> <nome> --slot 1`.
   - States de snes9x/bsnes/BizHawk/RetroArch NÃO são compatíveis com o MesenCE.
4. **Achar a RAM** (dinâmico primeiro — é a verdade do jogo):
   `./fab ram search <jogo> --state <s> --macro "<ação>" --frames N` →
   `./fab ram query <run> --unchanged 0:19 --changed 19:30 --game <jogo>` →
   confirme com `./fab run <jogo> --state <s> --macro … --watch nome=7E:xxxx:2s` (gera `trace.png`).
5. **Achar o código**: `./fab probe writes|reads <jogo> 7E:xxxx --state <s> --macro …` (instrução que
   escreve, reconstruída, + M/X reais) e `./fab probe exec <jogo> <BB:AAAA>`; depois o estático:
   `./fab re cdl <jogo> --state <s> --frames 3600` (repita com vários states) → `./fab re analyze <jogo>` →
   `./fab re func|xrefs|search|decompile`. Cite o `evidence_id` de cada fato.
6. **Escrever o mod**: `./fab mod new <id> --game <jogo> --goal "<o que se deve VER e medir>"`;
   edite `mods/<id>/mod.json` (cenários: state, macro, frames, watch, checks — exemplo completo em
   `mods/testbed-double-jump/`) e `patch.asm` seguindo **snes-rea-modder** (M/X, regra dos 4 bytes,
   autoclean/freecode, `expand_to` quando a ROM não tem bancos $10+ livres).
   Inclua sempre um cenário de **regressão** (comportamento original que precisa ficar igual).
7. **Ciclo**: siga **snes-mod-cycle** (`./fab cycle run mods/<id>` → olhar as imagens → `./fab cycle verdict`)
   até `objetivo-cumprido` ou `max_cycles`.
8. **Entrega**: `build/<id>/<id>.bps` (aplica com Flips/beat ou `./fab bps <rom> <bps> <saída>`),
   `mods/<id>/patch.asm`, `cycles/<id>/…/report.md`. Atualize `games/<jogo>/notes.md` (RAM, rotinas,
   hijacks com evidência) e grave na memória CoALA o que for durável (`coala.py add --type semantic …`).

## mod.json — critérios (`checks`)

Expressões sobre os traços de RAM do cenário (mod) e da baseline (ROM limpa, mesmo state/macro):
`min(y) < baseline.min(y) - 320`, `count(edges(vy < -60)) >= 2`, `last(air) == 0`,
`all(x == baseline.x)`, `any(pressed('B') & (air == 1))`, `at(lives, 300) == at(lives, 0)`.
Funções: min max mean sum abs len first last at window delta changes count any all edges falls
argmin argmax pressed clip. `watch`: `nome=BB:AAAA[:1|2|4][s]` (s = com sinal).
Os checks medem o objetivo; nunca os enfraqueça para "passar".

## Vídeos e imagens do usuário

O usuário pode gravar (OBS, celular, gravador do Mesen) e soltar em `media/inbox/`:
`./fab media inbox` (ou `./fab media analyze <arquivo|pasta> [--at 1.5,2.0]`) → folhas de contato com
timestamps, cortes de cena e `motion.png` (picos = ação). Leia as folhas com Read e compare com o que
o mod deveria fazer; detalhes em `references/video.md`. Comparar duas runs: `./fab media compare <runA> <runB>`.

## Quando chamar o usuário (só bloqueios reais)

ROM ausente/corrompida/intercalada; impossível chegar sozinho ao momento do jogo; pedido ambíguo
de um jeito que muda o design (ex.: "mais rápido" — andar? correr? tudo?); `fab doctor` falha e
`fab setup` não resolve. Todo o resto: decida e registre no relatório.

## Regras

- Nunca versionar ROMs, states, builds, BPS, frames ou vídeos de jogos comerciais (`fab doctor` verifica).
- A base limpa é só leitura; o Asar trabalha numa cópia em `build/<mod>/`.
- O REA 6.7.0 (MCP `rea`) não abre ROMs de SNES — use `fab re`; o REA serve para binários PE/ELF/JS/.NET.
- Captura: o frame N mostra o estado da lógica do frame N-1 (atraso normal da OAM); imagem 256x224.

Referências: `references/cli.md` (todos os comandos), `references/snes-ref.md` (mapa de memória,
registradores, flags, CDL), `references/video.md` (análise visual e veredito).
