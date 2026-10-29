# Sprites de SNES para edição por IA (Nano Banana) — export → prompt → import

Para mudar o DESENHO de sprites com ajuda de um modelo de imagem (Google Nano Banana / Gemini image
editing) sem partir a pixel art: o `fab ai` exporta uma **tilesheet EXPANDIDA** (cada píxel vira um
quadrado de cor sólida N×N, fácil do modelo editar), o **mapa JSON de coordenadas** (onde está cada
pose e cada tile na imagem gerada) e o **prompt**; depois re-importa a imagem devolvida, re-quantiza
cada quadrado para os índices da paleta original, limpa o que não ficou correto e gera o plano de
tiles para transpor para o jogo (pipeline `fab paint` / `fab gfx override`).

Evidência e decisões de design: `pesquisas/2026-10-28-…-snes-16-cores-4b.md` (pesquisa profunda).
Pintura sem IA (cor, partes, remap): **snes-sprite-paint**. Fluxo geral do jogo: **snes-mod-factory**.

## Pipeline (1 comando → 1 imagem → 1 pergunta)

```
1. captura      fab sprite snap <jogo> --state <s> --macro <txt> --frames "0-600:4" --label mov
2. export       fab ai export --capture runs/<cap> [--capture …] --palette <p> --out games/<jogo>/exports/<nome> --name <nome> [--bloco 8] [--mudanca "…"]
3. no Nano Banana: enviar sheet.png + colar o prompt EN do prompt.md (imagem de referência opcional)
4. import       fab ai import --map games/<jogo>/exports/<nome>/map.json --image <devolvida>.png --out runs/<imp>
5. transpor     fab ai import … --mod mods/<id> --name <nome> --evidence "…"  →  fab build  →  fab paint check / fab gfx check
```

- **Alvo**: `--palette <paleta OAM>` (estável entre frames; ex.: 6 = Ken) ou `--object N`. O desenho de cada pose é
  composto a partir dos TILES da **corrida de OAM** do alvo (o motor escreve cada objeto numa corrida contígua de
  entradas — fica de fora o lixo PARCADO fora do ecrã e objetos de outras corridas) e validado contra a **lista de
  cels do motor** (só o que a pose desenha; efeitos de outras rotinas caem). Capturar com `fab sprite snap --engine`
  para gravar a lista de cels; sem ela, o filtro é pulado. Cada píxel tem dono conferido: `mismatch_dono: 0` = export
  fiel ao que o jogo mostra.
- **Uma paleta por export** (paleta OAM p = CGRAM p+8). Folha multi-paleta = um export por paleta.
- **Fundo CALCULADO**: por omissão (`--fundo auto`) escolhe-se a cor com máxima distância à paleta do personagem —
  contraste máximo para o modelo e keying robusto do índice 0. `--fundo "#rrggbb"` fixa uma (tem de ficar fora da
  paleta: o export recusa coincidências).

## O que sai do `fab ai export`

| ficheiro | o quê |
|---|---|
| `sheet.png` | tilesheet EXPANDIDA (bloco N×N por píxel de arte) para o modelo editar |
| `sheet-1px.png` | referência 1 px por píxel (para conferir) |
| `map.json` | **o mapa na memória**: por pose id/célula/caixa_expandida/índices/tiles (hash, caixa, flips, VRAM) + bytes dos tiles + paleta |
| `prompt.md` | prompt EN (colar no Nano Banana) + PT; estrutura LOCK/CHANGE/CONSTRAINTS |
| `report.md` | poses, cobertura, como usar |

- `--bloco N` força o tamanho; por omissão o auto até `--max` (3072 = teto de ENTRADA do Gemini; 1024 = bucket 1K).
  Blocos ≥ 8 toleram melhor o blur do modelo; o import aceita qualquer tamanho de saída (re-escala por blocos).
- O `map.json` cobre os dois mundos (Q6.1 da pesquisa): **id estável + célula (grelha) + rect em píxeis**, mais
  flips/VRAM/bytes 4bpp para transpor para SNES (Q7).

## O prompt (o que a pesquisa mostra que funciona)

- **LOCK** primeiro (grelha de blocos, layout das células, fundo, paleta com hex exatos) + **CHANGE** (uma
  mudança só) + **CONSTRAINTS** (sem anti-aliasing/gradientes; cada bloco UMA cor; pedir o MAIOR tamanho de saída).
- Cláusulas oficiais: "change only the [specific element]… Keep everything else in the image exactly the same" e
  "Do not change the input aspect ratio" (guia Google).
- Paleta/grelha NÃO são garantidas por prompt ("16 colors max" já rendeu 528 tons): o import é que garante.
- **Não há parâmetro de máscara na API Gemini** — região confina-se por texto; espere leakage e use o import para
  verificar. Uma mudança por mensagem; para consistência de personagem, imagem de referência + mesma conversa.

## O que faz o `fab ai import`

1. **Alinhamento**: a imagem devolvida pode ter qualquer tamanho; mede-se a escala e procura-se o offset global
   que maximiza a concordância com os índices originais (a votação tolera deslocações até ~meio bloco).
2. **Re-quantização por bloco**: voto maioritário do INTERIOR do bloco → índice da paleta (o fundo vira índice 0).
   Pureza do voto < 0.7 = **bloco sujo** (o "quadrado que não ficou correto") → sinalizado em `check.png` (vermelho)
   e `report.md`; `--limpar auto` herda a moda dos vizinhos limpos quando há maioria clara.
3. **Plano de tiles**: cada píxel alterado resolve-se para (tile, píxel no tile) — flips incluídos — e os tiles
   novos saem em `plan.json`. Conflitos (o mesmo píxel com valores diferentes em poses diferentes) são REPORTADOS,
   nunca escolhidos às cegas; píxeis novos sem tile dono = `fora_do_alvo` (exigiriam tiles/OAM novos).
4. `--mod mods/<id> --name … --evidence …` grava no `paint.json`: tiles crus = patch de dados; comprimidos/WRAM =
   `vram_tiles` (servidos pelo `fab gfx override`). Depois `fab build` + `fab paint check` / `fab gfx check`.

## Verificação (só confie num export com isto verde)

```
fab ai roundtrip --map games/<jogo>/exports/<nome>/map.json
```
- **identidade**: importar a folha original tem de dar 0 píxeis alterados, 0 tiles no plano ("PERFEITO").
- **perturbação**: deslocamento + blur → o import realinha e recupera ≥99% dos píxeis; os sujos são sinalizados.

## Exemplo real — Ken (SFA2)

`games/sfa2/exports/ken-moveset/`: 41 poses COMPLETAS do moveset (macros `luta.txt` + `livre.txt`, 252 frames,
capturadas com `--engine`; poses iguais fundem-se), 1131 tiles únicos, **cor 0 apenas** (gi vermelho), paleta
CGRAM 14, **bloco 16** (folha 10128×10864 — quadrados grandes: mesmo com devolução a 4K cada quadrado sai ≥6 px,
logo a conversão de volta à arte é limpa), fundo AZUL #00A0F8 CALCULADO por contraste máximo. Validação:
`mismatch_dono: 0` (composto = exatamente o que o jogo mostra). Round-trip: identidade 0 alterações; perturbação
(deslocação + blur) recuperada a 100%.
⚠ Nota SFA2: nas poses de dano/queda, o "fogo" de impacto faz PARTE das listas de cels do próprio Ken (o jogo
guarda o efeito dentro da pose da vítima) — não é artefacto de extração.
Mapa + prompt gerados JUNTOS e prontos para o Nano Banana.

## FAQ

- **O modelo devolveu tamanho/proportção diferente.** O import re-escala por blocos (mesmo aspect ratio); se o
  aspect ratio mudou, o import recusa — peça o mesmo aspect ratio.
- **Muitos blocos sujos.** Peça ao modelo "flat solid colors, no anti-aliasing" e maior resolução de saída; blocos
  maiores (--bloco 8+) sobrevivem melhor. Depois `--limpar auto`.
- **Quero editar só uma parte.** O prompt confina por texto (não há máscara na API); edite uma região por pedido
  e use o `check.png` para ver se o resto ficou intacto.
- **Apareceram píxeis novos fora do desenho original.** São `fora_do_alvo`: não se transpõem sem tiles/OAM novos
  (caminho C da snes-sprite-paint).
- **Duas poses usam o mesmo tile e o modelo editou-as de forma diferente.** O plano REPORTA o conflito; escolha a
  versão certa (ou edite de novo com a mudança aplicada de forma consistente).
