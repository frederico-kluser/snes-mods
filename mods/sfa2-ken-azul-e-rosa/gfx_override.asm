; GERADO por `fab gfx override` — NÃO edite à mão (refaça o comando).
; dump runs/20261028-130232-gfx-luvas: luvas-pretas: rótulos por conteúdo de games/sfa2/parts/ken-ouro.json (census runs/20261025-181031-census-sfa2-luva, 300 f, cobertura 99,7%; alvo = paleta OAM 6 = Ken); mapa 14:1,15:13 = só os píxeis de LUVA: índice 1 ($0842) = corpo preto igual nas 6 cores, índice 13 = vinco no tom mais escuro da roupa (cor 2 = $1084) — decidido pela simulação work/sim-mapa-luvas.png; cabelo não é rotulado = intoc
; override de gráfico sem codec: 30 bloco(s) editado(s) servido(s) cru(s); hook em 1 disparo(s) de DMA para a VRAM; tabela e cópias no blob gfx_override.bin a partir de PC 0x400000
lorom

; disparo 1: DMA para a VRAM antes de C0:048C (m8,x8); hijack de 5 B:
;   C0:0487  A4 00        LDY $00                ; m8,x8
;   C0:0489  8D 0B 42     STA $420B              ; m8,x8
org $808487
    autoclean jml GfxOvr1
    nop

freecode
prot GfxOvrConfere, GfxOvrDevolve
GfxOvr1:
    db $A4,$00
    ; ↑ instruções originais antes do disparo (copiadas, sem desvios)
GfxOvr1Corpo:
    php
    sei                      ; sem IRQ com a janela do chip trocada
    rep #$30
    pha
    phx
    phy
    phb
    sep #$20
    lda.b #$00
    pha                      ; 0 = nenhum canal trocado
    lda.b #$04
    sta.l $004807          ; janela → página da tabela e das cópias
    lda $07,s              ; canais que o STA $420B vai disparar
    ldy.w #$0000             ; Y = 16 × canal
.canal
    lsr
    bcc .prox
    pha
    jsl GfxOvrConfere            ; C = 1: trocou a fonte deste canal
    bcc .igual
    lda.b #$01
    sta $02,s
.igual
    pla
.prox
    pha
    rep #$21
    tya
    adc.w #$0010
    tay
    sep #$20
    pla
    bne .canal
    pla
    bne .trocou
    lda.b #$03
    sta.l $004807          ; nada trocado: janela de volta antes do DMA
.trocou
    plb
    rep #$30
    ply
    plx
    pla
    plp
    php
    sei
    db $8D,$0B,$42
    ; ↑ o STA $420B original: o DMA acontece aqui
GfxOvr1Volta:
    php
    rep #$30
    pha
    phx
    phy
    phb
    sep #$20
    lda.b #$04
    sta.l $004807          ; janela → página da tabela e das cópias
    lda $06,s              ; os mesmos canais
    ldy.w #$0000             ; Y = 16 × canal
.canald
    lsr
    bcc .proxd
    pha
    jsl GfxOvrDevolve            ; canal que leu uma cópia: DMAP e fonte do jogo de volta
    pla
.proxd
    pha
    rep #$21
    tya
    adc.w #$0010
    tay
    sep #$20
    pla
    bne .canald
    lda.b #$03
    sta.l $004807          ; janela de volta (valor do reset do chip)
    plb
    rep #$30
    ply
    plx
    pla
    plp
    plp
    jml $C0048C


freecode
GfxOvrConfere:           ; JSL — canal em Y (16·n, x16), m8. Preserva X/Y/B; C = 1 se trocou a fonte
    phb
    phx
    pea.w $0000
    plb
    plb                      ; DBR = $00: registradores de DMA
    lda $4301,y
    cmp.b #$18               ; destino $2118 (VRAM, palavra)
    bne .nao
    ldx.w #$0000             ; X = entrada da tabela
.entrada
    sep #$20
    lda.l $F00008,x       ; banco da fonte
    cmp $4304,y
    bne .proxima
    rep #$20
    lda.l $F00009,x       ; endereço da fonte
    cmp $4302,y
    bne .proxima
    lda.l $F0000B,x       ; tamanho
    cmp $4305,y
    beq .achou
.proxima
    rep #$21                 ; m16, C = 0
    txa
    adc.w #$0018
    tax
    cpx.w #$02D0
    bne .entrada
.nao
    clc
.sai
    sep #$20
    plx
    plb
    rtl
.achou
    sep #$20
.troca
    rep #$20
    lda.l $F0000D,x       ; fonte → cópia editada
    sta $4302,y
    sep #$20
    lda.l $F0000F,x
    sta $4304,y
    lda.l $F00010,x
    lsr                      ; bit 0: fonte de endereço fixo (chip)
    bcc .anda
    lda $4300,y
    and.b #$E7               ; endereço que ANDA: a cópia é crua, em ordem
    sta $4300,y
.anda
    lda.l $F00010,x
    and.b #$02               ; bit 1: desarma o chip neste DMA
    beq .feito
    lda.b #$00
    sta.l $004801          ; --chip-disarm
.feito
    sec
    brl .sai


freecode
GfxOvrDevolve:           ; JSL — canal em Y (16·n, x16), m8. Preserva X/Y/B
    phb
    phx
    pea.w $0000
    plb
    plb
    ldx.w #$0000
.entrada
    sep #$20
    lda.l $F0000F,x       ; banco da cópia
    cmp $4304,y
    bne .proxima
    rep #$21
    lda.l $F0000D,x       ; cópia + tamanho = onde o DMA parou
    adc.l $F0000B,x
    cmp $4302,y
    beq .achou
.proxima
    rep #$21
    txa
    adc.w #$0018
    tax
    cpx.w #$02D0
    bne .entrada
.sai
    sep #$20
    plx
    plb
    rtl
.achou
    rep #$20
    lda.l $F00009,x       ; fonte do jogo
    sta $4302,y
    sep #$20
    lda.l $F00008,x
    sta $4304,y
    lda.l $F00013,x      ; DMAP do jogo
    sta $4300,y
    and.b #$08
    bne .sai                 ; fonte fixa: o DMA não andou
    rep #$21
    lda.l $F00009,x
    adc.l $F0000B,x       ; endereço que anda: parou em fonte + tamanho
    sta $4302,y
    bra .sai

