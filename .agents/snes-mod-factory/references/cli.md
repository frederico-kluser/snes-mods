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

`--watch` também lê a memória do PPU, com prefixo e offset em bytes: `n=cgram:01D2:2` (cor n da paleta =
bytes 2n e 2n+1; 256 cores = `$000-$1FF`), `n=vram:8000:2`, `n=oam:0000`. Para despejar a CGRAM inteira de
uma vez, gere 256 watches `cN=cgram:<2N>:2` (é o que revelou a paleta do Ken no SFA2).

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
| `fab build mods/<id>` | cópia da base limpa (+`expand_to`, +`blobs[]`) → Asar (`--fix-checksum=on --symbols=wla`) → regiões, portões (sobrescrita não declarada, hijack/M/X, tamanho de imediato), labels, BPS; ROM que cresceu → `rom_expandida` (emuladores que a rodam) |
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

## Pintura e mudança de sprites (qualquer jogo — guia passo a passo: skill `snes-sprite-paint`)
| comando | o que faz |
|---|---|
| `fab gfx dump <jogo> [--state s]… [--macro …] [--frames 600] [--bpp 4]` | export do tileset: cada upload para a VRAM (já descomprimido, guardado em `run-N/vram_uploads.*`) + o que já estava na VRAM; tiles únicos em `tiles-NN.png` com a origem (cru na ROM / comprimido por chip / montado na WRAM / já estava) e `tileset.md` |
| `fab gfx override mods/<id> --dump <dir> [--tiles 12,40-45 --map 14:9 --name … --evidence …] [--expand] [--data-at 0x… --data-evidence …] [--chip-disarm 00:4801=00]` | muda o DESENHO sem codec: cru → patch de dados; comprimido/WRAM → hook no disparo do DMA que serve a cópia editada (tabela + impressão digital), gera `gfx_override.asm` (+ blob) e `hijacks[]`/`data[]`/`blobs[]` |
| `fab gfx check mods/<id> --dump <dir>` | roda os cenários do dump na ROM do mod: o desenho novo chegou na VRAM, o velho sumiu, 0 colaterais |
| `fab ppu dma <jogo> [--state s] [--macro …] [--frames 60] [--mod id\|--rom …]` | log de cada DMA/HDMA: fonte (ROM/WRAM), destino (VRAM/OAM/CGRAM), instrução que dispara (PC + M/X) e se o gráfico é cru na ROM; `resumo` = buffer de paletas, sombra do OAM, origem dos gráficos |
| `fab sprite snap <jogo> --state s [--frames 60\|30,60\|0-120:10] [--mod id]` | duas runs (real + **falsa cor**) com snapshot do PPU: `overview.png` (sprites numerados), `bg.png` (áreas de BG B1…), `objN/bgN-indices.png` (um painel por índice), `palettes.png`, `report.md` (cores + paleta achada na ROM/WRAM) |
| `fab sprite report <captura> [--frame F]` | refaz as imagens de uma captura sem emular |
| `fab sprite regions <captura> --object N --indices a,b [--store parts.json]` | regiões conexas desses índices, numeradas |
| `fab sprite label <captura> --object N --indices a,b --regions 2,3 --part luva [--rest cabelo] --store …` | rótulo de peça por CONTEÚDO de tile (hash + píxel); `--pending <census> --items …` rotula pendentes |
| `fab sprite census <jogo> --store … --target luva [--state/--macro/--frames] [--engine] [--capture dir]` | cobertura dos rótulos em muitos frames, folhas de pendentes (deduplicados), sprites misturados e **nível de separabilidade** (1-4) com o mecanismo |
| `fab sprite tiles <captura> --object N [--indices] [--part --store]` | tiles do sprite ampliados e se estão CRUS na ROM |
| `fab sprite marks <census --engine> --store … --target … --out marks.asm [--mod-json …] [--max-other-px N]` | marcas por cel (motores de lista de cels, `game.json → sprite_engine`) a partir dos rótulos |
| `fab palette ramp <captura> (--object N\|--bg N\|--cgram-palette P [--box x,y,w,h]) --indices a-b (--to cor\|--colors …\|--copy-from PC:a-b)` | candidatas de rampa que preservam o sombreado (OKLab) + prévia exata; `proximo` traz o `fab paint set` pronto |
| `fab palette find <jogo> --colors "$011E,$001B"` | onde uma sequência BGR555 está na ROM (PC, endereço de CPU e `org` do Asar) |
| `fab paint set mods/<id> --pc 0x… --indices a-b --colors … --name … --evidence …` | grava no `paint.json` e gera `paint.asm` (org pelo mapa) + `data[]` |
| `fab paint remap mods/<id> --capture … --object N --map 14:9,15:12 [--part --store] …` | troca índices DENTRO do desenho dos tiles do sprite (cru → dados; comprimido → `vram_tiles`, servido pelo `fab gfx override`) |
| `fab paint oam-mirror mods/<id> --from-dma <run> (--tiles …\|--from-census …) --src-palette p --mirror-palette q --colors i:cor,…` | nível 2: hook antes do DMA do OAM + paleta-espelho por tabela de tiles (gera `oam_mirror.asm` e o hijack) |
| `fab paint check mods/<id> [--state s] [--frames auto\|30,90] [--baseline-rom …]` | mod × base píxel a píxel (esperado/colateral/cor errada/faltou) + **orçamento de VBlank** (DMA que caiu com a imagem sendo desenhada) |
| `fab probe exec <jogo> <Rótulo> --mod <id>` | sonda um rótulo do build ATUAL do mod (endereços mudam a cada build) |

Campos do `mod.json` que as ferramentas preenchem: `hijacks[]` (`addr`, `m`, `x`, `evidence`, `source`, `verify` =
rótulos extras cujo tamanho de instrução o build confere), `data[]` (regiões de dados com evidência, por `addr` ou
`pc`), `blobs[]` (`pc` + arquivo binário gravado pelo build, ex.: tabela/cópias do override), `expand_to`.
`"baseline": {"variant": {"name": "off", "defines": {"X_OFF": "1"}}}`: o `fab cycle run` usa como base o próprio mod
montado com esses defines (mesmo código, só valores) — obrigatório para mod com código, porque qualquer hook muda o
timing e o RNG do jogo; o relatório confere que a variante não muda opcode e mede a sincronia pela WRAM.

## Arquivos de uma run (`runs/<data>-<tipo>-<rótulo>/`)
`job.json` (o que rodou) · `result.json` (status, frames, hits, sha1 da ROM) · `harness.log` ·
`trace.csv` (frame, input, watches) · `probes.jsonl` · `frames/fNNNNN.png` (256x224) · `video.mp4`
(2x, 60/every fps) · `sheet.png` · `wram.bin` + `wram_index.csv` (dumps de WRAM) · `cdl.bin` ·
`ppu.bin` + `ppu_index.jsonl` (snapshots OAM+CGRAM+VRAM com o display ligado) · `dma.jsonl` (log de DMA) ·
`vram_uploads.bin` + `vram_uploads.jsonl` (o que cada DMA deixou na VRAM, com fonte, canal e M/X do disparo).
Campos do job ligados a isso: `ppu_frames`/`ppu_every`, `false_color`, `capture.frames`, `wram_frames`, `dma_log`, `vram_uploads`.
