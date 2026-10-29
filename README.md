# snes-mods — fábrica de mods de Super Nintendo com agentes

<p align="center">
  <a href="https://github.com/frederico-kluser/snes-mods/actions/workflows/ci.yml"><img src="https://github.com/frederico-kluser/snes-mods/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/frederico-kluser/snes-mods/actions/workflows/codeql.yml"><img src="https://github.com/frederico-kluser/snes-mods/actions/workflows/codeql.yml/badge.svg" alt="CodeQL"></a>
  <a href="https://securityscorecards.dev/viewer/?uri=github.com/frederico-kluser/snes-mods"><img src="https://api.securityscorecards.dev/projects/github.com/frederico-kluser/snes-mods/badge" alt="OpenSSF Scorecard"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="Licença: MIT"></a>
  <a href="https://www.conventionalcommits.org/"><img src="https://img.shields.io/badge/Conventional%20Commits-1.0.0-fe5196.svg" alt="Conventional Commits"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-3776AB.svg" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/plataforma-Windows%20x64-0078D6.svg" alt="Windows x64">
</p>

> **English summary** — An agent-driven factory for Super Nintendo (SNES) ROM hacks. Hand it a ROM and a goal: it
> reverse-engineers the game (headless MesenCE emulation with Lua probes + Ghidra/ghidra-snes), writes the 65816
> patch with Asar and runs an **autonomous evolution loop** that replays a savestate on the original and the modded
> ROM, records frames, video and RAM traces, scores objective checks and decides whether the mod improved. Sprite
> recoloring and redrawing work from numbered images and text alone — including compressed graphics, without the
> codec. Built for Claude Code (skills + CoALA memory), usable by any coding agent through the `fab` CLI.
> Documentation is in Portuguese.

Você passa a ROM e diz o que quer. O agente registra a ROM, investiga o jogo no emulador e no Ghidra, escreve o patch
em assembly 65816 (Asar) e entra num **ciclo autônomo**: roda o emulador headless a partir de um savestate, grava
frames/vídeo/RAM do mod e da ROM original, compara, avalia critérios objetivos, olha as imagens e decide se houve
evolução — até cumprir o objetivo.

<p align="center">
  <img src="docs/img/pulo-duplo.gif" alt="ROM original à esquerda e, à direita, a mesma ROM com o patch de pulo duplo: o bloco sobe bem mais alto ao apertar B no ar" width="518">
</p>
<p align="center"><sub>Ciclo real sobre a ROM de teste do repositório: mesmo savestate e mesmos inputs; à direita, o patch de pulo duplo.</sub></p>

## Como funciona

```
 ROM + pedido ──► fab rom add ──► savestate (fab state boot | fab play + import)
                                       │
          ┌──────────── investigação ──┴──────────────────────────┐
          │ dinâmico: MesenCE --testRunner + harness Lua          │
          │   fab ram · fab probe · fab ppu dma · fab sprite snap │
          │ estático: Ghidra 12.1.4 + ghidra-snes (fab re)        │
          └──────────────── evidence_id ──────────────────────────┘
                                       │
          mods/<id>/patch.asm + mod.json (cenários + checks)   ← à mão ou gerado:
                                       │                         fab paint · fab gfx override
        ┌──────────── fab cycle run (skill snes-mod-cycle) ─────────────┐
        │ Asar numa cópia → base × mod, mesmo state/macro               │
        │ frames · vídeo · traços de RAM · M/X · orçamento de VBlank    │
        │ compare.png · checks → pontuação → veredito (auto + visual)   │
        └──────────── repete até objetivo-cumprido ─────────────────────┘
                                       │
                        build/<id>/<id>.bps + relatório
```

## Começo rápido

Requisitos: Windows 10/11 x64, Python 3.12+, Git (e Node.js ≥ 22.19 só para o MCP do REA).

```bash
git clone https://github.com/frederico-kluser/snes-mods.git && cd snes-mods
./fab setup     # baixa e confere (sha256) o toolchain pinado em tools/manifest.json (~1 GB)
./fab doctor    # tudo OK?
./fab selftest  # testes unitários + ponta a ponta no emulador headless
```
No PowerShell use `.\fab.ps1`; no cmd, `fab.cmd`. O toolchain fica em `tools/` e as dependências numa `.venv` (fora do git).
Ou tudo de uma vez — Python, `.venv`, memória do projeto, toolchain, doctor e testes:
`powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 -SelfTest`.

Uso: abra o Claude Code na pasta e peça, por exemplo, *"Aqui está a ROM `D:\roms\MeuJogo.sfc`. Quero que o personagem
pule mais alto"* ou *"deixa a roupa do personagem azul"*. Se tiver, passe um savestate `.mss` do Mesen/MesenCE no
momento que interessa (senão o agente chega lá sozinho com `fab state boot`). Vídeos e prints vão em `media/inbox/`.
O agente entrega o `.bps`, o `patch.asm` e o relatório dos ciclos. Comandos: `./fab --help` e
[`cli.md`](.agents/snes-mod-factory/references/cli.md).

## Skills

| skill | para quê |
|---|---|
| `snes-mod-factory` | entrada de qualquer pedido: ROM → savestate → investigação → mod → entrega |
| `snes-mod-cycle` | patch 65816 (evidência, M/X, hijack de 4 bytes, Asar, portões do build) + o ciclo de evolução |
| `snes-sprite-paint` | cor, parte de sprite, desenho de tiles (crus ou comprimidos), tileset — só com imagens numeradas e texto |
| `pixel-peep` | ler/conferir pixel-art: mapa de índices ampliado, varinha, verificação antes × depois pixel-perfect |
| `rom-<jogo>` | diário de cada jogo analisado (fatos com evidência, states, estado dos mods, como continuar) — ex.: `rom-street-fighter-alpha` |
| `snes-mods-coala-agent-skill` | memória e catálogo locais do projeto (CoALA) |

Recomendada (externa): [`grid-layout`](https://github.com/frederico-kluser/grid-layout) — a disciplina de grelha
rotulada + partição exata + sondas determinísticas que separou luva × cabelo no SFA2 (o motor dela, HTML/Chromium,
não tem alvo aqui; detalhes em [`mods/sfa2-ken-azul-e-rosa/README.md`](mods/sfa2-ken-azul-e-rosa/README.md)).

## Regra de descoberta própria (não negociável)

**Não se usam projetos de terceiros que já tragam a solução pronta** — descompressores, tabelas de streams,
ferramentas de ROM-hacking, patches de outros. É roubar. Tudo o que entra num patch ou numa conclusão sai da
**nossa** evidência: sondas do emulador (`fab probe`/`ram`), desmontagem e leitura direta da ROM (`fab disasm`,
`fab re`), extração de píxeis pela própria tela (`fab sprite snap`, skill `pixel-peep`) e o que a RAM/VRAM mostra em
execução. Ferramentas externas podem ser **citadas** como referência, mas nunca como fonte dos valores que vão para
os patches. O que não se provar com `evidence_id` próprio não existe.

## Exemplo funcionando (sem ROM comercial)

[`fixtures/testbed/testbed.asm`](fixtures/testbed/testbed.asm) é uma ROM homebrew (LoROM, 1 MB) com um bloco que anda
e pula — a rotina de pulo fica **nos endereços do guia** (`$80:A41E–$80:A438`) — e gráficos crus e "comprimidos" (montados
na WRAM) para treinar pintura e override. [`mods/testbed-double-jump/`](mods/testbed-double-jump/) é o patch de salto
duplo do guia:

```
./fab cycle run mods/testbed-double-jump
→ 6/6 checks ✅ · hijack 80:A420 OK (JML $90:8008, 4 bytes, sem órfãos) · M/X dinâmico m8,x16 em 140/140
→ pulo duplo: imagens divergem a partir do f40 · regressão (pulo simples): 0/35 frames divergentes
```
<p align="center"><img src="docs/img/ram-pulo-duplo.png" alt="Traços de RAM: posição Y, velocidade Y, flag de ar e de pulo duplo, mod em vermelho e original em cinza, com a linha de inputs" width="760"></p>

## O que tem aqui

| caminho | o quê |
|---|---|
| `snesfab/` | a CLI `fab` (Python): ROM e mapas, emulação headless, PPU/sprites/paletas/gráficos, build Asar + BPS, ciclo, Ghidra |
| `lua/harness.lua` | roda dentro do MesenCE `--testRunner`: state, input, frames, RAM, sondas com M/X, CDL, PPU, falsa cor, log de DMA |
| `ghidra_scripts/` | sementes M/X + análise, export TSV e descompilação (headless) |
| `.agents/` | as skills acima (links em `.claude/skills/` e `.agents/skills/`) e a memória CoALA, versionada como dump (`fab memory dump\|restore\|status`) |
| `docs/decisoes.md` | decisões de arquitetura (ADRs): o que se decidiu, por quê e como se confere |
| `fixtures/testbed/` · `tests/` | ROM homebrew de teste · testes unitários, ponta a ponta e fuzzing (`tests/fuzz/`) |
| `mods/` · `games/` · `cycles/` | mods, notas por jogo e o histórico dos ciclos (sem material comercial) |
| `tools/manifest.json` | toolchain pinado com sha256 (instalado em `tools/`, fora do git) |

| ferramenta | versão | papel |
|---|---|---|
| MesenCE (sucessor do Mesen2) | 2.2.1 | emulador; `--testRunner` headless + Lua |
| Asar | 1.91 | montador 65816 (`--fix-checksum=on --symbols=wla`) |
| Ghidra + ghidra-snes (joshleaves, recompilado) | 12.1.4 · v1.3.0+2 | análise estática headless (LoROM/HiROM/ExHiROM/SA-1) |
| Temurin JDK · ffmpeg (gyan.dev) | 21.0.12.1 · 2026-10-22 | Ghidra · vídeo e frames |
| rea-agents (npm, `tools/rea`) | 6.7.0 | MCP do REA, só neste projeto (`.mcp.json`) |
| Python | 3.12+ (numpy, Pillow, matplotlib com hash) | CLI `fab` |

## FAQ

**Preciso de qual ROM?** Uma que você possui (o `fab rom add` remove cabeçalho SMC e detecta o mapa/chip). Para
testar sem ROM comercial: o testbed (`./fab testbed`).

**Por que MesenCE? Posso jogar o mod no snes9x/bsnes?** O ciclo precisa de emulação headless determinística com Lua
(MesenCE); savestates só servem nele. O `.bps` final roda em qualquer emulador. Se o mod **expandir a ROM**, o
`fab build` lista em `rom_expandida` quais emuladores a rodam (ex.: S-DD1 acima de 4 MiB: MesenCE/Mesen2 e bsnes;
snes9x só abaixo de 8 MiB).

**Dá para mudar o desenho de um sprite comprimido?** Sim, sem descompressor: `fab gfx dump` exporta o tileset pelo
que chega na VRAM e `fab gfx override` serve o desenho editado no próprio DMA (validado no testbed e num jogo com S-DD1).

**E se a ROM não tiver espaço livre?** `expand_to` no `mod.json` ou `fab gfx override --expand`; o build cuida do
cabeçalho e diz onde a ROM maior roda.

**O agente pode errar endereço e corromper a ROM?** O `fab build` recusa sobrescrita não declarada, hijack sem M/X
verificado, operando órfão e imediato com tamanho errado (aponta arquivo:linha) — e a ROM original nunca é tocada.

**Por que meu mod com código não passa nos checks contra a ROM limpa?** Todo hook muda o timing e o RNG do jogo. A
base de comparação passa a ser o próprio mod com a mudança desligada por valor (`baseline.variant`).

**Por que o REA não é usado na ROM?** O REA 6.7.0 não abre ROM de SNES (`unsupported binary format`; o 65816 está no
PR morluto/rea#4911). O lane estático é o Ghidra + ghidra-snes via `fab re`, com o mesmo contrato de evidência.

**Funciona com outro agente que não o Claude Code?** Sim: tudo é a CLI `fab` e as instruções estão em `AGENTS.md`
(espelho do `CLAUDE.md`).

**O que é versionado?** Código, skills, notas, mods (`patch.asm`, `mod.json`) e a memória CoALA (o dump
`coala.canonical.jsonl`; a base SQLite fica local e o `fab memory restore` a recria num clone novo). Nunca ROMs,
states, builds, BPS, frames, vídeos ou prints de jogos comerciais (`.gitignore` + `fab doctor`).

## Decisões
As decisões de arquitetura estão em [`docs/decisoes.md`](docs/decisoes.md), cada uma com a sua verificação — inclusive
os desvios em relação ao guia original: MesenCE no lugar do Mesen2 (arquivado em 2026-06), Ghidra + ghidra-snes
recompilado no lugar do REA (que não abre ROM de SNES) e o ciclo no emulador depois do build, onde o guia parava.

## Contribuindo · Segurança · Versionamento
Leia o [CONTRIBUTING.md](CONTRIBUTING.md) (ambiente, branches `<tipo>/<slug>`, Conventional Commits, testes) e o
[Código de Conduta](CODE_OF_CONDUCT.md); ideias em [Discussions](https://github.com/frederico-kluser/snes-mods/discussions).
Vulnerabilidades: [SECURITY.md](SECURITY.md) (Private Vulnerability Reporting), nunca em issue pública.
[SemVer](https://semver.org/lang/pt-BR/) a partir dos commits; o release-please mantém o PR de release e o [CHANGELOG.md](CHANGELOG.md).

## Legal, licença e créditos
Use apenas ROMs que você possui; para compartilhar um mod, distribua `patch.asm` e/ou o `.bps`. Código sob a licença
[MIT](LICENSE). O `fab setup` baixa das fontes oficiais, sem redistribuir: [MesenCE](https://github.com/nesdev-org/MesenCE)
(GPL-3.0), [Ghidra](https://github.com/NationalSecurityAgency/ghidra) (Apache-2.0), [ghidra-snes](https://github.com/joshleaves/ghidra-snes)
(MIT), [Asar](https://github.com/RPGHacker/asar) (LGPL-3.0/GPL-3.0/WTFPL), [ffmpeg](https://ffmpeg.org) (builds GPL da
gyan.dev), [Eclipse Temurin](https://adoptium.net) (GPL-2.0 com Classpath Exception) e [REA](https://github.com/morluto/rea)
(MIT). A memória CoALA (`.agents/snes-mods-coala-agent-skill`) vem da coala-agent-skill do mesmo autor, também MIT.
Versões, dependências Python e o que está (ou não) no repositório: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
