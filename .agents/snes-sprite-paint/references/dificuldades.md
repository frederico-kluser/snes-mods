# As 16 dificuldades do mod das luvas (SFA2) → a técnica/ferramenta que as resolve em QUALQUER jogo

Origem: o diário técnico em `games/sfa2/notes.md` (sessão de 2026-10-25). Cada linha: o que custou caro, o que
agora faz isso automaticamente, e o que ainda é decisão do agente.

| # | dificuldade (antes) | agora (ferramenta/técnica) | o agente ainda decide |
|---|---|---|---|
| 1 | descobrir que a paleta do sprite é `p+8` na CGRAM (pokes, dumps, horas) | `fab sprite snap`: o render da camada de sprites (OAM+VRAM) e a **falsa cor** (CGRAM trocada por cores-código num frame) dão, por píxel, o índice da CGRAM; o report já escreve "paleta OAM 6 = CGRAM 14" e acha a paleta na WRAM e na ROM | qual objeto é o personagem (overview.png) |
| 2 | Asar montou `lda #$08` com 16 bits (o `00` virou BRK) | `fab build` desmonta o NOSSO código com o M/X declarado e compara com o mapa endereço→linha do Asar: tamanho errado = erro com arquivo:linha; os geradores escrevem `.b/.w` em todo imediato | nada (só ler o erro) |
| 3 | duas listas de cels para a mesma pose (18 runs sem efeito) | rótulos por **conteúdo do tile** (hash dos 32 bytes + píxel) valem em qualquer pose/slot; o censo agrupa pendentes repetidos ("×20") | rotular por número nas folhas |
| 4 | `org` LoROM × endereço de execução do S-DD1 (escrita no motor de sprites) | `paint set/remap/oam-mirror` geram o `org` pelo mapa (`rom.asar_org`); `data[]` aceita `"pc"`; o build **recusa** sobrescrita não declarada | nada |
| 5 | evidência de M/X ignorada (endereço canônico × de execução) | o build casa o hijack pelo **offset no arquivo** (qualquer espelho: `00:82CB` ≡ `80:82CB`, `C0:0312` ≡ `80:8312`) | medir o M/X (o `fab ppu dma` já traz o do ponto do DMA) |
| 6 | freecode acabou | o gerador de nível 2 é enxuto (≈ 0,8 KiB com tabelas); o build mostra o erro do Asar | escolher o que cortar |
| 7 | o mesmo tile é luva numa pose e cabelo noutra | `fab sprite census` mede a **separabilidade** (nível 1-4) e lista tiles seguros × ambíguos; nível 4 sai mudando o desenho com `--part` (cru ou comprimido) | escolher o mecanismo pela tabela da skill |
| 8 | filtro de conflito pela caixa do blob (punhos ficavam loiros) | decisão por **píxel rotulado** (não por caixa nem "maior blob = cabelo"); `fab sprite marks --max-other-px` mostra o custo de cada tolerância | quanto resíduo aceitar (com números) |
| 9 | todo hook desloca o RNG: checks contra a ROM limpa nunca passam | base **variante** no ciclo (`baseline.variant`: mesma fonte, só valores mudam) + conferência de que a variante não muda opcode + **sincronia pela WRAM** | escrever o `if defined(...)` que troca só valores |
| 10 | "flash" de dano escreve a paleta por fora da rotina hookada | o ciclo A/B acusa (o check de cópia fiel do espelho falha nesses frames) e o `fab ppu dma` mostra todos os caminhos de paleta | se vale um hook a mais |
| 11 | sonda exec no freecode "mentia" | era endereço velho: `fab probe exec <jogo> <Rótulo> --mod <id>` resolve o rótulo no build ATUAL; e a verificação é por efeito (`paint check`) | nada |
| 12 | faltavam poke/intervalos/mais hits | `--poke` (frames `*`, `A-B`), `--probe-max`, e agora snapshot do PPU, falsa cor, log de DMA e dumps por frame no harness | nada |
| 13 | dado declarado contado como freespace | `data[]` ganha de freespace; regiões vizinhas do `paint` são juntadas | nada |
| 14 | testes "falhando" pelo Python errado | rode `./fab selftest` (usa a `.venv`) | nada |
| 15 | CI vermelho por título de PR > 72 / F401 | `oss-gate.sh` + `ruff` antes de subir | nada |
| 16 | métrica de "ouro" contava o fogo da Rose | as medidas usam o **dono do píxel** (objeto/paleta/tile), não a cor da tela | nada |

## Gráfico comprimido (resolvido sem codec, 2026-10-25)
- `fab gfx dump` exporta o tileset pelo que chega na VRAM (já descomprimido) e grava cada upload com a fonte do DMA.
- `fab gfx override` serve o desenho EDITADO no próprio disparo do DMA: cópia crua na ROM + tabela; fonte na WRAM →
  impressão digital separa os conteúdos do mesmo buffer; chip que descomprime no DMA → canal volta a andar,
  `--chip-disarm` desarma o chip e, depois do DMA, o hook devolve o DMAP e a fonte (há jogo que escreve o DMAP uma
  vez só). `--expand` resolve ROM cheia (S-DD1: área acima de 4 MiB lida pela janela $F0-$FF).
- Validado: testbed (dois desenhos no mesmo buffer da WRAM, modos espaço livre e blob) e um S-DD1 real (ROM de
  5 MiB: 35 tiles trocados, 0 colaterais, `fab gfx check` OK).
- Codecs e descompressores de terceiros **não entram** (regra de descoberta própria do README): nada de recomprimir.

## O que ainda NÃO é automático (limites honestos)
- O override cobre os disparos de DMA que os cenários do dump mostraram (junte states/macros); upload não linear
  (remapeamento/incremento especial da VRAM) e fontes que não são ROM nem WRAM (porta de dados de chip, BW-RAM do
  SA-1) ficam de fora; disparo que liga vários canais comprimidos ao mesmo tempo com `--chip-disarm` gera aviso.
- Nível 3 (decisão por pose) depende do motor do jogo: há adaptador para **listas de cels** (`game.json →
  sprite_engine`, `fab sprite marks`); outros motores precisam de um adaptador novo.
- Hook no escritor do OAM (alternativa ao hook no VBlank quando o tempo livre é pouco): ainda manual.
- Camadas de BG: cor e paleta são genéricas (falsa cor); rótulo de PEÇA em BG (por tile do mapa) não existe.
