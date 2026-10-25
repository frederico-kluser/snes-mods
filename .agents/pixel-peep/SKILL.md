---
name: pixel-peep
description: Ler e editar pixel-art minúscula (sprites, tiles, paletas, screenshots antigos) píxel a píxel — amplia as células mantendo grelha/rótulos à escala normal, trabalha sobre o MAPA de valores (índices, sem converter de volta), varinha mágica RGB para famílias de cores ("tudo o que muda") e verificação ANTES×DEPOIS pixel-perfect com restauro dos falsos positivos. Use SEMPRE que precisar de identificar que cores/índices um sprite usa, classificar tiles, planear uma recoloração, medir áreas de cor ou conferir que uma alteração tocou SÓ no que devia.
---

# pixel-peep — ler e editar pixel-art píxel a píxel

Imagens de 256x224 (ou recortes 8x8/16x16) são pequenas demais para julgar à vista. A técnica:
**ampliar as CÉLULAS de píxel e NÃO a moldura** — grelha e texto ficam à escala normal, finos e
legíveis por cima dos blocos grandes. O produto principal é o **MAPA de valores**: a matriz de
índices/cor por célula. É o mapa que diz ONDE alterar; **não converta de volta para "normal"** —
trabalhe sempre em cima dos valores (índice da paleta), que é assim que se patcha.

## O ciclo (sempre assim)

1. **Recortar** (`--crop x,y,w,h`) a região de interesse — nunca ampliar o screenshot inteiro.
2. **Ampliar** até a folha ficar ~512-1200 px (`--fit 640` calcula; `--scale N` força). 2x/4x para
   frames inteiros; 8x-40x para recortes de 8x8/16x16. Grelha e rótulos **nunca** ampliados.
3. **Ler o mapa**: `--indices --palette "bgr555 <rom>:<off>:<n>"` → cada célula mostra o índice; o
   `<out>.txt` guarda a matriz. Use os VALORES como mapa de edição (o que mudar, onde).
4. **Varinha mágica** (`--wand <índice|#hex> --tolerance N`): lista a família de cores próximas e
   marca as células; `<out>.mask.txt` = a máscara X/. do que **deve** mudar ("tudo o que muda").
5. **Aplicar** a alteração (patch de paleta/tiles) usando o mapa.
6. **VERIFICAR ANTES × DEPOIS** (`pixel_verify.py`): compara com a máscara pretendida e separa
   **falsos positivos** (pintados a mais) de **falhados** (não pintados). Objetivo **0 + 0**.
   ⚠ O ANTES e o DEPOIS têm de ser o **MESMO frame de duas runs determinísticas** (baseline ×
   alterado) — comparar frames diferentes apanha a animação do cenário e falsifica tudo.
7. **Corrigir e repetir**: `--fix` restaura do ANTES os falsos positivos; re-verifique. Pode correr
   o processo quantas vezes for preciso — a exigência é **pixel-perfect**, não a primeira tentativa.

## Scripts

```bash
# mapa ampliado + matriz de valores (+ varinha)
python .agents/pixel-peep/scripts/pixel_grid.py <imagem> [--crop x,y,w,h] [--fit 640 | --scale N]
        [--indices] [--palette "bgr555 <arquivo>:<offset>:<n>" | "hex #aabbcc,..."]
        [--wand <índice|#hex> --tolerance N] --out <out.png>

# verificação antes×depois pixel-perfect (+ restauro dos falsos)
python .agents/pixel-peep/scripts/pixel_verify.py --before <antes.png> --after <depois.png>
        [--mask <out.mask.txt> | --palette ... --wand <alvo> --tolerance N]
        --out <ver.png> [--fix <depois_corrigido.png>]
```

- `bgr555` = conversão por replicação de bits (`(v<<3)|(v>>2)`), a mesma do MesenCE.
- `pixel_verify.py` sai com exit 0 **só** quando falsos=0 e falhados=0 (pixel-perfect).
- Saídas: `<out>.txt` (matriz de valores = mapa), `<out>.mask.txt` (máscara X/. da varinha).

## SOMBREADO: a regra que não se pode quebrar ao trocar cor

Trocar cor de sprite **não é** trocar um tom por outro: é trocar uma **rampa**. Um tecido/punho
lê-se como volume porque os tons claros e escuros mantêm uma relação. Se todos os tons viram o
mesmo valor, o objeto **achata** (fica uma mancha monocromática) e o desenho morre — mesmo que a
"cor" esteja certa. Regras:

1. **Nunca** mapeie 2+ tons de origem no MESMO tom de destino (isso é o "tom único"). Preserve a
   ordem: realce continua mais claro que a sombra.
2. **Mantenha o espaçamento relativo** da rampa original. Meça a distância em RGB entre o realce e a
   sombra e guarde uma distância **visível a 1x** (não adianta separar 2-3 níveis: some na tela).
3. **Não use o tom do CONTORNO como sombra** da peça: a sombra encosta no contorno e a silhueta
   derrete. O contorno é a linha mais escura e tem de continuar a ser a mais escura.
4. **Tecido escuro (preto):** use 2 tons da própria família (ex.: realce `$2908` + sombra `$1084` —
   66,66,82 e 33,33,33) e **confira no zoom E a 1x**; preto puro (`$0000`) nos dois tons é o erro
   clássico.
5. **Verifique sempre** (não confie no valor): simule a rampa sobre o frame real, amplie 8-10x e
   olhe; depois confirme a 1x. Só então aplique no patch.
6. Em **paleta espelho** (espelho de uma paleta para redirecionar peças), troque **só** os tons da
   peça; todos os outros têm de ficar **byte-idênticos** à paleta original — é isso que garante que
   pele, manga e contorno não mudam por construção.

**Exemplo real (SFA2, luvas do Ken):** a luva e o cabelo partilham os tons 14/15. Escolhida a rampa
`$2908` (realce) + `$1084` (sombra) — os dois tons do gi preto do Akuma — em vez de um preto único;
o punho mantém o vinco e não se confunde com o contorno `$0842`. Simulação: `games/sfa2/prints/34-luvas-rampas-sombreado.png`
(5 variantes, 10x). Ver também `references/`… e a skill do jogo para os valores.

## Receitas prontas

- **Que índices um sprite usa?** recorte + `--indices --palette "bgr555 rom:off:16"`; a matriz
  permite contagens por zona (cabeça, luvas, gi…).
- **Classificar tiles (luvas × cabelo × gi):** tiles extraídos do OAM → mapa de índices por tile →
  composição: só índices do ramp amarelo = luvas/cabelo; o tom de realce (ex.: 08) denuncia o
  cabelo; pele/vermelhos = corpo. Tiles que MISTURAM cores (punho = pele+ouro+contorno) exigem
  truque de paleta (espelho com os tons amarelos a preto) em vez de troca de paleta simples.
- **Planejar uma recoloração:** varinha no tom de origem → máscara = tudo o que muda → aplicar →
  `pixel_verify` antes/depois → `--fix` → re-verificar até 0+0.
- **Medir áreas:** contar na matriz (texto), nunca estimar pela imagem.

## Exemplo real (SFA2, punho do Ken 16x16)

```bash
python .agents/pixel-peep/scripts/pixel_grid.py runs/<run>/frames/f00060.png \
    --crop 142,133,16,16 --indices --palette "bgr555 roms/sfa2/sfa2.sfc:0x1F0260:16" \
    --wand 15 --tolerance 60 --out work/pg-punho.png
```

→ folha ~640px com cada píxel em bloco (índice dentro), grelha fina, coordenadas legíveis;
`work/pg-punho.txt` = o mapa de valores; `work/pg-punho.mask.txt` = o que a varinha apanhou.
