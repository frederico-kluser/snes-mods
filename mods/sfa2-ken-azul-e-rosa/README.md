# Ken de gi azul, rosa (Dan) e preta (Akuma)

Jogo: `sfa2` (STREET FIGHTER ALPHA2)

Objetivo: As três primeiras roupas do Ken ganham novas cores: cor 0 (soco) continua de gi azul royal,
cor 1 (chute) passa de roxa para rosa como o do Dan e cor 2 (2+ socos) passa de branca para preta como a
do Akuma (tons copiados das paletas deles na ROM), no sprite da luta e nos retratos (seleção e tela VS);
pele, cabelo, faixas, efeitos, as cores 3-5 do Ken e os outros personagens ficam iguais e a lógica da
luta não muda.

## Estado — PRONTO (2026-10-25, veredito `objetivo-cumprido` nos ciclos 1 e 3)
- [x] evidências recolhidas (Dan = id 12 e Akuma = id 2 na grade: nomes + `$7E:07A2`; tons dos gi deles
      em `0x1F1E40` e `0x1F0460`; paletas do Ken conferidas byte a byte)
- [x] patch monta sem avisos (6 regiões de dados declaradas em `data[]`, 0 hijacks; BPS 185 B)
- [x] ciclo com todos os checks a passar (ciclo 3: 42/42, score 1.0)
- [x] verificação visual (prints 25-33: lutas rosa e preta, retratos, preview azul, regressões)

## O que o patch muda
- `patch.asm` (só dados, BGR555):
  - cor 0 (soco): `$BE:8272` → `$7E06 $7102 $60A1 $5060 $4440` (azul) e retrato `$BE:CE6A` →
    `$7E06 $7102 $5881 $3C20`
  - cor 1 (chute): `$BE:8292` → `$6ADC $521E $419C $311A $2098` = **cópia fiel do gi do Dan** e retrato
    `$BE:CE8A` → `$521E $419C $311A $2098`
  - cor 2 (2+ socos): `$BE:82B2` → `$2908 $18C6 $14A5 $1084 $1084` = **cópia fiel do gi do Akuma** e
    retrato `$BE:CEAA` → `$2908 $18C6 $14A5 $1084` (com o realce — simulação print 33)
- Este BPS substitui o `sfa2-ken-gi-azul` (não empilhe BPS: os dois são feitos sobre a ROM limpa).

## Cenários (7)
- `luta-soco` · `selecao-e-vs` — cor 0 azul. `luta-rosa` · `selecao-e-vs-rosa` — cor 1 rosa do Dan.
- `luta-preta` · `selecao-e-vs-preta` — cor 2 preta do Akuma (o original mostra branco).
- `regressao-verde` — cor 3 (gi verde-escuro, selecionado com 2 chutes) intacta: 0 frames divergentes.

⚠ O `warmup` (40) nas lutas existe porque o savestate carrega a paleta já resolvida da ROM limpa; o jogo
só a recarrega da ROM (rotina `C0:3A8F`) na 1.ª transição de ação ou ~70 frames depois.
