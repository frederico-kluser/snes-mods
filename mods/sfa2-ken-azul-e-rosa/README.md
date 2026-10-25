# Ken de gi azul, rosa (Dan) e preta (Akuma) + luvas pretas na roupa preta

Jogo: `sfa2` (STREET FIGHTER ALPHA2)

Objetivo: As três primeiras roupas do Ken ganham novas cores: cor 0 (soco) continua de gi azul royal,
cor 1 (chute) passa de roxa para rosa como o do Dan e cor 2 (2+ socos) passa de branca para preta como a
do Akuma (tons copiados das paletas deles na ROM), no sprite da luta e nos retratos (seleção e tela VS);
pele, cabelo, faixas, efeitos, as cores 3-5 do Ken e os outros personagens ficam iguais. **Na roupa preta
(cor 2) as LUVAS também ficam pretas — só elas: o cabelo continua loiro** (pedido do dono, 2026-10-25).

## Estado
- **Cores do gi e retratos: PRONTO** (ciclos 1 e 3, `objetivo-cumprido`, 42/42 checks — só dados).
- **Luvas pretas na cor 2: mecanismo PRONTO e medido; cobertura PARCIAL.**
  - [x] 3 hooks montados e verificados (`fab build`: 0 avisos, m/x conferidos em todos).
  - [x] espelho da paleta confirmado em runtime (pal 11 = cópia fiel da pal 14; tons 14/15 = rampa preta).
  - [x] validação pixel a pixel por "mod × mod com a regra desligada" (mesmo timing): 530 frames,
        18 609 px alterados, **destino sempre na rampa preta (0 erros)**; origem ouro em 95,6% (o resto
        são frames do "flash" de dano, que escreve `$06C0` por fora da rotina hookada).
  - [ ] poses em que o punho erguido é desenhado por um tile do grupo da cabeça (ex.: `$2E`) ainda
        mostram essa luva loira — a regra por tile cobre hoje `$0C`/`$0E`.
  - [ ] ciclo oficial (ciclo 4: 21/46) **não certifica**: os hooks deslocam o RNG da CPU e a luta joga
        diferente do baseline limpo (ver "Armadilha do timing").

## O que o patch muda
- **Dados** (BGR555):
  - cor 0 (soco): `$BE:8272` → `$7E06 $7102 $60A1 $5060 $4440` (azul) e retrato `$BE:CE6A` →
    `$7E06 $7102 $5881 $3C20`
  - cor 1 (chute): `$BE:8292` → `$6ADC $521E $419C $311A $2098` = **cópia fiel do gi do Dan** e retrato
    `$BE:CE8A` → `$521E $419C $311A $2098`
  - cor 2 (2+ socos): `$BE:82B2` → `$2908 $18C6 $14A5 $1084 $1084` = **cópia fiel do gi do Akuma** e
    retrato `$BE:CEAA` → `$2908 $18C6 $14A5 $1084` (com o realce — simulação print 33)
- **Código** (luvas pretas na cor 2):
  1. `C0:0312` (VBlank, antes do DMA da CGRAM; m8/x16): copia `$06C0-$06DF` → `$0660-$067F`.
     **Só com `$7E:07C8 == 2`** (roupa preta) sobrescreve os tons 14/15 com a rampa da luva
     (`$2908` realce + `$1084` sombra — **2 tons, sombreado preservado**; preto único achata).
  2. `C0:5CA9` (atributo do sprite; m8/x16): se a paleta base é 6 (P1) **e** o tile final
     (`$0015C2,X`) é `$0C`/`$0E` → `attr ^= $0A` → paleta 3 = **paleta espelho** (CGRAM 11).
     Como o espelho só difere nos tons 14/15, pele/manga/contorno ficam idênticos por construção.
  3. `C0:3A9A` (fim da recarga de paleta `C0:3A60-3A9D`; m8/x16): refaz o espelho para não ficar
     1 frame atrasado na recarga.
- BPS de ~339 B; 6 regiões de dados + 3 hijacks; este BPS substitui o `sfa2-ken-gi-azul`
  (não empilhe BPS: ambos nascem da ROM limpa).

## Por que o espelho precisa de paleta separada
Medido nesta sessão: a **paleta de sprite é `índice do OAM + 8`** (Ken OAM 6 → CGRAM 14; Rose OAM 7 →
CGRAM 15), então a sprite pal 3 cai na **CGRAM 11** (`$160-$17F`), que o jogo deixa **toda a zeros**
durante a luta. Não há como trocar o tom só da luva por paleta: cabelo e luva partilham os tons 14/15 —
o que os separa é o TILE. Daí "espelho + redirecionar a peça".

## Cenários (7)
- `luta-soco` · `selecao-e-vs` — cor 0 azul (+ checagem de que o espelho é **cópia fiel**, luvas loiras).
- `luta-rosa` · `selecao-e-vs-rosa` — cor 1 rosa do Dan.
- `luta-preta` · `selecao-e-vs-preta` — cor 2 preta do Akuma (o original mostra branco) + checagens do
  espelho e da rampa preta de 2 tons.
- `regressao-verde` — cor 3 (gi verde-escuro, 2 chutes) intacta.

⚠ O `warmup` (40) nas lutas existe porque o savestate carrega a paleta já resolvida da ROM limpa; o jogo
só a recarrega da ROM (rotina `C0:3A8F`) na 1.ª transição de ação ou ~70 frames depois.

## ⚠ Armadilha do timing (importante para quem continuar)
Os hooks (mesmo sem a regra da luva) **deslocam o timing da CPU** e o RNG do jogo muda com ele: a luta
joga diferente **a partir do frame 1** (`7E:0709` = 203 no limpo × 201 no mod; a vida diverge depois).
Consequência prática: **checks de luta alinhados ao baseline da ROM limpa não servem para mod com
código** — giram ❌ mesmo com o mod correto (foi o que deu o ciclo 4 vermelho: 21/46).
Verificação válida: rodar o **mod × mod com a regra desligada** (mesmo timing) e comparar píxeis, ou
usar checks que não dependem do alinhamento de frame.
