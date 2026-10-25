# Ken de gi azul e rosa (Dan)

Jogo: `sfa2` (STREET FIGHTER ALPHA2)

Objetivo: A cor 0 do Ken continua de gi azul royal e a cor 1 (escolhida com chute) passa de roxa para
rosa como o do Dan (cores copiadas da paleta dele na ROM), no sprite da luta e nos retratos (seleção e
tela VS); pele, cabelo, faixas, efeitos, as cores 2-5 do Ken e os outros personagens ficam iguais e a
lógica da luta não muda.

## Estado — PRONTO (2026-10-25, veredito `objetivo-cumprido` no ciclo 1)
- [x] evidências recolhidas (Dan = id 12 na grade, nome "DAN" + `$7E:07A2=12`; tons do gi dele em
      `0x1F1E40`; paletas do Ken conferidas byte a byte)
- [x] patch monta sem avisos (4 regiões de dados declaradas em `data[]`, 0 hijacks; BPS 163 B)
- [x] ciclo com todos os checks a passar (ciclo 1: 29/29, score 1.0)
- [x] verificação visual (prints 25-29: luta rosa, retratos rosa, preview azul, regressão branca 0 divergências)

## O que o patch muda
- `patch.asm` (só dados, BGR555):
  - cor 0 (soco): `$BE:8272` → `$7E06 $7102 $60A1 $5060 $4440` (azul, igual ao mod `sfa2-ken-gi-azul`)
    e retrato `$BE:CE6A` → `$7E06 $7102 $5881 $3C20`
  - cor 1 (chute): `$BE:8292` → `$6ADC $521E $419C $311A $2098` = **cópia fiel do gi do Dan**
    e retrato `$BE:CE8A` → `$521E $419C $311A $2098` (rampa do Dan sem o realce mais claro)
- Este BPS substitui o `sfa2-ken-gi-azul` (não empilhe BPS: os dois são feitos sobre a ROM limpa).

## Cenários (5)
- `luta-soco` · `selecao-e-vs` — cor 0 azul (iguais ao mod anterior).
- `luta-rosa` · `selecao-e-vs-rosa` — cor 1 rosa do Dan (o original mostra o gi roxo).
- `regressao-branco` — cor 2 (gi branco, selecionado com 2 socos) intacta: 0 frames divergentes.

⚠ O `warmup` (40) nas lutas existe porque o savestate carrega a paleta já resolvida da ROM limpa; o jogo
só a recarrega da ROM (rotina `C0:3A8F`) na 1.ª transição de ação ou ~70 frames depois.
