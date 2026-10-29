# Uma agent skill por jogo (`rom-<jogo>`) + pasta de prints

Todo jogo analisado pela fábrica segue o mesmo padrão (modelo vivo: `.agents/rom-street-fighter-alpha/`,
o Street Fighter Alpha 2). A skill do jogo é o diário dele: o que se sabe (com evidência), o que se
decidiu, em que pé está cada mod e **como continuar** — outro agente (ou outra sessão) tem de conseguir
retomar só com ela. Os fatos duráveis vão também para a memória CoALA, e a skill aponta as chaves.

## Quando criar
No passo 2 da `snes-mod-factory`, logo depois do `fab rom add` (o jogo já tem id e `games/<id>/`).
Se o jogo já tem skill, carregue-a ANTES de qualquer outra coisa e continue de onde ela parou.

## Onde e como
- Nome: `rom-<slug do título>` (ex.: `rom-street-fighter-alpha`, `rom-super-mario-world`). O id curto da
  fábrica (`fab rom add --id sfa2`) aparece dentro da skill.
- Arquivos reais em `.agents/rom-<jogo>/` (`SKILL.md` + `references/` quando crescer) e dois links
  versionados, como as outras skills do projeto (Git Bash; no Windows precisa do Modo de Desenvolvedor):
  ```bash
  MSYS=winsymlinks:nativestrict ln -s ../../.agents/rom-<jogo> .claude/skills/rom-<jogo>
  MSYS=winsymlinks:nativestrict ln -s ../rom-<jogo> .agents/skills/rom-<jogo>
  ```
- Elo com a memória CoALA: a skill lista as chaves do jogo; grave os fatos duráveis com
  `coala.py add --key <id>-<assunto>` citando o caminho da skill, e abra o `games/<id>/notes.md` (que o
  `sync` ingere) com um ponteiro para ela. O motor da CoALA não ingere `.agents/` nem `.claude/`.

## Pasta de prints — sempre
- `games/<id>/prints/` — **crie ao começar o jogo** (`mkdir -p`). É ignorada pelo git (frames de jogo
  comercial; `fab doctor` falha se algo dali for versionado). É por ela que o usuário acompanha o trabalho.
- Cada avanço ou teste ganha um print com o próximo número, `NN-descricao-curta.png`, e uma linha no
  `LEIA-ME.txt` da pasta (o que mostra, de qual run/ciclo veio). Nunca renumere os antigos.
- O que printar: a `preview_sheet` de cada `fab state boot` útil, recortes ampliados (Read com zoom), dumps
  de paleta/RAM renderizados, simulações de antes/depois, e em cada ciclo o `compare.png` e o
  `trace_compare.png` de cada cenário; no fim, o resultado (antes × depois).

## Esqueleto do `SKILL.md`
```markdown
---
name: rom-<jogo>
description: Skill do jogo <Título> (<região>, SNES, <mapa/chip>; id `<id>` na fábrica) — o que já se
  descobriu, o estado dos mods e como continuar. Use SEMPRE que o pedido mencionar <título>, <apelidos>,
  `<id>`, <personagens/temas do pedido>.
---
# <Título> (`<id>`) — skill do jogo
> Padrão "uma skill por jogo" (ver .agents/snes-mod-factory/references/skill-de-jogo.md).

## Comece por aqui (toda sessão)   ← doctor, CoALA recall + chaves, notes.md, pasta de prints, como recriar ROM/states
## Identificação                   ← arquivo do usuário, hashes, cabeçalho, chip, limitações
## Como chegar a cada momento      ← tabela state | origem + macro | o que mostra
## Fatos verificados               ← RAM/ROM/rotinas com evidence_id; inferido ≠ verificado
## Estado (<data>)                 ← pedido, decisões (com o porquê), o que está feito/pendente, branch/commits
## Como continuar (em ordem)       ← passos com comandos exatos, até o critério de pronto
## Perguntas em aberto
## Avanços (diário)                ← uma entrada por sessão, com data; acrescente embaixo
```

## Manutenção (ao parar ou no fim de cada sessão)
1. Reescreva **Estado** e **Como continuar**; acrescente a entrada do dia em **Avanços**.
2. Fatos novos → tabelas da skill + `games/<id>/notes.md` + `coala.py add --key <id>-<assunto>`.
3. Prints novos na pasta, com o índice atualizado.
4. Nada de dumps de código comercial em arquivos versionados: endereços, tamanhos e a descrição da rotina
   bastam; poucos valores de dados só quando o patch ou um check precisa deles.
