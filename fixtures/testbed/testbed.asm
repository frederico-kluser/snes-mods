; ════════════════════════════════════════════════════════════════════════════
;  SNESFAB TESTBED — "jogo" homebrew mínimo para validar a fábrica de mods.
;  Código original deste repositório (sem material comercial). LoROM, 1 MB.
;
;  Um bloco vermelho 16x16 anda (←/→) e pula (B) sobre um chão verde; régua de
;  altura à esquerda (marca a cada 16 px, marca dupla a cada 32 px).
;  A rotina de pulo fica exatamente onde o guia REA/Asar a descreve:
;     $80:A41E  SEP #$20 / $80:A420 LDA $72 / BNE $A438 / LDA $16 / AND #$80 ...
;  para que mods/testbed-double-jump (o patch do guia) funcione sem adaptações.
;
;  Mapa de RAM (direct page, D=$0000 → $7E:00xx):
;    $10 contador de frames   $11 contador de NMIs
;    $15 botões mantidos  (B Y Sel St U D L R)    $16 botões novos neste frame
;    $17 botões mantidos  (A X L R 0 0 0 0)       $18 botões novos neste frame
;    $72 no ar (0 = chão, 1 = ar)                 $7D velocidade Y (s8, 1/16 px/frame)
;    $94-$95 X do jogador (px)                    $96-$97 Y do jogador (12.4 fixo)
;    $1DFA pedido de som de pulo (escrito, nunca lido)      $1DF9 livre
;    $0200-$041F sombra da OAM (DMA no NMI)
;  Montar:  fab testbed build      (ou: asar --fix-checksum=on testbed.asm out.sfc)
; ════════════════════════════════════════════════════════════════════════════

lorom

!GroundFixed = $0C00        ; Y = 192 px em 12.4
!Gravity     = $03
!MaxFall     = $40
!JumpSpeed   = $B0          ; -80 → -5 px/frame

; ── DMA de CPU → VRAM (canal 0, modo 1: $2118/$2119) ───────────────────────
macro vram_dma(src, dest, size)
    rep #$20
    lda.w #<dest>
    sta $2116
    lda.w #<src>&$FFFF
    sta $4302
    lda.w #<size>
    sta $4305
    sep #$20
    lda.b #<src>>>16
    sta $4304
    lda.b #$80
    sta $2115
    lda.b #$01
    sta $4300
    lda.b #$18
    sta $4301
    lda.b #$01
    sta $420B
endmacro

org $808000
Reset:
    sei
    clc
    xce                     ; modo nativo
    jml .bank80             ; o vetor aponta para o espelho $00:8000; passa para $80
.bank80:
    rep #$30
    ldx.w #$1FFF
    txs
    phk
    plb                     ; DB = $80 (I/O e WRAM baixa acessíveis)
    lda.w #$0000
    tcd                     ; D = $0000
    sep #$20

    lda.b #$8F
    sta $2100               ; forced blank
    stz $4200               ; sem NMI/IRQ/auto-joypad durante o init

    ; registradores da PPU $2101-$2133 zerados
    ldx.w #$0000
-   stz $2101,x
    inx
    cpx.w #$0033
    bne -
    lda.b #$E0
    sta $2132               ; COLDATA limpo
    lda.b #$FF
    sta $4201
    ldx.w #$0000
-   stz $4202,x
    inx
    cpx.w #$000C
    bne -

    ; WRAM $0000-$1EFF zerada (a pilha vive em $1F00-$1FFF)
    rep #$20
    ldx.w #$0000
-   stz $0000,x
    inx
    inx
    cpx.w #$1F00
    bne -
    ; sombra da OAM: tudo fora do tela (Y=$F0)
    lda.w #$F0F0
    ldx.w #$0000
-   sta $0200,x
    inx
    inx
    cpx.w #$0200
    bne -
    sep #$20

    ; VRAM inteira zerada (DMA de fonte fixa, 64 KiB)
    rep #$20
    lda.w #$0000
    sta $2116
    lda.w #ZeroWord&$FFFF
    sta $4302
    lda.w #$0000
    sta $4305
    sep #$20
    lda.b #ZeroWord>>16
    sta $4304
    lda.b #$80
    sta $2115
    lda.b #$09
    sta $4300
    lda.b #$18
    sta $4301
    lda.b #$01
    sta $420B

    ; gráficos
    %vram_dma(ObjTilesTop, $0000, $0040)       ; tiles 0,1  (metade de cima do 16x16)
    %vram_dma(ObjTilesBottom, $0100, $0040)    ; tiles 16,17 (metade de baixo)
    %vram_dma(BgTiles, $1000, $0080)           ; BG1: 0 vazio, 1 relva, 2 marca, 3 terra

    ; paletas
    stz $2121
    ldx.w #$0000
-   lda.l BgPalette,x
    sta $2122
    inx
    cpx.w #$0008
    bne -
    lda.b #$80
    sta $2121
    ldx.w #$0000
-   lda.l ObjPalette,x
    sta $2122
    inx
    cpx.w #$0006
    bne -

    ; tilemap BG1 em $2000 (32x32): chão nas linhas 26-27, régua na coluna 0-1
    lda.b #$80
    sta $2115
    rep #$20
    lda.w #$2000+(26*32)
    sta $2116
    ldx.w #$0020
-   lda.w #$0001
    sta $2118
    dex
    bne -
    ldx.w #$0020
-   lda.w #$0003
    sta $2118
    dex
    bne -
    ldy.w #$0000
.ruler:
    tya
    asl
    asl
    asl
    asl
    asl
    clc
    adc.w #$2000
    sta $2116
    lda.w #$0002
    sta $2118
    tya
    and.w #$0003
    bne .rulerNext
    lda.w #$0002
    sta $2118
.rulerNext:
    iny
    iny
    cpy.w #$001A
    bcc .ruler
    sep #$20

    ; modo de vídeo
    lda.b #$01
    sta $2105               ; BGMODE 1
    stz $2101               ; OBSEL: 8x8/16x16, base $0000
    lda.b #$20
    sta $2107               ; BG1SC: tilemap $2000, 32x32
    lda.b #$01
    sta $210B               ; BG1 chr $1000
    lda.b #$11
    sta $212C               ; TM: BG1 + OBJ

    ; estado inicial do jogador
    rep #$20
    lda.w #$0040
    sta $94                 ; X = 64
    lda.w #!GroundFixed
    sta $96                 ; no chão
    sep #$20
    stz $7D
    stz $72
    jsr UpdateOam
    jsr OamDma

    lda.b #$0F
    sta $2100               ; tela ligado, brilho máximo
    lda.b #$81
    sta $4200               ; NMI + auto-joypad

MainLoop:
    wai
-   lda $4212
    and.b #$01
    bne -                   ; espera o fim da leitura automática do comando
    jsr ReadJoypad
    jsr JumpCheck           ; rotina em $80:A41E (ponto de hijack do guia)
    jsr MoveHorizontal
    jsr Physics
    jsr UpdateOam
    inc $10
    bra MainLoop

; ── leitura do comando: $15/$17 mantidos, $16/$18 novos neste frame ─────────
ReadJoypad:
    sep #$20
    lda $4219
    sta $00
    lda $15
    eor.b #$FF
    and $00
    sta $16
    lda $00
    sta $15
    lda $4218
    sta $00
    lda $17
    eor.b #$FF
    and $00
    sta $18
    lda $00
    sta $17
    rts

MoveHorizontal:
    sep #$20
    lda $15
    and.b #$01              ; Direita
    beq .noRight
    rep #$20
    lda $94
    clc
    adc.w #$0002
    cmp.w #$00F0
    bcc .storeRight
    lda.w #$00F0
.storeRight:
    sta $94
    sep #$20
.noRight:
    lda $15
    and.b #$02              ; Esquerda
    beq .noLeft
    rep #$20
    lda $94
    sec
    sbc.w #$0002
    bpl .storeLeft
    lda.w #$0000
.storeLeft:
    sta $94
    sep #$20
.noLeft:
    rts

; ── gravidade, integração em 12.4 e aterragem ───────────────────────────────
Physics:
    sep #$20
    lda $7D
    clc
    adc.b #!Gravity
    bmi .storeSpeed         ; ainda a subir
    cmp.b #!MaxFall
    bcc .storeSpeed
    lda.b #!MaxFall
.storeSpeed:
    sta $7D
    rep #$20
    lda $7D
    and.w #$00FF
    cmp.w #$0080
    bcc .positive
    ora.w #$FF00            ; extensão de sinal
.positive:
    clc
    adc $96
    sta $96
    cmp.w #!GroundFixed
    bcc .inAir
    lda.w #!GroundFixed
    sta $96
    sep #$20
    lda $7D
    bmi .inAir8
    stz $7D
    stz $72
    rts
.inAir:
    sep #$20
.inAir8:
    lda.b #$01
    sta $72
    rts

UpdateOam:
    sep #$20
    lda $94
    sta $0200               ; X (8 bits baixos)
    rep #$20
    lda $96
    lsr
    lsr
    lsr
    lsr
    sep #$20
    sta $0201               ; Y em píxeis
    stz $0202               ; tile 0
    lda.b #$30
    sta $0203               ; prioridade 3, paleta 0
    lda $95
    and.b #$01
    ora.b #$02              ; sprite grande (16x16) + bit 8 do X
    sta $0400
    rts

OamDma:
    sep #$20
    stz $2102
    stz $2103
    rep #$20
    lda.w #$0200
    sta $4302
    lda.w #$0220
    sta $4305
    sep #$20
    stz $4304
    stz $4300
    lda.b #$04
    sta $4301
    lda.b #$01
    sta $420B
    rts

NmiHandler:
    rep #$30
    pha
    phx
    phy
    sep #$20
    lda $4210               ; reconhece o NMI
    jsr OamDma
    inc $11
    rep #$30
    ply
    plx
    pla
    rti

EmptyHandler:
    rti

ZeroWord:
    dw $0000

; 4bpp: 8 linhas × (plano0, plano1) seguidas de 8 linhas × (plano2, plano3)
ObjTilesTop:
    db $FF,$00,$FF,$00,$F3,$0C,$F3,$0C,$FF,$00,$FF,$00,$FF,$00,$FF,$00   ; tile 0: olho
    db $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
    db $FF,$00,$FF,$00,$CF,$30,$CF,$30,$FF,$00,$FF,$00,$FF,$00,$FF,$00   ; tile 1: olho
    db $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
ObjTilesBottom:
    db $FF,$00,$FF,$00,$FF,$00,$FF,$00,$FF,$00,$FF,$00,$FF,$00,$FF,$00   ; tile 16
    db $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
    db $FF,$00,$FF,$00,$FF,$00,$FF,$00,$FF,$00,$FF,$00,$FF,$00,$FF,$00   ; tile 17
    db $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00

BgTiles:
    db $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00   ; 0: vazio
    db $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
    db $FF,$00,$FF,$00,$FF,$00,$FF,$00,$FF,$00,$FF,$00,$FF,$00,$FF,$00   ; 1: relva (cor 1)
    db $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
    db $00,$FF,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00   ; 2: marca (cor 2, linha 0)
    db $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
    db $FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF   ; 3: terra (cor 3)
    db $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00

BgPalette:
    dw $7E8C, $1304, $7FFF, $1150      ; céu, relva, branco, terra
ObjPalette:
    dw $0000, $109F, $7FFF             ; (transparente), vermelho, branco

; ── rotina de pulo nos endereços do guia ────────────────────────────────────
org $80A41E
JumpCheck:
    sep #$20                ; $80:A41E  E2 20
    lda $72                 ; $80:A420  A5 72   no ar?
    bne .exit               ; $80:A422  D0 14
    lda $16                 ; $80:A424  A5 16   botões novos
    and.b #$80              ; $80:A426  29 80   B
    beq .exit               ; $80:A428  F0 0E
    lda.b #!JumpSpeed       ; $80:A42A  A9 B0
    sta $7D                 ; $80:A42C  85 7D
    lda.b #$01
    sta $72
    lda.b #$01
    sta $1DFA               ; pedido de som de pulo
    nop
.exit:
    rts                     ; $80:A438

; ── cabeçalho interno e vetores ─────────────────────────────────────────────
org $80FFC0
    db "SNESFAB TESTBED      "  ; 21 bytes
    db $20                  ; LoROM, SlowROM
    db $00                  ; só ROM
    db $0A                  ; 1 MB
    db $00                  ; sem SRAM
    db $01                  ; América do Norte
    db $00                  ; licenciado
    db $00                  ; versão 1.0
    dw $FFFF, $0000         ; complemento e checksum (o Asar corrige)

org $80FFE0
    dw $0000, $0000
    dw EmptyHandler&$FFFF   ; COP nativo
    dw EmptyHandler&$FFFF   ; BRK nativo
    dw EmptyHandler&$FFFF   ; ABORT nativo
    dw NmiHandler&$FFFF     ; NMI nativo
    dw $0000
    dw EmptyHandler&$FFFF   ; IRQ nativo
    dw $0000, $0000
    dw EmptyHandler&$FFFF   ; COP (emulação)
    dw $0000
    dw EmptyHandler&$FFFF   ; ABORT (emulação)
    dw EmptyHandler&$FFFF   ; NMI (emulação)
    dw Reset&$FFFF          ; RESET
    dw EmptyHandler&$FFFF   ; IRQ/BRK (emulação)

; ── expande para 1 MB (bancos $10-$1F livres para freecode) ─────────────────
org $9FFFFF
    db $00
