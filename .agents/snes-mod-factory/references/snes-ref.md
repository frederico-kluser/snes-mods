# Referência rápida de SNES para mods

## CPU 65C816 (Ricoh 5A22)
- Registrador P: `N V M X D I Z C` (bits 7..0) + E (emulação, oculto). **M = bit 5 ($20)**: 1 → A de 8 bits.
  **X = bit 4 ($10)**: 1 → X/Y de 8 bits. `SEP #$20` → A 8 bits · `REP #$20` → A 16 bits ·
  `SEP/REP #$10` → índices · `#$30` → ambos. PLP/RTI/XCE restauram/alteram flags (estado incerto na análise estática).
- Imediatos com largura variável: `LDA/ADC/SBC/AND/ORA/EOR/CMP/BIT #` seguem M; `LDX/LDY/CPX/CPY #` seguem X.
- Saltos longos: `JSL` ($22 ll hh bb, empilha 3 bytes, volta com `RTL`) · `JML` ($5C ll hh bb, sem retorno).
  `JSR`/`RTS` ficam no banco atual. Os dois longos têm **4 bytes**.
- DP (direct page) usa o registrador D (quase sempre $0000) e acessa SEMPRE o banco $00 → WRAM baixa.
  Absolutos (`LDA $1234`) usam o DB (banco de dados): nos bancos $00-$3F/$80-$BF, $0000-$1FFF é WRAM
  e $2100-$5FFF é I/O. Fora desses bancos (ex.: DB=$7E ou ROM $C0+) o mesmo `$1234` é outra coisa.
  No freecode, use `sta.l $7E1234` (long) quando não tiver certeza do DB.
- Vetores (banco $00): nativo COP $FFE4, BRK $FFE6, NMI $FFEA, IRQ $FFEE; emulação RESET $FFFC, NMI $FFFA, IRQ/BRK $FFFE.

## Mapas de memória
| mapa | endereço CPU → offset no arquivo (sem cabeçalho) |
|---|---|
| LoROM | `((banco & $7F) << 15) + (addr - $8000)`, addr ≥ $8000; bancos $80+ = FastROM |
| HiROM | `((banco & $3F) << 16) + addr` em $C0-$FF (e $40-$7D); espelho em $00-$3F/$80-$BF:$8000-$FFFF |
| ExHiROM | $C0-$FF → primeiros 4 MB; $40-$7D → 4 MB+ |
| SA-1 | MMC padrão (`sa1rom` do Asar e do `fab`): $00-$3F:8000+ = 1.º e 2.º MiB, $80-$BF:8000+ = 3.º e 4.º MiB (**não** é espelho FastROM); $C0-$FF = os 4 MiB lineares, vista usada pelo ghidra-snes. O jogo pode reprogramar o MMC ($2220-$2223) |
| WRAM | $7E:0000-$7F:FFFF (128 KiB); espelho $0000-$1FFF nos bancos $00-$3F/$80-$BF |
| SRAM | LoROM: $70-$7D:$0000-$7FFF (típico) · HiROM: $20-$3F/$A0-$BF:$6000-$7FFF |
- Cabeçalho SMC: arquivo com tamanho % 1024 == 512 → 512 bytes de copiadora no início (o `fab rom add` remove).
- Cabeçalho interno: $00:FFC0 (LoROM → offset $7FC0; HiROM → $FFC0): título (21), map mode ($FFD5),
  chipset ($FFD6), tamanho ($FFD7: 2^n KiB), SRAM ($FFD8), região, versão, complemento + checksum ($FFDC-$FFDF).
- **Asar `freecode`** só procura espaço em bancos **$10-$3F** (precisa de ROM ≥ 1 MiB em LoROM). ROM de
  512 KiB → `"expand_to": "1MB"` no mod.json (o build preenche com $00 e corrige o byte de tamanho).
  `freedata` prefere bancos sem espelho de RAM ($40-$6F, $F0-$FF) — no S-DD1 esses bancos não são vistos pela CPU
  nos mesmos endereços: dado que a CPU/DMA lê vai em `freecode` (o `fab gfx override` já faz isso).
- O Asar respeita etiquetas RATS (`STAR` + tamanho): não aloca espaço livre dentro delas (os blobs do fab têm uma).

## Chips e ROM expandida
- **S-DD1** (SFA2, Star Ocean): `$00-$3F/$80-$BF:8000-FFFF` = LoROM fixa só dos 2 primeiros MiB; `$C0-$FF` = 4
  janelas HiROM de 1 MiB escolhidas por `$4804-$4807` (reset 0/1/2/3); `$40-$7D` não mapeiam ROM. Descomprime no
  DMA: `$4800` liga canais, `$4801` arma o próximo DMA de cada canal (zera ao terminar); o chip vigia o endereço que
  o jogo escreve em `$43x2-$43x4` e só descomprime leituras nas janelas `$C0-$FF` (canal de fonte FIXA).
- **Acima de 4 MiB no S-DD1** o conteúdo só aparece trocando uma janela: o `fab gfx override --expand` grava na
  área nova e troca `$4807` (janela `$F0-$FF`) só durante o DMA, com IRQ desligado, devolvendo o valor do reset.
- Quem roda S-DD1 expandido (código-fonte lido em 2026-10-25): **Mesen2/MesenCE** — página = registro & `$0F`, ROM
  fora de potência de 2 espelhada até a próxima (verificado no fab com 5 MiB); **bsnes/higan** — registro & `$8F`,
  página & `$0F`; **snes9x** — página = valor & 7 e S-DD1 com **8 MiB ou mais** é tratado como "conversão
  descomprimida" (quebra): fique abaixo de 8 MiB; **FXPak Pro** — firmware 1.11.1 reconhece S-DD1 acima de 48 Mbit
  (não testado). Fontes: `Core/SNES/Coprocessors/SDD1/` do Mesen2, `sfc/coprocessor/sdd1/sdd1.cpp` do bsnes,
  `ppu.cpp`/`memmap.cpp` do snes9x, notas de versão do FXPak. O build repete isso em `rom_expandida`.

## Registradores de I/O mais úteis
| endereço | nome | uso |
|---|---|---|
| $2100 | INIDISP | brilho / forced blank |
| $2101 | OBSEL | tamanho/base dos sprites |
| $2102-$2104 | OAMADD/OAMDATA | sprites |
| $2105 | BGMODE | modo de vídeo |
| $2107-$210C | BGxSC / BGxxNBA | tilemaps / tiles dos BGs |
| $210D-$2114 | BGxHOFS/VOFS | scroll |
| $2115-$2119 | VMAIN/VMADD/VMDATA | VRAM |
| $2121-$2122 | CGADD/CGDATA | paletas |
| $212C-$212D | TM/TS | camadas ligadas |
| $2140-$2143 | APUIO0-3 | comunicação com o SPC700 (som) |
| $4200 | NMITIMEN | NMI/IRQ/auto-leitura do controle |
| $420B / $420C | MDMAEN / HDMAEN | DMA / HDMA |
| $4210 | RDNMI | reconhece NMI |
| $4212 | HVBJOY | bit 0 = leitura automática do controle em curso |
| $4218/$4219 | JOY1L/JOY1H | controle 1 |
| $4300-$437F | DMAPx… | canais de DMA |
- JOY1H ($4219): `B Y Select Start Up Down Left Right` (bit 7..0) · JOY1L ($4218): `A X L R 0 0 0 0`.
  Jogos copiam isso para variáveis na DP (ex.: "mantidos" e "novos neste frame" = `novo & ~anterior`).

## Sprites (OBJ), paletas e o que medir em vez de supor
- **Paleta de sprite = linha p+8 da CGRAM**: o atributo do OAM (`vhoopppN`) traz p = 0-7 → cores `128+16p`…
  `143+16p`. Em Mode 1 os BGs de 4 bpp usam as linhas 0-7 (cores 0-127) e o BG3 (2 bpp) grupos de 4 cores.
  Índice 0 de cada paleta é transparente; a cor 0 da CGRAM é o fundo (backdrop).
- OAM: 128 × 4 bytes (X baixo, Y, tile, atributo) + 32 bytes da tabela alta (2 bits/sprite: bit 8 do X,
  tamanho). OBSEL (`$2101` = `ppu.oamMode/oamBaseAddress/oamAddressOffset` no Mesen) dá os 2 tamanhos e a base
  dos tiles (em PALAVRAS). Tile de sprite grande: coluna soma no nibble baixo, linha no alto (com volta em 16).
- Por linha: só os 32 primeiros sprites (range over) e 34 fatias de 8 px (time over). As fatias são carregadas
  do ÚLTIMO sprite da linha para o primeiro → no time over quem some são os de MAIOR prioridade (menor índice).
- **Falsa cor**: trocar a CGRAM inteira por cores-código no começo do frame (e devolver no fim) faz a imagem
  dizer o índice da CGRAM de cada píxel visível — de qualquer camada, sem conhecer o jogo (`fab sprite snap`).
  Píxel misturado (color math/brilho) não decodifica (vira −1).
- **Quando tirar o snapshot do PPU**: com o display LIGADO. Jogos que esticam o VBlank com forced blank (SFA2:
  imagem só nas linhas ~24-215, DMA fora disso) têm OAM/VRAM do frame seguinte já no `endFrame`; o harness
  espera o 1.º IRQ/NMI com o display ligado. O render × falsa cor tem de concordar ~100% (o report mostra).
- **VBlank é curto** (~37 linhas no NTSC, menos o DMA do jogo): código de hook rodando no NMI que demora demais
  empurra o DMA para dentro da imagem (sprites/gráficos corrompem). `fab paint check` compara a linha de cada
  DMA mod × base e acusa o estouro.
- **Todo hook muda o timing da CPU**: jogos que sorteiam com o tempo (IA de luta) jogam diferente desde o 1.º
  frame. Base de comparação de mod com código = o próprio mod com a mudança desligada por VALOR
  (`mod.json → baseline.variant`), nunca a ROM limpa.

## Code/Data Log do MesenCE (`fab re cdl`)
Byte por byte da ROM: $01 código · $02 dado · $04 alvo de salto · $08 entrada de sub-rotina ·
$10 X a 8 bits · $20 M a 8 bits (os dois últimos só no 1º byte de cada instrução executada).
O `fab re analyze` usa as entradas ($08) como sementes com o M/X observado.

## memType do Lua do MesenCE (harness)
`snesMemory` (barramento da CPU, relativo) · `snesDebug` (idem sem efeitos colaterais) ·
`snesWorkRam` (WRAM absoluta, cobre todos os espelhos) · `snesPrgRom` (offset na ROM) ·
`snesSaveRam` · `snesVideoRam` · `snesSpriteRam` · `snesCgRam`.
Savestates só podem ser criados/carregados dentro de callback de execução da CPU principal (o harness cuida).
`emu.getState()` traz o PPU (`ppu.scanline`, `ppu.forcedBlank`, `ppu.oamMode`, `ppu.vramAddress`…) e os canais de
DMA (`dmaController.channel[N].srcAddress/srcBank/destAddress/transferSize…`) — use isso e não `emu.read` em
`$43xx`: no S-DD1 o `Peek` (leitura de depuração) de `$4000-$4FFF` devolve 0; a leitura da CPU funciona (o hook
pode ler `$43xx`).
Eventos úteis: `startFrame` (linha 0), `endFrame` (linha ~225), `irq`, `nmi`.
