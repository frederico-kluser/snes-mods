---
name: snes-sprite-paint
description: Pintar e mudar sprites de QUALQUER jogo de SNES passo a passo, decidindo só com imagens numeradas e texto — trocar a cor de roupa/cabelo/personagem/retrato/HUD/cenário, pintar só uma PARTE que divide cor com outra (luva × cabelo), mudar o DESENHO dos tiles (crus na ROM ou comprimidos/montados na WRAM, sem codec) e verificar píxel a píxel sem vídeo. Comandos fab sprite/palette/paint/gfx/ppu. Use SEMPRE que o pedido for "muda a cor de…", "deixa o personagem de roupa X", "pinta só a luva/o cabelo", "troca a paleta", "muda o sprite/desenho", "recolorir", "skin", "outfit", "exporta o tileset", ou quando for preciso saber que índice/paleta/tile pinta uma coisa na tela.
---

# Pintura e mudança de sprites — qualquer ROM de SNES

Feito para quem decide **só olhando imagens e lendo texto** (inclusive LLMs mais fracas): cada passo é
**1 comando → 1 imagem → 1 pergunta**. Endereço, `org`, M/X, hijack e verificação são das ferramentas — **nunca
calcule endereço à mão**: copie o comando que vem em `proximo`.

Antes: `./fab doctor --quick`, ROM registrada, um savestate com o alvo na tela e um mod (`fab mod new <id> --game
<jogo>`) — fluxo geral na **snes-mod-factory**. Sem ROM comercial: **Treino** no fim.

## 0. Uma vez por jogo: de onde vêm paleta, OAM e gráficos
`./fab ppu dma <jogo> --state <state> --frames 60` → leia `resumo`: o **buffer de paletas** na WRAM (e quem o copia
para a CGRAM), a **sombra do OAM** e se os **gráficos** vêm crus da ROM ou comprimidos. Anote na skill `rom-<jogo>`
e guarde o `run` (o `fab paint oam-mirror` usa).

## 1. Fotografar a cena (sempre primeiro)
`./fab sprite snap <jogo> --state <state> --frames 60` e abra, nesta ordem:
1. `overview.png` — sprites numerados. *Qual número é o alvo?*
2. `bg.png` — áreas de BG numeradas (B1, B2…: retrato, HUD, cenário). *O alvo está aqui?*
3. `objN-indices.png` (ou `bgN-indices.png`) — um painel por índice de cor (magenta = onde aparece). *Quais painéis
   são a parte a pintar?* (ex.: 9-13 = a roupa)
4. `report.md` — cores e **de onde vem a paleta** (ROM PC e WRAM); os próximos comandos já usam isso.

O report aplica o hardware: sprite usa a paleta **p+8** da CGRAM (OAM 6 = CGRAM 14); índice 0 é transparente.
⚠ O mesmo personagem pode ter outra paleta em outra tela (luta × retrato × VS): fotografe cada uma.

## 2. Que caminho seguir
| o que muda | caminho |
|---|---|
| a COR de partes inteiras (tudo o que usa aqueles índices) | **A** |
| a cor de UMA parte que divide os índices com outra (luva × cabelo no mesmo dourado) | **B** |
| o DESENHO (trocar índices dentro dos tiles) | **C** |

A ou B? No `objN-indices.png`, se o magenta dos índices acende também algo que NÃO deve mudar → **B**.

## A — recolorir índices inteiros (só dados)
```
./fab palette ramp <captura> --object N --indices 9-13 --to azul      # ou --bg N / --cgram-palette P
```
`--to`: nome (azul, preto, rosa, verde-escuro, dourado…), `#rrggbb` ou `$BGR555`; copiar de outro personagem:
`--copy-from <PC da paleta dele>:9-13`. Abra `rampas.png` (A fiel · B contraste · C suave · D artística, ampliado e
em 1x). *Qual letra fica melhor e mantém o volume?* Recuse ✗ (tons iguais achatam; tom igual ao contorno derrete).
Nunca um tom só para a peça inteira. Depois copie o `proximo`, trocando só cores e nome:
```
./fab paint set mods/<id> --pc 0x1F0260 --indices 9-13 --colors "$7E06,$7102,$60A1,$5060,$4440" --name gi-azul --evidence "…"
./fab build mods/<id> && ./fab paint check mods/<id> --state <state>
```
`check-fNNNNN.png`: **verde** mudou certo · **vermelho** mudou o que não devia · **laranja** cor errada · **amarelo**
faltou. Só aceite `OK … 0 colaterais`.

## B — uma parte que divide os índices com outra
1. `./fab sprite regions <captura> --object N --indices 14,15` → *quais números são a parte?*
2. Rótulo pelo CONTEÚDO do tile (vale em qualquer pose): `./fab sprite label <captura> --object N --indices 14,15
   --regions 2,3 --part luva --rest cabelo --store games/<jogo>/parts/<objeto>.json`
3. Censo em muitos frames (macro com golpes/andar): `./fab sprite census <jogo> --store … --target luva --state <s>
   --macro <m> --frames 0-598:2` → `pendentes-01.png` (corpo inteiro + zoom). Rotule uma peça por vez (`fab sprite
   label --pending <census> --items 2,3 --part luva --store …`); **na dúvida, não rotule**. Repita até
   `cobertura_media ≥ 0,99`.
4. `resumo.separabilidade.nivel` diz o mecanismo:

| nível | significa | faça |
|---|---|---|
| 1 | nenhuma outra peça usa esses índices | caminho A |
| 2 | cada nº de tile é sempre de uma peça só | `fab paint oam-mirror` (abaixo) |
| 3 | o mesmo tile é a peça numa pose e outra noutra | marca por pose/cel (motor de lista de cels: `fab sprite marks`) |
| 4 | há sprites com as DUAS peças | separar 100% só mudando o desenho: caminho C com `--part` |

Nível 2 — gerador (paleta-espelho só para os tiles da peça; paleta livre = linha sem uso no `palettes.png`):
```
./fab paint oam-mirror mods/<id> --from-dma <run do ppu dma> --from-census <census> --src-palette 6 --mirror-palette 3 \
    --colors "14:$2908,15:$1084" --evidence "…"
./fab build mods/<id> && ./fab paint check mods/<id> --state <state> --frames 30,90
```
`ESTOURO DE VBLANK` no check = o código não cabe no tempo livre do jogo: não entregue.

## C — mudar o desenho (cru ou comprimido, sem codec)
1. **Ver os tiles**: por objeto, `./fab sprite tiles <captura> --object N [--part luva --store …]`; o tileset inteiro,
   numerado e com a origem: `./fab gfx dump <jogo> --state <s> [--state <s2>] [--macro …] --frames 600` →
   `tiles-NN.png` (**verde** cru na ROM · **laranja** comprimido por chip · **azul** montado na WRAM · **cinza** já
   estava na VRAM). O dump só vê o que os cenários CARREGAM: comece antes do carregamento (power-on, menu, troca de pose).
2. **Editar** (troca de índices; `--part` limita aos píxeis rotulados — separa luva e cabelo dentro do mesmo tile):
   - pelo objeto: `./fab paint remap mods/<id> --capture <captura> --object N --map 14:9,15:12 [--part luva --store …] --name … --evidence …`
   - pelos números da folha: `./fab gfx override mods/<id> --dump <dir> --tiles 12,13,40-45 --map 14:9 --name … --evidence …`

   Desenho **cru** vira patch de dados. Desenho **comprimido/WRAM** vai para o override: `./fab gfx override mods/<id>
   --dump <dir>` gera o hook no disparo do DMA, que serve a cópia editada (impressão digital separa conteúdos do
   mesmo buffer da WRAM). Opções: `--expand` (ROM sem espaço; no S-DD1 a área nova fica acima de 4 MiB, lida pela
   janela $F0-$FF) e `--chip-disarm <reg>=<valor>` (chip que descomprime no DMA: o registro que o jogo arma antes do
   DMA comprimido, achado com `fab probe writes`).
3. **Verificar**: `./fab build mods/<id>` → `./fab gfx check mods/<id> --dump <dir>` (VRAM: o desenho novo chegou, o
   velho sumiu, 0 colaterais) → sprite na tela: `./fab paint check`.

⚠ Mudar o desenho muda o tile em TODAS as roupas/paletas que o usam.

## Regras que viraram ferramenta
- `paint set/remap/oam-mirror` e `gfx override` geram o `org` certo para o mapa e declaram `data[]`/`hijacks[]`.
- O build recusa sobrescrita não declarada, hijack sem M/X e imediato com tamanho errado (arquivo:linha).
- Sonda de código do mod pelo NOME: `fab probe exec <jogo> <Rótulo> --mod <id>`. Verifique por EFEITO.
- Armadilhas e a ferramenta que resolve cada uma: `references/dificuldades.md`.

## Treino (sem ROM comercial: o testbed)
```
./fab sprite snap testbed --state parado --frames 5               # 1 sprite (boneco): paleta OAM 0 = CGRAM 8
./fab palette ramp <captura> --object 1 --indices 1 --to azul     # rampas para o vermelho do boneco
./fab gfx dump testbed --frames 30                                # do power-on: 5 tiles crus + 4 montados na WRAM
./fab gfx override mods/<id> --dump <dir> --tiles <nº do tile em $1000> --map 1:3 --name xadrez --evidence "treino"
```
Os testes ponta a ponta (`tests/test_e2e.py`) fazem A (paint set), C cru (remap), C comprimido (gfx override nos
dois modos: espaço livre e blob) e o nível 2 (oam-mirror) — são exemplos completos.

## FAQ
- **O mod não mostra a cor nova no começo.** O savestate traz a paleta já carregada: o `paint check` acha sozinho o
  frame em que o jogo recarrega; nos cenários, use `warmup`.
- **A paleta aparece em mais de um lugar da ROM.** O check mostra qual o jogo usa; se faltar píxel, troque o `--pc`.
- **O tile que quero não está no dump.** Ele foi carregado antes do state: refaça o dump a partir de um state anterior.
- **`gfx check` acusa desenho velho.** Há um disparo de DMA que o dump não viu: junte states/macros no dump e refaça o override.
- **Mod com código e os checks contra a ROM limpa falham.** Hook muda o RNG: base variante (FAQ da **snes-mod-cycle**).
- **A ROM cresceu (`--expand`). Onde roda?** O build traz `rom_expandida` com os emuladores (MesenCE/Mesen2 e bsnes;
  snes9x só abaixo de 8 MiB no S-DD1).
- **Exemplo real?** SFA2 (Ken): paleta OAM 6 = CGRAM 14, gi = índices 9-13, paleta `7E:06C0`/ROM `0x1F0260`; luvas
  e cabelo dividem 14-15 (nível 4); o desenho do gi, comprimido pelo S-DD1, foi trocado sem codec com
  `gfx override --expand` (skill `rom-street-fighter-alpha`, print 50).
