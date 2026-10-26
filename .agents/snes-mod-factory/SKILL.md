---
name: snes-mod-factory
description: Fábrica de mods (ROM hacks) de Super Nintendo deste repositório — do "aqui está a ROM, quero X" até o patch BPS verificado. Registra a ROM (cabeçalho SMC, LoROM/HiROM/chips), cria/importa savestates, descobre RAM e código com o MesenCE headless (sondas, busca de RAM, CDL) e o Ghidra+ghidra-snes, escreve o patch Asar, roda o ciclo de evolução com frames/vídeo/RAM e entrega. Use SEMPRE que o pedido envolver ROM de SNES/Super Nintendo/Super Famicom (.sfc/.smc), mod, hack, patch, cheat, "quero que o personagem…", savestate, emulador, vídeo/imagens de gameplay ou o comando `fab`.
---

# SNES mod factory (`fab`)

Tudo passa pela CLI `fab` na raiz: `./fab …` (Git Bash), `.\fab.ps1 …` (PowerShell), `fab.cmd …`. Saída em JSON;
`./fab <cmd> --help` mostra as opções; erros vêm como `Erro: <o quê> — Solução: <o que fazer>`.
Skills irmãs: **snes-mod-cycle** (patch 65816 + ciclo), **snes-sprite-paint** (cor, sprite, gráfico),
**pixel-peep** (ler/conferir píxeis), **snes-mods-coala-agent-skill** (memória), **rom-<jogo>** (diário de cada jogo).

## Fluxo: "ROM + o que eu quero"

0. **Saúde**: `./fab doctor --quick` (falhou → `./fab setup`, idempotente).
1. **Memória**: `python .agents/snes-mods-coala-agent-skill/scripts/coala.py recall "<jogo> <pedido>" --budget 1500`.
   Jogo conhecido → carregue a skill `rom-<jogo>` e leia `games/<jogo>/notes.md` antes de tudo.
2. **Registrar a ROM** (só leitura, nunca versionada): `./fab rom add "<arquivo>" --id <slug>` → `roms/<id>/<id>.sfc`
   (sem cabeçalho SMC), `games/<id>/game.json` (mapa, chip, checksum, vetores) e `notes.md`. Coprocessador (SA-1,
   SuperFX, Cx4…) → avise as limitações antes de prometer. Crie a skill `rom-<jogo>` (`references/skill-de-jogo.md`)
   e a pasta `games/<id>/prints/` (ignorada pelo git; todo avanço vira um print numerado + linha no `LEIA-ME.txt`).
3. **Savestate no momento certo** (todo ciclo parte de um):
   - o usuário deu um `.mss` do Mesen/MesenCE → `./fab state import <jogo> <nome> --file <arquivo>`;
   - senão: `./fab state boot <jogo> <nome> --macro "120;1 Start;90;1 Start;240"` e abra a `preview_sheet`; ajuste até
     o último frame mostrar o momento (`--from-state` encadeia). Sintaxe de macro: `references/cli.md`;
   - inviável sozinho → peça `./fab play <jogo>` + Shift+F1 e rode `./fab state import <jogo> <nome> --slot 1`.
   - States de snes9x/bsnes/BizHawk/RetroArch não servem no MesenCE.
4. **Achar a RAM** (dinâmico primeiro): `./fab ram search` → `./fab ram query <run> --unchanged 0:19 --changed 19:30`
   → confirme com `./fab run <jogo> --state <s> --macro … --watch nome=7E:xxxx:2s` (gera `trace.png`).
5. **Achar o código**: `./fab probe writes|reads|exec …` e depois `./fab re cdl` → `re analyze` → `re func|xrefs|
   search|decompile`. Cite o `evidence_id` de cada fato (protocolo: **snes-mod-cycle**, parte A).
6. **Escrever o mod**: `./fab mod new <id> --game <jogo> --goal "<o que se deve VER e medir>"`; edite `mod.json`
   (cenários: state, macro, frames, watch, checks — modelo: `mods/testbed-double-jump/`) e `patch.asm`. Sempre um
   cenário de **regressão**. Pedido de cor/roupa/sprite/retrato/HUD/desenho → **snes-sprite-paint** (os comandos
   `fab paint`/`fab gfx` geram o `.asm`, o `org`, `data[]` e `hijacks[]`).
7. **Ciclo**: **snes-mod-cycle**, parte B (`fab cycle run` → olhar as imagens → `fab cycle verdict`) até
   `objetivo-cumprido`. Copie o `compare.png`/`trace_compare.png` de cada ciclo para `games/<jogo>/prints/`.
8. **Entrega**: `build/<id>/<id>.bps` (aplica com Flips/beat ou `./fab bps <rom> <bps> <saída>`), `patch.asm`,
   `cycles/<id>/…/report.md`; se a ROM cresceu, repasse ao usuário o `rom_expandida` do build (emuladores que a
   rodam). Atualize `notes.md`, a skill `rom-<jogo>` (Estado, Como continuar, Avanços) e a CoALA. Ao parar no meio,
   o mesmo: a skill do jogo tem de bastar para outra sessão continuar.

## `mod.json` — critérios (`checks`)
Expressões sobre os traços de RAM do cenário (mod) e da base (mesmo state/macro):
`min(y) < baseline.min(y) - 320` · `count(edges(vy < -60)) >= 2` · `last(air) == 0` · `all(x == baseline.x)` ·
`any(pressed('B') & (air == 1))` · `at(lives, 300) == at(lives, 0)`.
Funções: min max mean sum abs len first last at window delta changes count any all edges falls argmin argmax
pressed clip. `watch`: `nome=BB:AAAA[:1|2|4][s]` (s = com sinal); PPU com prefixo e offset em bytes:
`cgram:01D2:2` (cor n = bytes 2n), `vram:`, `oam:`. Os checks medem o objetivo: nunca os enfraqueça para passar.

## Vídeos e imagens do usuário
Arquivos em `media/inbox/` → `./fab media inbox` (ou `./fab media analyze <arquivo|pasta> [--at 1.5,2.0]`): folhas de
contato, cortes de cena e `motion.png`. Leia com Read; detalhes em `references/video.md`. Duas runs lado a lado:
`./fab media compare <runA> <runB>`.

## Quando chamar o usuário (só bloqueio real)
ROM ausente/corrompida; impossível chegar sozinho ao momento do jogo; pedido ambíguo que muda o design ("mais rápido"
— andar? correr?); `fab doctor` falha e `fab setup` não resolve. O resto: decida e registre no relatório.

## FAQ
- **A ROM pode ser modificada?** Nunca: `roms/<id>/<id>.sfc` é só leitura; o Asar trabalha numa cópia em `build/<mod>/`.
- **O que nunca vai para o git?** ROMs, states, builds, BPS, frames/vídeos e prints de jogo comercial (`fab doctor` confere).
- **Qual frame mostra a lógica de qual?** O frame N mostra o estado da lógica do N-1 (OAM enviada no NMI); 256x224.
- **O jogo tem chip (S-DD1, SA-1…).** O `fab rom add` detecta e o `rom.py` conhece os mapas. Gráfico comprimido muda
  sem codec com `fab gfx override` (skill **snes-sprite-paint**).
- **ROM sem espaço livre.** `"expand_to"` no `mod.json` ou `fab gfx override --expand`; o build lista os emuladores
  que rodam a ROM maior (`rom_expandida`).

Referências: `references/cli.md` (todos os comandos) · `references/snes-ref.md` (memória, registradores, chips,
ROM expandida) · `references/video.md` (análise visual) · `references/skill-de-jogo.md` (skill do jogo + prints).
