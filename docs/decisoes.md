# Decisões de arquitetura (ADRs)

O que se decidiu, por quê e como se confere. Cada decisão aponta para o teste, o comando ou o arquivo que a sustenta;
o código e o estado atuais continuam sendo a verdade. Data = quando a decisão entrou.

## ADR-01 — Windows nativo e toolchain fixado com sha256 (2026-10-24)

- **Decisão**: tudo roda nativo no Windows x64. O `fab setup` baixa as ferramentas de
  [`tools/manifest.json`](../tools/manifest.json) (URL, versão e sha256) para `tools/`, fora do git, e compila o
  ghidra-snes. Python 3.12+ numa `.venv` com dependências fixadas com hash (`pip-compile`: `requirements.in` →
  `requirements.txt`); o CI instala com `--require-hashes` (matriz 3.12/3.13/3.14).
- **Por quê**: instalação reprodutível e conferível; pisos `>=` soltos geravam alertas OSV no Scorecard.
- **Verificação**: `fab doctor` (cada ferramenta e versão) e o CI. Um comando para tudo: ADR-19.

## ADR-02 — Emulador: MesenCE headless com harness Lua (2026-10-24)

- **Problema**: o ciclo precisa de emulação determinística, sem janela, com RAM, PPU e savestates. O Mesen2 foi
  arquivado em 2026-06.
- **Decisão**: MesenCE 2.2.1 em `--testRunner` com [`lua/harness.lua`](../lua/harness.lua) (state, macro de input,
  frames, RAM, sondas com M/X, CDL, PPU, falsa cor, log de DMA). Config portátil em `tools/mesen/settings.json`: Lua
  com I/O, RAM inicial zerada e `Snes.DisableFrameSkipping=true`.
- **Armadilhas medidas**: sem `DisableFrameSkipping` as capturas atrasam 1-5 frames em relação à RAM; savestate só
  carrega/salva dentro de callback de execução da CPU (o harness cuida); `emu.takeScreenshot` vem vazio no
  testRunner (usa-se `emu.getScreenBuffer`); o frame N mostra a lógica do frame N-1; o state não confere o hash da
  ROM (o state da ROM limpa roda no mod); states de outros emuladores não servem.
- **Verificação**: `tests/test_e2e.py::test_capture_aligned_with_ram` e o smoke headless do `fab doctor`.

## ADR-03 — Lane estático: Ghidra + ghidra-snes; o REA fica para outros alvos (2026-10-24)

- **Problema**: o REA 6.7.0 não abre ROM de SNES (`unsupported binary format`; o modo cru só aceita
  6502/x86/x86_64/arm/arm64/m68k; o 65816 está no PR morluto/rea#4911).
- **Decisão**: `fab re` = Ghidra 12.1.4 headless + ghidra-snes (commit `d33ce5d`), recompilado contra o 12.1.4
  porque só há release para o 12.0.4. O loader não segue os vetores: `ghidra_scripts/SnesSeedAndAnalyze.java`
  semeia vetores + entradas de sub-rotina do CDL do MesenCE com o M/X/E reais. O Ghidra não cria referência para
  operando direct page: `fab re xrefs` completa com busca textual. O REA continua instalado só neste projeto
  (`tools/rea`, `.mcp.json` gerado pelo `fab setup`) para PE/ELF/JS e afins.
- **Verificação**: `fab doctor` (`ghidra-snes (65816:LE:24:snes)`; com `--rea`, o provedor Ghidra do REA).

## ADR-04 — Evidência antes de patch (2026-10-24)

- **Decisão**: cada endereço de um patch tem `evidence_id`: um registro com perfil da análise, resultado normalizado
  e limitações, gerado por `fab probe` (writes/reads/exec, com a instrução reconstruída e o M/X reais), `fab ram`
  (search/query) ou `fab re` (func/xrefs/decompile). Observação ≠ inferência ≠ incógnita. Os ids são determinísticos
  para as mesmas entradas (`fab re evidence <jogo> <id>` mostra o registro).
- **Verificação**: a tabela de evidências de [`mods/testbed-double-jump/README.md`](../mods/testbed-double-jump/README.md).

## ADR-05 — Portões do build (2026-10-24, ampliados em 2026-10-25)

- **Decisão**: o Asar trabalha numa cópia em `build/<mod>/`; a ROM original e `roms/<id>/<id>.sfc` são só leitura.
  O `fab build` recusa hijack sem M/X verificado (`mod.json → hijacks[]` com `evidence`), hijack que não cobre
  instruções inteiras (JML/JSL de 4 bytes, sobra com NOP, sem desvio para dentro, retorno em fronteira), sobrescrita
  não declarada, operando órfão e imediato com tamanho errado para o M/X do ponto (aponta arquivo:linha — `A9 08 00`
  com M=8 executa o `00` como BRK). Regiões de dados declaradas em `data[]`, com evidência, ganham do espaço livre.
  `freecode` só usa os bancos $10-$3F (ROM < 1 MB precisa de `expand_to`). Distribui-se o `.bps` e o `patch.asm`.
- **Verificação**: `tests/test_sprites.py` (`test_imediato_de_16_bits_com_m8_e_acusado`, `OamMirrorGeneratorTests`)
  e `tests/test_unit.py` (`DataRegionTests`, `BpsTests`).

## ADR-06 — Ciclo autônomo com ledger e veredito duplo (2026-10-24)

- **Decisão**: `fab cycle run mods/<id>` monta o mod, roda mod × base com o mesmo state e o mesmo macro, grava
  frames, vídeo e traços de RAM, mede o M/X no hijack, avalia os checks do `mod.json` (pontuação) e dá o veredito
  automático (evoluiu/regrediu/igual; build quebrado = falhou ou regrediu). Tudo vai para `cycles/<id>/ledger.jsonl`
  (só se acrescenta) e `cycle-NNN/report.md`. O veredito visual é do agente: `fab cycle verdict …`
  (`objetivo-cumprido`, `evoluiu`, `regrediu`, `igual`, `inconclusivo`).
- **Pronto** = todos os checks ✅ + imagens conferidas + regressão com 0 frames divergentes. Limite `max_cycles`
  (padrão 8); três ciclos seguidos sem evolução param o loop e reportam o melhor ciclo.
- **Verificação**: `tests/test_e2e.py::test_cycle_detects_evolution_and_regression`; `fab cycle run
  mods/testbed-double-jump` (6/6 checks, regressão 0/35 frames divergentes).

## ADR-07 — Mod com código compara contra a base variante (2026-10-25)

- **Problema**: todo hook muda o timing da CPU e o RNG muda junto. No SFA2 a luta jogava diferente da ROM limpa já
  no frame 1, e o ciclo 4 do mod das luvas deu 21/46 sem defeito no patch.
- **Decisão**: `mod.json → baseline.variant` monta o MESMO patch com a mudança desligada por valor (`defines`) e usa
  essa ROM como base; o relatório mede a sincronia mod × variante (bytes da WRAM que diferem) e acusa quando a
  variante não serve de base. Mod só de dados continua contra a ROM limpa.
- **Verificação**: linha "sincronia mod × variante" do `report.md` de cada ciclo (`snesfab/cycle.py`).

## ADR-08 — Warmup de medição e watch do PPU (2026-10-25)

- **Problema**: o savestate traz estado já resolvido — no SFA2 a paleta do lutador só é relida da ROM a cada ~70
  frames, então um mod de cor só aparece na CGRAM depois da 1.ª recarga.
- **Decisão**: `warmup` por cenário (`mod.json → scenarios[].warmup`, `fab run --warmup`) roda N frames antes de
  medir; watches de memória de vídeo (`cgram:`, `vram:`, `oam:`).
- **Verificação**: `tests/test_e2e.py::test_warmup_starts_measurement_late`, `tests/test_unit.py::JobTests` e
  `SerializationTests::test_watch_ppu`.

## ADR-09 — Mapas de memória pelo hardware (2026-10-24/25)

- **Decisão**: S-DD1 = LoROM fixa só dos 2 primeiros MiB em `$00-$3F/$80-$BF:8000-FFFF` e janelas de 1 MiB em
  `$C0-$FF` (`$4804-$4807`); o SFA2 executa em `$C0:xxxx` com DBR=`$BF` (sondas de MMIO no banco `$BF`). SA-1 segue o
  MMC padrão como o `sa1rom` do Asar (ainda não validado com ROM SA-1 real). `fab addr` converte e classifica;
  `pc_to_snes` recusa offset fora do mapa. ROM expandida: o `fab build` lista em `rom_expandida` os emuladores que a
  rodam (S-DD1 acima de 4 MiB: MesenCE/Mesen2 e bsnes; snes9x só abaixo de 8 MiB).
- **Verificação**: `tests/test_unit.py::RomTests` (`test_sdd1_mmc_padrao`, `test_sa1_como_o_asar`,
  `test_lorom_hirom_exhirom`). O erro do SA-1 foi achado pelo fuzzing (ADR-16).

## ADR-10 — Pintura de sprites só com imagens numeradas e texto (2026-10-25)

- **Problema**: mudar cor, parte ou desenho de sprite exigia vídeo e investigação manual; o dono quer que LLMs mais
  fracas façam isso em qualquer ROM.
- **Decisão**: kit genérico (skill `snes-sprite-paint`): `fab ppu dma` (de onde vêm paleta, OAM e gráficos),
  `fab sprite snap` (render do OAM + falsa cor + snapshot do PPU → objetos numerados, índices e origem da paleta na
  WRAM/ROM), `fab palette ramp`, `fab paint set|remap|oam-mirror` e `fab paint check` (píxeis antes × depois e
  orçamento do VBlank). A paleta de sprite é a linha p+8 da CGRAM — medida, nunca deduzida.
- **Verificação**: `tests/test_sprites.py` e os e2e `test_sprites_render_e_falsa_cor_batem_com_a_tela`,
  `test_paint_set_build_e_check` e `test_oam_mirror_nivel2_gera_monta_e_cabe_no_vblank`.

## ADR-11 — Gráfico comprimido sem codec (2026-10-25)

- **Problema**: gráfico comprimido (S-DD1 ou formato do jogo) pediria um descompressor, e a regra de descoberta
  própria (ADR-12) proíbe usar o de terceiros.
- **Decisão**: `fab gfx dump` exporta o tileset pelo que cada DMA deixou na VRAM (já descomprimido); `fab gfx
  override` serve o desenho editado no próprio disparo do DMA (`STA/STX/STY $420B`): cópia crua + tabela de 24 B por
  bloco, impressão digital de 8 B para fonte na WRAM, `--chip-disarm` para chip que descomprime no DMA (o hook devolve
  DMAP e fonte depois) e `--expand` para ROM cheia; `fab gfx check` confere na VRAM.
- **Verificação**: e2e `test_gfx_dump_exporta_o_tileset` e `test_gfx_override_serve_o_desenho_editado_sem_codec`,
  `tests/test_sprites.py::GfxOverrideTests`; no SFA2, ROM de 5 MiB, 35 tiles e 0 colaterais.

## ADR-12 — Regra de descoberta própria (2026-10-25, regra do dono)

- **Decisão**: nada de solução pronta de terceiros — descompressores, tabelas de streams, ferramentas de ROM-hacking
  feitas para o jogo, patches alheios. Podem ser citados como referência; tudo o que entra num patch ou numa conclusão
  sai da nossa evidência (sondas, desmontagem, leitura da ROM, píxeis da tela). O toolchain genérico (emulador,
  Ghidra, Asar) é ferramenta, não solução.
- **Contexto**: a investigação do SFA2 chegou a usar o toolchain de um projeto de terceiros para o mesmo jogo; foi
  apagado a pedido do dono e os fatos úteis foram rederivados com as nossas ferramentas.
- **Verificação**: seção "Regra de descoberta própria" do [README](../README.md); cada fato com `evidence_id` (ADR-04).

## ADR-13 — Uma skill por jogo e pasta de prints (2026-10-25, pedido do dono)

- **Decisão**: cada jogo analisado ganha a skill `rom-<jogo>` (`.agents/rom-<jogo>/SKILL.md` + links em
  `.claude/skills/` e `.agents/skills/`), pelo modelo `.agents/snes-mod-factory/references/skill-de-jogo.md`, e a
  pasta `games/<id>/prints/` (ignorada pelo git) com prints numerados e um `LEIA-ME.txt` — é por ela que o dono
  acompanha. Ao parar, a skill é reescrita (Estado, Como continuar, Avanços).
- **Verificação**: o `fab doctor` falha se algum print for versionado.

## ADR-14 — Skills enxutas (2026-10-25)

- **Decisão**: entrada = `snes-mod-factory`; código 65816 + ciclo = `snes-mod-cycle` (a antiga `snes-rea-modder`
  foi fundida nela); pintura = `snes-sprite-paint`; píxeis = `pixel-peep`; jogo = `rom-<jogo>`; memória =
  `snes-mods-coala-agent-skill`. Textos compactos com FAQ; `CLAUDE.md` e `AGENTS.md` espelhados para qualquer agente.

## ADR-15 — Memória CoALA versionada (`track-dump`) (2026-10-26)

- **Problema**: a base CoALA (SQLite) era local e ignorada pelo git; num clone novo ou noutra máquina sumia o que os
  agentes aprenderam (decisões, armadilhas, receitas).
- **Decisão**: política `track-dump` do instalador da coala-agent-skill — `coala.sqlite` continua fora do git e
  versiona-se `memory/coala.canonical.jsonl`. `fab memory dump` sincroniza (docs + código) e exporta (determinístico,
  segredos mascarados, sempre LF); `fab memory restore` recria a base num clone novo (init + import + sync);
  `fab memory status` e o `fab doctor` acusam dump desatualizado ou sync pendente.
- **Armadilha resolvida**: o `import` do motor anota em cada registro "Importado de <caminho local> (linha N) em
  <data>"; o dump seguinte levaria o caminho da máquina para o git público e reescreveria todos os registros. O
  `restore` devolve aos registros que importou a proveniência exata do dump — um clone restaurado exporta o mesmo
  arquivo, byte a byte.
- **Antes de versionar**: o dump foi auditado — só fontes versionadas, nenhum e-mail, token ou caminho local.
- **Verificação**: `tests/test_memory.py` (dump em dia, CRLF, restore byte a byte, `--force` só mexe no que importou,
  dump versionado íntegro e sem caminho local) e o `fab doctor` (recusa `.sqlite` versionado).

## ADR-16 — Robustez: FabError e fuzzing contínuo (2026-10-24)

- **Decisão**: entrada malformada (macro, critérios, BPS, ROM) vira `FabError` — `Erro: … — Solução: …` e exit code
  0/1/2/3, nunca stack trace. Os parsers rodam sob fuzzing (atheris no CI Linux; no Windows, corpus + mutações) e cada
  crash corrigido vira teste de regressão; foi assim que apareceu o erro do mapa SA-1 (ADR-09).
- **Verificação**: `tests/fuzz/fuzz_{bps,checks,macro,rom}.py`, `.github/workflows/fuzz.yml`,
  `tests/test_unit.py` (`ChecksTests::test_sandbox`, `BpsTests::test_patch_malformado`).

## ADR-17 — Publicação aberta com a governança da opensource-project (2026-10-24)

- **Decisão**: licença MIT; rulesets como código em `.github/rulesets/` (`main` com PR, squash, check `build`
  estrito e histórico linear; branches `<tipo>/<slug>`; tags `v*` imutáveis); Conventional Commits no hook local e
  no job `build`; release-please (começa em 0.1.0) gera versão e `CHANGELOG.md`; actions fixadas por SHA com
  `permissions` mínimas; CodeQL, Scorecard e dependency review. PR com 0 aprovações enquanto houver um mantenedor (o
  GitHub não deixa aprovar o próprio PR).
- **Verificação**: `oss-doctor.sh` da opensource-project; Scorecard 7,4 em 2026-10-24.

## ADR-18 — Nada de material comercial no git (2026-10-24)

- **Decisão**: ROMs, savestates, builds, BPS, frames, vídeos e prints de jogo comercial ficam fora (`.gitignore`) e
  o `fab doctor` falha se algo assim for versionado; distribui-se `patch.asm` e/ou `.bps`. Para ter exemplo sem ROM
  comercial, a ROM homebrew [`fixtures/testbed/`](../fixtures/testbed/testbed.asm) põe a rotina de pulo nos
  endereços do guia e treina pintura e override com gráficos crus e "comprimidos" (montados na WRAM). Créditos e
  licenças de terceiros: [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).
- **Verificação**: `fab doctor` ("git sem ROMs/states/prints/base") e `fab selftest`.

## ADR-19 — Bootstrap de um comando (2026-10-26)

- **Decisão**: [`bootstrap.ps1`](../bootstrap.ps1), idempotente e sem admin: Python 3.12+ (winget no escopo do
  usuário se faltar), `.venv` + `requirements.txt` com hash, `fab memory restore` num clone novo, `fab setup`
  (`-SkipTools`, `-NoRea`), `fab doctor` e, com `-SelfTest`, `fab selftest`. Salvo com BOM UTF-8: o Windows
  PowerShell 5.1 lê script sem BOM pela página de código ANSI do sistema e estragaria os acentos.
- **Verificação**: rodado num clone novo em 2026-10-26 — memória restaurada idêntica ao dump.

## Desvios em relação ao guia original

| Guia | Aqui | Motivo |
| --- | --- | --- |
| Mesen2 | MesenCE 2.2.1, headless com harness Lua | o Mesen2 foi arquivado em 2026-06 (ADR-02) |
| REA para analisar a ROM | Ghidra + ghidra-snes via `fab re` | o REA 6.7.0 não abre ROM de SNES (ADR-03) |
| ghidra-snes da release | recompilado contra o Ghidra 12.1.4 | só há release para o 12.0.4 (ADR-03) |
| análise automática do loader | sementes = vetores + CDL do MesenCE | o loader não segue os vetores (ADR-03) |
| o processo termina no build | ciclo no emulador contra a base, com critérios, imagens e ledger | ADR-06 |
