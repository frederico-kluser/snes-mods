# Ken de gi azul, rosa (Dan) e preta (Akuma) + LUVAS PRETAS (todas as cores)

Jogo: `sfa2` (STREET FIGHTER ALPHA2)

Objetivo: As três primeiras roupas do Ken ganham novas cores: cor 0 (soco) continua de gi azul royal,
cor 1 (chute) passa de roxa para rosa como o do Dan e cor 2 (2+ socos) passa de branca para preta como a
do Akuma (tons copiados das paletas deles na ROM), no sprite da luta e nos retratos (seleção e tela VS);
pele, faixas, efeitos, o gi das cores 3-5 do Ken e os outros personagens ficam iguais. **E as LUVAS do
sprite de luta passam a PRETAS em todas as cores de uniforme — só elas: o cabelo continua loiro**
(pedido do dono, 2026-10-27: "mude só as luvas do Ken para preto sem pintar o cabelo").

## Estado
- **Cores do gi e retratos: PRONTO** (ciclos 1 e 3, `objetivo-cumprido`, 42/42 checks — só dados).
- **Luvas pretas: pelo DESENHO (novo mecanismo), 198/198 tiles, 31 667 px.**
  - [x] rótulos por CONTEÚDO de tile (`games/sfa2/parts/ken-ouro.json`): 198 hashes de luva × 159 de
        cabelo, cobertura 99,7% em 300 frames (`fab sprite census`) — a separação luva × cabelo é por
        **PÍXEL dentro do tile** (nível 4: os dois compartilham índices e até o mesmo tile).
  - [x] `fab paint remap --part luva --map 14:1,15:13` varrido por TODOS os frames das 3 capturas
        (alvo = paleta OAM 6, como o censo escolhe; `work/luvas_remap.py`): 198/198 tiles, 31 667 px.
  - [x] mapa escolhido por simulação (`work/sim-mapa-luvas.png`): **14→1** (índice 1 = `$0842` = corpo
        preto IGUAL nas 6 cores de uniforme) e **15→13** (vinco no tom mais escuro da roupa — na cor 2
        = `$1084`, o sombreado aprovado no print 34, um tom mais escuro). Cabelo: índices 14/15
        intocados = ouro.
  - [x] `fab gfx dump` (3 estados de luta × com macro `luta.txt` × luta livre) + `fab gfx override
        --expand --chip-disarm 00:4801=00`: os tiles vêm comprimidos (S-DD1); o hook no disparo do DMA
        (`C0:048C`) serve as cópias editadas e devolve o DMAP. 26 blocos, ROM de 5 MiB.
  - [ ] ciclo oficial + veredito (ver "Estado" na skill `rom-street-fighter-alpha`).

## O que o patch muda
- **Dados** (BGR555, `patch.asm`):
  - cor 0 (soco): `$BE:8272` → `$7E06 $7102 $60A1 $5060 $4440` (azul) e retrato `$BE:CE6A` →
    `$7E06 $7102 $5881 $3C20`
  - cor 1 (chute): `$BE:8292` → `$6ADC $521E $419C $311A $2098` = **cópia fiel do gi do Dan** e retrato
    `$BE:CE8A` → `$521E $419C $311A $2098`
  - cor 2 (2+ socos): `$BE:82B2` → `$2908 $18C6 $14A5 $1084 $1084` = **cópia fiel do gi do Akuma** e
    retrato `$BE:CEAA` → `$2908 $18C6 $14A5 $1084` (com o realce — simulação print 33)
- **Desenho** (`gfx_override.asm` gerado + `gfx_override.bin`): 198 tiles do Ken com os píxeis de LUVA
  remapeados `14→1, 15→13`. O hook intercepta o DMA comprimido (`C0:048C`), serve a cópia editada e
  devolve o DMAP/fonte (o jogo escreve o DMAP uma vez só). Área nova acima de 4 MiB (janela `$F0-$FF`).

## Por que mudar o DESENHO e não a paleta (história do mod)
A paleta de sprite do Ken tem 16 tons e **está toda ocupada**: 1 = contorno/faixa, 2-8 = pele/branco,
9-13 = gi, 14-15 = cabelo **E** luvas (o dourado). Não há como dar à luva uma cor nova por paleta sem
pintar o cabelo. A v1 resolveu com "espelho de paleta" (CGRAM 11) + redirecionamento de cel por marca
(3 hooks, `marks.asm`): funcionava, mas (a) deixava resíduo nos 66 sprites que contêm luva **e** cabelo
no mesmo cel (nível 4) e (b) os hooks deslocavam o RNG da CPU, impedindo a certificação do ciclo contra
a ROM limpa. A v2 (atual) muda o **desenho** do tile separando luva e cabelo píxel a píxel
(`fab paint remap --part luva`): sem código por frame, sem resíduo, cabelo 100% intacto.

⚠ O desenho é o mesmo em TODAS as roupas: por isso a luva fica preta nas 6 cores (decisão do dono).

## Como os tiles das luvas foram achados (método da grelha + partição)
Núcleo da skill `grid-layout` aplicado ao problema (grelha rotulada → partição exata → sonda):
1. **Sonda**: em cada frame pinta-se o ouro (tons 14/15 → magenta) com `fab run --poke` e recolhe-se o
   OAM do MESMO frame (`--wram-every 1`): cada sprite dá caixa 16x16 + número de tile.
2. **Partição**: separam-se os componentes conexos do ouro; o **maior** é o cabelo (massa de ~70-90 px,
   sempre maior que um punho) e os restantes são punhos.
3. **Critério**: um píxel/tile entra como luva se a caixa dele toca um punho **e nunca toca o cabelo**
   nos frames analisados — e o rótulo final é por CONTEÚDO de tile (hash dos 32 B → píxeis 0-63), vale
   em qualquer pose que use o mesmo desenho.
4. Resultado (`fab sprite census` + rótulos manuais dos pendentes): **198 hashes de luva**, 159 de
   cabelo, 66 sprites com as duas peças resolvidos por píxel (nível 4).

## Cenários (7)
- `luta-soco` · `selecao-e-vs` — cor 0 azul.
- `luta-rosa` · `selecao-e-vs-rosa` — cor 1 rosa do Dan.
- `luta-preta` · `selecao-e-vs-preta` — cor 2 preta do Akuma (o original mostra branco).
- `regressao-verde` — cor 3 (gi verde-escuro, 2 chutes): gi e lógica intactos; **só as luvas mudam**
  (pretas por decisão do dono em todas as cores).

⚠ O `warmup` (40) nas lutas existe porque o savestate carrega a paleta já resolvida da ROM limpa; o jogo
só a recarrega da ROM (rotina `C0:3A8F`) na 1.ª transição de ação ou ~70 frames depois. O mesmo vale
para o desenho: o state traz a VRAM com os tiles originais e o jogo re-envia o bloco do Ken a cada
~14 frames (`E0:0427` etc.) — depois do warmup o desenho novo está na tela.

## ⚠ Armadilha do timing (importante para quem continuar)
Hooks em código quente (VBlank, laço de cels) **deslocam o timing da CPU** e o RNG do jogo muda: a luta
joga diferente a partir do frame 1 e checks alinhados à ROM limpa giram ❌ mesmo com o mod correto
(ciclo 4 da v1: 21/46 por isso). Verificação válida: base variante (`baseline.variant`) ou checks que
não dependem de alinhamento de frame. O hook atual (DMA de upload, em blanking) preserva a lógica — o
check `logica-igual` do ciclo confirma frame a frame.
