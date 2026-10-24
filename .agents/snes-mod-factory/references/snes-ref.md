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
| SA-1 | LoROM nos bancos $00-$3F/$80-$BF + $C0-$FF linear (MMC configurável!) |
| WRAM | $7E:0000-$7F:FFFF (128 KiB); espelho $0000-$1FFF nos bancos $00-$3F/$80-$BF |
| SRAM | LoROM: $70-$7D:$0000-$7FFF (típico) · HiROM: $20-$3F/$A0-$BF:$6000-$7FFF |
- Cabeçalho SMC: arquivo com tamanho % 1024 == 512 → 512 bytes de copiadora no início (o `fab rom add` remove).
- Cabeçalho interno: $00:FFC0 (LoROM → offset $7FC0; HiROM → $FFC0): título (21), map mode ($FFD5),
  chipset ($FFD6), tamanho ($FFD7: 2^n KiB), SRAM ($FFD8), região, versão, complemento + checksum ($FFDC-$FFDF).
- **Asar `freecode`** só procura espaço em bancos **$10-$3F** (precisa de ROM ≥ 1 MiB em LoROM). ROM de
  512 KiB → `"expand_to": "1MB"` no mod.json (o build preenche com $00 e corrige o byte de tamanho).
  `freedata` = bancos sem espelho de RAM ($40-$6F, $F0-$FF).

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

## Code/Data Log do MesenCE (`fab re cdl`)
Byte por byte da ROM: $01 código · $02 dado · $04 alvo de salto · $08 entrada de sub-rotina ·
$10 X a 8 bits · $20 M a 8 bits (os dois últimos só no 1º byte de cada instrução executada).
O `fab re analyze` usa as entradas ($08) como sementes com o M/X observado.

## memType do Lua do MesenCE (harness)
`snesMemory` (barramento da CPU, relativo) · `snesDebug` (idem sem efeitos colaterais) ·
`snesWorkRam` (WRAM absoluta, cobre todos os espelhos) · `snesPrgRom` (offset na ROM) ·
`snesSaveRam` · `snesVideoRam` · `snesSpriteRam` · `snesCgRam`.
Savestates só podem ser criados/carregados dentro de callback de execução da CPU principal (o harness cuida).
