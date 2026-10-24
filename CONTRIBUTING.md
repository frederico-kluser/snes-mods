# Contribuindo com o snes-mods

Obrigado pelo interesse! Este guia explica o ambiente, o fluxo de trabalho e a régua de qualidade de
qualquer mudança em `frederico-kluser/snes-mods`. Ao participar, você concorda com o
[Código de Conduta](CODE_OF_CONDUCT.md).

## Regra número zero: nada de material de jogos comerciais

**Nunca** inclua em commits, issues, PRs ou anexos: ROMs, savestates, builds montados, patches BPS
de jogos comerciais, frames/vídeos/prints de jogos comerciais, exports do Ghidra ou trechos grandes de
código desmontado. O `.gitignore` bloqueia os formatos conhecidos e `./fab doctor` verifica o índice
do git. Para reproduzir um problema, use a ROM homebrew do próprio repositório
(`fixtures/testbed/`) ou descreva o jogo (título, região, mapa, sha256 da base limpa).

## Ambiente

Requisitos: **Windows 10/11 x64** (o toolchain pinado em `tools/manifest.json` é para `windows-x64`),
**Python 3.12+**, **Git** e, opcionalmente, **Node.js ≥ 22.19** (servidor MCP do REA).

```bash
git clone https://github.com/<seu-usuario>/snes-mods.git
cd snes-mods
git remote add upstream https://github.com/frederico-kluser/snes-mods.git

./fab setup      # baixa e verifica (sha256) JDK 21, Ghidra 12.1.4, MesenCE, Asar, ffmpeg; compila o ghidra-snes
./fab doctor     # tudo deve sair OK
./fab selftest   # testes unitários + ponta a ponta (MesenCE headless com a ROM de teste)
```

No PowerShell use `.\fab.ps1`; no cmd, `fab.cmd`. Na primeira execução o wrapper cria a `.venv`
com `requirements.txt`. Ferramentas de desenvolvimento: `pip install -r requirements-dev.txt`. As dependências são fixadas
com hash a partir de `requirements*.in` (`pip-compile --generate-hashes`); o Dependabot mantém os dois.

**Linux/macOS**: os testes unitários rodam (`python -m unittest discover -s tests -t .`); os de ponta a
ponta pulam porque o manifesto ainda não tem seção para essas plataformas. Contribuições que adicionem
`linux-x64`/`macos-arm64` ao `tools/manifest.json` são muito bem-vindas.

## Como enviar uma mudança

- **Nunca faça push direto na `main`** — um ruleset do GitHub recusa. Tudo entra por pull request
  com **squash merge**.
- Trabalhe num fork ou numa branch curta `<tipo>/<slug>` e abra o PR contra `main`.
- Um assunto por PR; mantenha a branch atualizada com rebase sobre `upstream/main`.

### Nomes de branch (impostos pelo GitHub)

`<tipo>/<slug>` com tipos fechados: `feat` `fix` `docs` `style` `refactor` `perf` `test` `build`
`ci` `revert` `hotfix` `release` — ex.: `feat/hirom-expand`, `fix/probe-pc-backtrack`,
`docs/video-guide`. Slug curto em kebab-case. Só branches de automação (`dependabot/*`,
`renovate/*`, `release-please--*`) fogem à regra.

### Mensagens de commit (Conventional Commits)

O título do PR vira a mensagem do squash e alimenta o changelog e a versão (SemVer):

```text
feat(cycle): veredito automático por cenário
fix(emu): capturas alinhadas com a RAM em velocidade máxima
docs: guia de análise de vídeo
feat!: novo formato do mod.json        ← quebra compatibilidade (MAJOR)
```

Tipos: `feat` `fix` `docs` `style` `refactor` `perf` `test` `build` `ci` `chore` `revert`;
cabeçalho com no máximo **72 caracteres**. O job `build` do CI valida o título do PR e os commits.

## Régua de qualidade (antes de abrir o PR)

```bash
ruff check snesfab tests                      # lint (config em ruff.toml)
python -m unittest discover -s tests -t .     # testes unitários (qualquer SO)
./fab selftest                                # + ponta a ponta (Windows com toolchain)
```

- Toda mudança de comportamento vem com teste; bug corrigido vem com teste de regressão.
- Funcionalidades que mexem no emulador/ciclo devem ser exercitadas com a ROM de teste
  (`fixtures/testbed/testbed.asm` + `mods/testbed-double-jump/`).
- Se o comportamento mudar, atualize a documentação dos agentes: as skills em
  `.agents/snes-mod-*`, `.agents/snes-rea-modder` e o `CLAUDE.md`/`AGENTS.md` (espelhados).
- Workflows: actions fixadas por SHA, `permissions` mínimas e `timeout-minutes` em todo job.

### Fuzzing

Os parsers que recebem entrada de terceiros (patch BPS, macro, critério do `mod.json`, ROM e endereços)
têm alvos de fuzzing em `tests/fuzz/` (atheris/libFuzzer). O CI roda cada alvo nos PRs que mexem em
`snesfab/` e por 10 minutos toda semana. Para rodar localmente:

```bash
# Linux x86-64 ou WSL: libFuzzer guiado por cobertura (o 1.º diretório recebe as entradas novas)
pip install --require-hashes -r requirements.txt -r requirements-fuzz.txt
python tests/fuzz/fuzz_bps.py -max_total_time=60 work/fuzz/bps tests/fuzz/corpus/bps

# Windows/macOS (sem atheris): corpus + mutações aleatórias; também reproduz um crash baixado do CI
python tests/fuzz/fuzz_bps.py crash-0123abcd
```

Crash corrigido vira teste de regressão em `tests/test_unit.py`, e a entrada vai para `tests/fuzz/corpus/<alvo>/`.

## Revisão, merge e releases

- O PR só entra com o status check `build` verde (lint + testes + mensagens convencionais) e as
  conversas resolvidas; o merge é sempre squash.
- As releases são automáticas: o **release-please** mantém um PR de release com a próxima versão
  (calculada pelos commits) e o `CHANGELOG.md`. Não edite o changelog à mão.
- Tags `v*` são imutáveis.

## Licença

Ao contribuir, você concorda que sua contribuição é licenciada sob a [MIT](LICENSE), como o restante
do projeto. Ferramentas de terceiros baixadas pelo `fab setup` mantêm suas próprias licenças e não
são redistribuídas por este repositório.
