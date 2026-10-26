---
name: pixel-peep
description: Ler e editar pixel-art minúscula (sprites, tiles, paletas, screenshots antigos) píxel a píxel — amplia as células mantendo grelha/rótulos à escala normal, trabalha sobre o MAPA de valores (índices, sem converter de volta), varinha mágica RGB para famílias de cores ("tudo o que muda") e verificação ANTES×DEPOIS pixel-perfect com restauro dos falsos positivos. Use SEMPRE que precisar de identificar que cores/índices um sprite usa, classificar tiles, planear uma recoloração, medir áreas de cor ou conferir que uma alteração tocou SÓ no que devia.
---

# pixel-peep — ler e editar pixel-art píxel a píxel

256x224 (ou 8x8/16x16) é pequeno demais para julgar a olho. Amplie as **células**, não a moldura: grelha e texto
ficam finos e legíveis por cima dos blocos. O produto é o **mapa de valores** (índice de paleta por célula) — é ele
que diz onde mudar; trabalhe sempre sobre os índices, que é como se faz o patch.
(Nos jogos, o `fab sprite snap` já entrega mapas por índice e o `fab paint check` a conferência píxel a píxel; use
esta skill para recortes, prints do usuário e conferências finas.)

## O ciclo
1. **Recorte** (`--crop x,y,w,h`) só a região — nunca amplie a tela inteira.
2. **Amplie** até ~512-1200 px (`--fit 640` calcula; `--scale N` força): 2-4x para frames, 8-40x para 8x8/16x16.
3. **Leia o mapa**: `--indices --palette "bgr555 <rom>:<off>:<n>"` → índice em cada célula; `<out>.txt` = a matriz.
4. **Varinha** (`--wand <índice|#hex> --tolerance N`): a família de cores e a máscara `<out>.mask.txt` do que muda.
5. **Aplique** a mudança (paleta/tiles) pelo mapa.
6. **Verifique ANTES × DEPOIS** (`pixel_verify.py`): falsos positivos (pintou a mais) e falhados (faltou) → **0 + 0**.
   ANTES e DEPOIS = o MESMO frame de duas runs determinísticas (base × alterado); frames diferentes mentem.
7. **Corrija e repita** (`--fix` restaura do ANTES os falsos positivos) até pixel-perfect.

```bash
python .agents/pixel-peep/scripts/pixel_grid.py <imagem> [--crop x,y,w,h] [--fit 640 | --scale N] \
       [--indices] [--palette "bgr555 <arquivo>:<offset>:<n>" | "hex #aabbcc,..."] [--wand <alvo> --tolerance N] --out <out.png>
python .agents/pixel-peep/scripts/pixel_verify.py --before <antes.png> --after <depois.png> \
       [--mask <out.mask.txt> | --palette … --wand <alvo> --tolerance N] --out <ver.png> [--fix <corrigido.png>]
```
`bgr555` converte por replicação de bits (`(v<<3)|(v>>2)`), como o MesenCE; `pixel_verify.py` só sai com 0 se 0 + 0.

## Sombreado: a regra que não se quebra
Trocar cor de sprite é trocar uma **rampa**, não um tom. Se todos os tons viram o mesmo valor, o objeto achata.
1. Nunca mapeie 2+ tons de origem no MESMO destino; realce continua mais claro que a sombra.
2. Mantenha o espaçamento relativo, com distância **visível a 1x** (2-3 níveis somem na tela).
3. Não use o tom do **contorno** como sombra: a silhueta derrete.
4. Tecido preto = 2 tons da família (ex.: `$2908` realce + `$1084` sombra), nunca `$0000` nos dois.
5. Simule sobre o frame real, confira ampliado **e** a 1x antes do patch (`fab palette ramp` faz isso).
6. Paleta-espelho: troque só os tons da peça; o resto byte-idêntico à original.

## Receitas
- **Que índices um sprite usa?** recorte + `--indices --palette "bgr555 rom:off:16"`; conte na matriz por zona.
- **Classificar tiles (peça × peça):** mapa de índices por tile; tile que MISTURA peças no mesmo índice pede paleta-
  espelho por tile/cel ou mudança de desenho (`snes-sprite-paint`, caminhos B/C).
- **Planejar recoloração:** varinha no tom → máscara → aplicar → `pixel_verify` → `--fix` → até 0 + 0.
- **Medir área:** conte na matriz (texto), nunca estime pela imagem.

## FAQ
- **Por que não ampliar a imagem inteira?** Grelha e rótulos engrossam e o modelo lê pior; recorte e amplie a célula.
- **O verify acusa mudanças que não fiz.** Os frames não são o mesmo instante: rode base e mod com o mesmo state/macro.
- **Exemplo real?** Punho do Ken (SFA2) 16x16: `pixel_grid.py runs/<run>/frames/f00060.png --crop 142,133,16,16
  --indices --palette "bgr555 roms/sfa2/sfa2.sfc:0x1F0260:16" --wand 15 --tolerance 60 --out work/pg-punho.png`;
  rampas das luvas em `games/sfa2/prints/34-luvas-rampas-sombreado.png`.
