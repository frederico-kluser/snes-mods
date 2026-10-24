# `fab` — referência de comandos

Wrappers na raiz: `./fab` (Git Bash), `.\fab.ps1` (PowerShell), `fab.cmd` (cmd). Na primeira execução
criam a `.venv` (numpy, Pillow, matplotlib). Códigos de saída: 0 ok · 1 falha operacional · 2 uso ·
3 dependência ausente. Erros saem como `Erro: <o quê> — Solução: <o que fazer>`.

Endereços: `BB:AAAA` (`80:A420`, `7E:007D`), `$BBAAAA` ou `0xBBAAAA`. WRAM aceita os espelhos
(`00:0072` ≡ `7E:0072`). Offsets de arquivo só com `--pc`.

## Setup e saúde
| comando | o que faz |
|---|---|
| `fab setup [--force] [--no-rea] [--no-testbed]` | baixa (sha256), extrai e configura JDK 21, Ghidra 12.1.4, MesenCE 2.2.1, Asar 1.91, ffmpeg; compila e instala o ghidra-snes; settings do Mesen; REA local + `.mcp.json`; testbed |
| `fab doctor [--quick] [--rea]` | verifica tudo (inclui smoke test headless, ROMs fora do git e, com `--rea`, o provedor Ghidra do REA) |
| `fab testbed` | remonta a ROM homebrew de teste e o state `parado` |
| `fab selftest [--quick]` | testes unitários + ponta a ponta |

## ROMs e endereços
| comando | o que faz |
|---|---|
| `fab rom add <rom> --id <slug> [--force] [--note]` | registra: remove cabeçalho SMC, detecta LoROM/HiROM/ExHiROM/SA-1, base limpa só leitura em `roms/<id>/<id>.sfc`, `games/<id>/game.json` + `notes.md` |
| `fab rom info <jogo>` / `fab rom list` | metadados / jogos registrados |
| `fab addr <jogo> <endereço>` | classifica (ROM/WRAM/MMIO) e converte para offset; `--pc 0x2420` faz o inverso |
| `fab disasm <jogo> <BB:AAAA> [--count N] [--flags m8,x16] [--rom build/…]` | desmontagem linear 65816 com SEP/REP rastreados |

## Savestates e emulador
| comando | o que faz |
|---|---|
| `fab play <jogo> [--rom …]` | abre o MesenCE (GUI). Shift+F1..F10 salva slots; F1..F10 carrega |
| `fab state import <jogo> <nome> --slot N` | importa o slot salvo no `fab play` (`tools/mesen/SaveStates/<jogo>_<N>.mss`) |
| `fab state import <jogo> <nome> --file x.mss` | importa um .mss qualquer do Mesen/MesenCE |
| `fab state boot <jogo> <nome> [--macro …] [--frames N] [--from-state s]` | cria state headless (power-on ou a partir de outro state + macro) e gera folha de pré-visualização |
| `fab state list <jogo>` | states com nota/origem |
| `fab run <jogo> [--state s] [--macro …] [--frames N] [--watch n=7E:0096:2s]… [--probe exec:80:A420]… [--every K] [--wram-every K] [--mod id \| --rom …] [--label …] [--no-video]` | cenário headless → `runs/<run>/`: `frames/f*.png`, `video.mp4`, `sheet.png`, `trace.csv`/`trace.png`, `probes.jsonl` |

## Investigação dinâmica (MesenCE headless)
| comando | o que faz |
|---|---|
| `fab probe writes <jogo> 7E:xxxx [--end …] --state s --macro … --frames N` | quem escreve: agrupa por instrução (reconstruída a partir do PC seguinte), valores, frames, M/X |
| `fab probe reads …` | idem para leituras |
| `fab probe exec <jogo> 80:A420 …` | execuções no endereço com M/X/E e registradores reais (auditoria de hijack) |
| `fab ram search <jogo> --state s --macro … --frames N [--every 1]` | grava a WRAM inteira a cada N frames |
| `fab ram query <run> [--changed A:B] [--unchanged A:B] [--increased A:B] [--decreased A:B] [--equals F=V] [--word] [--game g]` | filtra candidatos (estilo cheat search); frames são do cenário |

## Investigação estática (Ghidra 12.1.4 + ghidra-snes, headless)
| comando | o que faz |
|---|---|
| `fab re cdl <jogo> --state s [--macro …] [--frames 3600]` | roda o cenário e acumula o Code/Data Log (código executado + M/X por instrução) em `work/ghidra/<jogo>/cdl.bin` |
| `fab re analyze <jogo>` | importa a base limpa (loader SNES), semeia vetores + entradas do CDL com o contexto M/X/E, auto-análise, exporta TSVs |
| `fab re funcs <jogo> [--pattern] [--limit]` | funções (mais chamadas primeiro) |
| `fab re func <jogo> <addr>` | função que contém o endereço: instruções com m8/m16·x8/x16, chamadores, chamadas, SEP/REP |
| `fab re xrefs <jogo> <addr>` | referências (com espelhos de WRAM) + operandos direct page/absolutos que batem |
| `fab re search <jogo> "<regex>"` | regex sobre `mnemônico operandos` (ex.: `"STA.*0x7d"`) |
| `fab re decompile <jogo> <addr>…` | pseudocódigo C (aproximação: cruze com `re func`) |
| `fab re evidence <jogo> [<evidence_id>]` | livro-razão de evidências (`work/evidence/<jogo>.jsonl`) |

## Mods, build e ciclo
| comando | o que faz |
|---|---|
| `fab mod new <id> --game <jogo> [--title] [--goal]` | cria `mods/<id>/` (mod.json, patch.asm, macro, README) |
| `fab mod list` | mods |
| `fab build mods/<id>` | cópia da base limpa (+`expand_to`) → Asar (`--fix-checksum=on --symbols=wla`) → regiões alteradas, verificação de hijack, labels, BPS |
| `fab cycle run mods/<id> [--note "hipótese"]` | build → baseline (cache) → mod → comparação visual/RAM → checks → pontuação → veredito automático → ledger + `report.md` |
| `fab cycle verdict mods/<id> <evoluiu\|regrediu\|igual\|objetivo-cumprido\|inconclusivo> [--cycle N] --notes "…"` | veredito visual do agente (append-only) |
| `fab cycle status mods/<id>` | histórico do ledger |

## Mídia
| comando | o que faz |
|---|---|
| `fab media inbox` | processa arquivos novos em `media/inbox/` |
| `fab media analyze <vídeo\|imagem\|pasta> [--n 16] [--scene 0.25] [--at 1.5,2.0]` | ffprobe, frames uniformes + cortes de cena, `motion.png`, folhas de contato |
| `fab media compare <runA> <runB> [--title]` | folha lado a lado + diferença + traços |
| `fab bps <rom> <patch.bps> <saída>` | aplica BPS (remove cabeçalho SMC da origem se houver) |

## Macros
Uma linha = `<frames> [Botão+Botão]`; `#`/`;` comentam; `Nx a / b` repete grupos.
Na linha de comando use `;` para separar linhas: `--macro "20;1 B;18;1 B;100"`. Arquivo `.txt` também vale.
Botões: `A B X Y L R Start Select Up Down Left Right`.
```
30              # 30 frames sem botões
1 B             # 1 frame com B (o jogo vê "B pressionado agora")
12 Right+B      # 12 frames segurando →+B
3x 1 A / 10 -   # (1 frame A, 10 frames nada) × 3
```
Dica: muitos jogos detectam "pressionou agora" por borda → separe dois toques com ≥1 frame sem o botão.

## Arquivos de uma run (`runs/<data>-<tipo>-<rótulo>/`)
`job.json` (o que rodou) · `result.json` (status, frames, hits, sha1 da ROM) · `harness.log` ·
`trace.csv` (frame, input, watches) · `probes.jsonl` · `frames/fNNNNN.png` (256x224) · `video.mp4`
(2x, 60/every fps) · `sheet.png` · `wram.bin` (busca de RAM) · `cdl.bin`.
