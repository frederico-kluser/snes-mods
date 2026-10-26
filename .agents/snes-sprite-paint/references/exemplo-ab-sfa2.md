# Exemplo trabalhado: base A/B por variante num mod com código (SFA2, luvas do Ken)

Técnica genérica (dificuldade 9): todo hook muda o timing da CPU e jogos que sorteiam com o tempo jogam
diferente desde o 1.º frame. Comparar contra a ROM limpa faz os checks alinhados falharem sem o mod estar
errado (no `sfa2-ken-azul-e-rosa`, o ciclo 4 deu 21/46 por isso).

## O que foi feito (ciclo 5 do `sfa2-ken-azul-e-rosa`, 2026-10-25 — experimento da técnica)
1. No `patch.asm`, a variante desliga a pintura trocando só os VALORES escritos (as 2 cores da luva voltam ao
   ouro original da cor 2):
   ```asm
   !luva_realce = $2908
   !luva_sombra = $1084
   if defined("LUVA_OFF")
       !luva_realce = $339E   ; ouro original (índice 14 da paleta em 0x1F02A0)
       !luva_sombra = $029C   ; (índice 15)
   endif
   ```
2. No `mod.json`: `"baseline": {"variant": {"name": "off", "defines": {"LUVA_OFF": "1"}}}`.
3. Checks reescritos para a base variante: valores ABSOLUTOS das cores novas (ex.: `count(gi1 == 0x2908) >=
   0.8*len(gi1)`), igualdade com a base no resto (`all(pele == baseline.pele)`) e SINCRONIA da luta
   (`all(x1 == baseline.x1) and all(hp1 == baseline.hp1)`), que contra a ROM limpa nunca valia.

## Resultado medido
- `variant_safety`: a variante difere do mod em 8 bytes (4 operandos de cor + checksum), nenhum opcode.
- Sincronia pela WRAM: 0-4 bytes diferentes nos 7 cenários (só os 2 tons da luva no espelho).
- 35/36 checks (antes 21/46). O check que falhou era REAL: em 7/560 frames (choque elétrico, flashes de dano)
  a paleta do Ken muda por um caminho que não passa pelo buffer copiado pelo hook → o espelho fica diferente
  por 1 frame (dificuldade 10, agora medida).
- O compare sincronizado mostrou um defeito que as métricas antigas (contagem de "blobs" de ouro) escondiam:
  nas cambalhotas (Ken de cabeça para baixo, f316/f492) mechas do CABELO ficaram pretas — marcas de cel
  geradas pela heurística "o maior blob é o cabelo". Rótulos por conteúdo (`fab sprite label/census`) e o
  nível de separabilidade (4) explicam e quantificam isso.
- Checks antigos com bug achados no caminho: `esp1 == gi1` comparava o índice 1 do espelho com o 9 da
  paleta; `esp14 == 0x339E` na cor 0 (cujo ouro é `$12DE`).

A pedido do dono, o mod voltou ao estado anterior (o pedido era criar técnicas, não resolver o mod); o ciclo 5
ficou no ledger como registro do experimento. Para aplicar a técnica: repita os passos 1-3.
