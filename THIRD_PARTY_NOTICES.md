# Avisos de terceiros

O código deste repositório é MIT (veja [LICENSE](LICENSE)). Nenhum código de terceiros é versionado aqui: o que vem
de fora é baixado na máquina de quem usa, da fonte oficial, com versão e sha256 fixados — e não é redistribuído.

## Incluído no repositório

### Memória CoALA — `.agents/snes-mods-coala-agent-skill/`

Motor `coala.py` e arquivos gerenciados vêm da coala-agent-skill, do mesmo autor deste repositório, também sob MIT.
O dump `memory/coala.canonical.jsonl` é a memória do próprio projeto: notas dos agentes e trechos dos documentos e
do catálogo de código deste repositório (o export mascara segredos; o teste `tests/test_memory.py` recusa caminhos
locais de máquina).

## Ferramentas baixadas pelo `fab setup` (não redistribuídas)

O `fab setup` baixa cada ferramenta para `tools/` (fora do git), conferindo o sha256 fixado em
[`tools/manifest.json`](tools/manifest.json). Cada uma mantém a sua licença:

| Ferramenta | Versão | Licença |
| --- | --- | --- |
| [MesenCE](https://github.com/nesdev-org/MesenCE) (sucessor do Mesen2) | 2.2.1 | GPL-3.0 |
| [Asar](https://github.com/RPGHacker/asar) | 1.91 | LGPL-3.0 ou posterior; a interface da DLL (`dll/asardll.h`, `dll/asardll.cpp`) é WTFPL |
| [Ghidra](https://github.com/NationalSecurityAgency/ghidra) | 12.1.4 | Apache-2.0; componentes de terceiros com licenças próprias (`licenses/` e `GPL/` do pacote) |
| [ghidra-snes](https://github.com/joshleaves/ghidra-snes) | commit `d33ce5d` (v1.3.0+2) | MIT — compilado na máquina contra o Ghidra fixado; o `fab setup` só põe `version=@extversion@` no `extension.properties` e encurta o `Module.manifest` |
| [Eclipse Temurin JDK](https://adoptium.net) | 21.0.12.1+1 | GPL-2.0 com Classpath Exception |
| [ffmpeg](https://ffmpeg.org) (build "essentials" da [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)) | 2026-10-22 | GPL-3.0 (o build inclui componentes GPL) |
| [REA](https://github.com/morluto/rea) (`rea-agents`, npm, em `tools/rea`) | 6.7.0 | MIT; as dependências npm têm licenças próprias |

Dependências Python (instaladas na `.venv` a partir de `requirements.txt`, com hash): numpy 2.5.4 (BSD-3-Clause, com
partes 0BSD/MIT/Zlib/CC0-1.0), Pillow 13.0.0 (MIT-CMU) e matplotlib 3.11.2 (licença do matplotlib, no estilo da PSF)
com as dependências dele — contourpy (BSD-3-Clause), cycler (BSD-3-Clause), fonttools (MIT), kiwisolver
(BSD-3-Clause), packaging (Apache-2.0 ou BSD-2-Clause), pyparsing (MIT), python-dateutil (Apache-2.0 e
BSD-3-Clause), six (MIT) e tzdata (Apache-2.0). Desenvolvimento: ruff 0.17.2 (MIT, `requirements-dev.txt`); fuzzing
no CI: atheris 3.1.0 (Apache-2.0, `requirements-fuzz.txt`).

## Jogos e Nintendo

Nenhuma ROM, savestate, build, BPS, frame, vídeo ou print de jogo comercial é versionado (`.gitignore` +
`fab doctor`). A ROM de teste ([`fixtures/testbed/testbed.asm`](fixtures/testbed/testbed.asm)) é código próprio; ela
põe a rotina de pulo nos endereços do exemplo do guia de referência usado na concepção do projeto, e
[`mods/testbed-double-jump/`](mods/testbed-double-jump/) reproduz o patch desse exemplo. As imagens de `docs/img/`
saem dela. Notas de jogo (`games/<id>/`, skills `rom-<jogo>`, relatórios de ciclo) trazem só fatos medidos por nós
(endereços, valores de paleta, comportamento) — sem dumps de código ou de gráficos comerciais.

Super Nintendo e SNES são marcas da Nintendo; os nomes de jogos citados pertencem aos seus donos. Este projeto não tem
relação com eles.
