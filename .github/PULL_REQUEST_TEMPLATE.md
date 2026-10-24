<!-- Obrigado por contribuir com o snes-mods!
     O TÍTULO do PR vira a mensagem do squash merge: use Conventional Commits,
     ex.: `feat(cycle): veredito automático por cenário`. -->

## O quê

<!-- O que esta mudança faz, em poucas linhas. -->

## Por quê

<!-- Motivação e contexto. Ligue issues com palavras de fechamento: -->

Closes #

## Como

<!-- Abordagem, alternativas consideradas, trade-offs. -->

## Checklist

- [ ] Título no formato Conventional Commits (≤ 72 caracteres).
- [ ] `ruff check snesfab tests` sem erros.
- [ ] Testes: `python -m unittest discover -s tests -t .` (e `./fab selftest` no Windows com toolchain).
- [ ] Mudança de comportamento tem teste (bug corrigido tem teste de regressão).
- [ ] **Nenhuma** ROM, savestate, build, BPS, frame/vídeo/print de jogo comercial no diff ou nos anexos.
- [ ] Documentação atualizada onde o comportamento mudou (README, skills em `.agents/`, `CLAUDE.md`/`AGENTS.md`).
- [ ] Workflows alterados: actions fixadas por SHA, `permissions` mínimas, `timeout-minutes`.
- [ ] Mudanças incompatíveis sinalizadas abaixo e com `!`/`BREAKING CHANGE:` no título/corpo.

## Mudanças incompatíveis

<!-- Nenhuma — ou descreva a migração (ex.: formato do mod.json, comandos do fab). -->

-

## Evidências

<!-- Saída de `./fab doctor`/`./fab selftest`, relatório de ciclo, folhas de contato do TESTBED
     (nunca de jogos comerciais). -->
