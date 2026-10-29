# Ken de gi azul

Jogo: `sfa2` (STREET FIGHTER ALPHA2)

Objetivo: O uniforme padrão do Ken (cor 0, escolhida com soco) passa de gi vermelho a gi azul royal na
luta, no sprite e no retrato da seleção e na tela VS; pele, cabelo, faixa, efeitos, a cor de chute (roxa)
e os outros personagens ficam iguais e a lógica da luta não muda.

## Estado — PRONTO (2026-10-25, veredito `objetivo-cumprido` no ciclo 2)
- [x] evidências recolhidas (paletas na ROM: `ev-dbaa2b8b4bf8`; recarga em luta: `ev-7d902d01f792`,
      `ev-d6cb5f0e50b5`; cor por botão: prints 10/13)
- [x] patch monta sem avisos (2 regiões de dados declaradas em `data[]`, 0 hijacks; BPS 137 B)
- [x] ciclo com todos os checks a passar (ciclo 2: 16/16, score 1.0)
- [x] verificação visual (prints 20-24: luta, seleção/VS, regressão 0 divergências, olhos do retrato)

## O que o patch muda
- `patch.asm` (só dados, BGR555): `$BE:8272` 10 B = gi da cor 0 do lutador (cores 9-13) →
  `$7E06 $7102 $60A1 $5060 $4440`; `$BE:CE6A` 8 B = gi da cor 0 do retrato (cores 5-8) →
  `$7E06 $7102 $5881 $3C20` (a cor 8 também pinta os olhos — opção A `$3C20`).
- Trocar a cor do gi = mudar as constantes `!gi_*` no topo do `patch.asm`.

## Cenários
- `luta-soco` (state `luta-ken-rose-fight`, warmup 40) — o gi azul durante a luta inteira.
- `selecao-e-vs` (state `selecao`) — retrato/sprite da seleção, mapa e tela VS azuis.
- `regressao-chute` (state `luta-ken-chute-fight`) — cor 1 (gi roxo) intacta, 0 frames divergentes.

⚠ O `warmup` existe porque o savestate carrega a paleta já resolvida da ROM limpa; o jogo só a
recarrega da ROM (rotina `C0:3A8F`) na 1.ª transição de ação ou ~70 frames depois.
