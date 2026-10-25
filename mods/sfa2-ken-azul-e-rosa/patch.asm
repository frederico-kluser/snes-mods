; ════════════════════════════════════════════════════════════════════════════
;  Ken de gi azul, rosa (Dan) e preta (Akuma) + LUVAS PRETAS na roupa preta
;  Street Fighter Alpha 2 (USA) — S-DD1, LoROM
;
;  Duas partes:
;   1. DADOS: tons do gi das cores 0/1/2 (lutador) e dos retratos (seleção e VS).
;   2. CÓDIGO: "espelho de paleta" para as luvas ficarem PRETAS só na roupa preta
;      (cor 2), com sombreado preservado (2 tons), sem tocar no cabelo.
;
;  Mecânica do espelho (toda a evidência está no README e nas notas do jogo):
;   · CGRAM: Ken usa a paleta 14 (cores 224-239) = buffer WRAM $06C0-$06DF,
;     copiado para a CGRAM por DMA a cada VBlank (C0:0308-0320, CGADD=0).
;   · O atributo do sprite é (flags_do_cel & $C2) ^ $0B; os bits 2-5 das flags
;     NÃO são usados pelo motor (C0:5CA7), logo servem de MARCA.
;   · A paleta de sprite p do OAM cai na CGRAM p+8 (medido: Ken OAM 6 → CGRAM 14,
;     Rose OAM 7 → CGRAM 15). Logo sprite pal 3 → CGRAM 11 (cores 176-191),
;     que o jogo deixa ZERADA durante a luta → é a nossa paleta espelho.
;   · Espelho = cópia fiel da pal 14 com os tons 14/15 (cabelo E luva) trocados
;     pela rampa preta de 2 tons; os cels marcados usam o espelho, e como só os
;     tons 14/15 diferem, pele/manga/contorno ficam idênticos por construção.
; ════════════════════════════════════════════════════════════════════════════
lorom

; ── tons novos do gi (formato 0bbbbbgggggrrrrr) ─────────────────────────────
; cor 0 — azul royal
!azul_0 = $7E06   ; r6  g16 b31 — era $011E (realce)
!azul_1 = $7102   ; r2  g8  b28 — era $001B
!azul_2 = $60A1   ; r1  g5  b24 — era $0017
!azul_3 = $5060   ; r0  g3  b20 — era $0013
!azul_4 = $4440   ; r0  g2  b17 — era $0011 (sombra)

; cor 1 — rosa do Dan: CÓPIA FIEL dos tons do gi do Dan (id 12, $DF:1E40 = PC 0x1F1E40)
!rosa_0 = $6ADC   ; r6  g22 b27 — era $5910 (realce)
!rosa_1 = $521E   ; r30 g16 b20 — era $488C
!rosa_2 = $419C   ; r28 g12 b16 — era $404A
!rosa_3 = $311A   ; r26 g8  b12 — era $3828
!rosa_4 = $2098   ; r24 g4  b10 — era $3006 (sombra)

; cor 2 — preta do Akuma: CÓPIA FIEL dos tons do gi do Akuma (id 2, $DF:0460 = PC 0x1F0460)
!preta_0 = $2908   ; r0 g2  b2  (realce) — era $7BDE
!preta_1 = $18C6   ; r0 g1  b1  — era $7B58
!preta_2 = $14A5   ; r1 g1  b1  — era $7AD4
!preta_3 = $1084   ; r0 g1  b1  — era $6A50
!preta_4 = $1084   ; r0 g1  b1  (sombra) — era $518C

; ── rampa das LUVAS pretas (2 tons: SOMBREADO preservado, nunca tom único) ──
; realce = o mesmo melhor tom do gi preto (a luva pega a mesma luz do tecido);
; sombra = o tom escuro da rampa do gi. Nenhum dos dois é $0842 (o CONTORNO),
; senão a luva se funde com a linha de contorno e achata.
; evidência: simulação work/sim-luvas-2.png (10x) + games/sfa2/prints/34-…png
!luva_realce = $2908   ; (66,66,82) — realce
!luva_sombra = $1084   ; (33,33,33) — sombra
!cor_p1      = $7E07C8 ; cor do uniforme do P1 (0 soco, 1 chute, 2 = roupa preta)

; ── Lutador Ken (tabela $BF:B6C8, id 1): cor n em 0x1F0260 + n*32; gi = cores 9-13 ─
; evidência: ev-dbaa2b8b4bf8 (lida em C0:3982 no início do round) + dump de CGRAM (pal 14)
; cor 0 (era $011E $001B $0017 $0013 $0011):
org $BE8272
    dw !azul_0, !azul_1, !azul_2, !azul_3, !azul_4

; cor 1 (era $5910 $488C $404A $3828 $3006 — gi roxo, escolhido com chute):
org $BE8292
    dw !rosa_0, !rosa_1, !rosa_2, !rosa_3, !rosa_4

; cor 2 (era $7BDE $7B58 $7AD4 $6A50 $518C — gi branco, 2+ socos):
org $BE82B2
    dw !preta_0, !preta_1, !preta_2, !preta_3, !preta_4

; ── Retratos do Ken (PC 0x1F4E60 + n*32; gi = cores 5-8) ─────────────────────
; cor 0 (era $113E $0C7B $0855 $000F; a cor 8 também pinta os olhos → opção A $3C20):
org $BECE6A
    dw $7E06, $7102, $5881, $3C20

; cor 1 (era $6952 $50CE $404A $3006): rosa do Dan, rampa sem o realce mais claro
; (o retrato do Dan usa outros significados nos índices 6-8 — simulação em work/sim-retrato-rosa.png):
org $BECE8A
    dw $521E, $419C, $311A, $2098

; cor 2 (era $7B58 $7292 $5DEE $494A): preta do Akuma, rampa COM o realce (o tecido mantém o caimento;
; o retrato do Akuma usa índices próprios — simulação em work/sim-retrato-preta.png):
org $BECEAA
    dw $2908, $18C6, $14A5, $1084

; ════════════════════════════════════════════════════════════════════════════
;  HIJACK 1 — espelho de paleta, antes do DMA da CGRAM
;  C0:0312 = LDY #$0500 / STY $4302 (6 bytes, LDY+STY inteiros) → JML + 2 NOP
;  M/X no ponto: m8,x16 (ev-…: sonda de escrita em C0:030D devolveu m8,x16)
; ════════════════════════════════════════════════════════════════════════════
org $008312                      ; = C0:0312 (janela S-DD1 → PC 0x0312)
    autoclean jml EspelhoPaleta
    nop
    nop

; ════════════════════════════════════════════════════════════════════════════
;  HIJACK 2 — atributo do sprite: manda o CEL MARCADO para a paleta espelho
;  C0:5CA9 = EOR $0B / STA $0015C3,X (2 + 4 bytes) → JML + 2 NOP
;  M/X no ponto: m8,x16 (sonda exec em C0:5CAB)
; ════════════════════════════════════════════════════════════════════════════
org $00DCA9                      ; = C0:5CA9 (PC 0x5CA9; LoROM $00:DCA9)
    autoclean jml AtributoCel
    nop
    nop

; ════════════════════════════════════════════════════════════════════════════
;  HIJACK 3 — fim da RECARGA da paleta (C0:3A60-3A9D): o jogo reescreve $06C0-$06DF
;  em plena luta; sem este hook o espelho ficaria 1 frame atrasado (luva pisca na cor
;  antiga). C0:3A9A = INC $A2 / PLX / RTL (4 bytes, 3 instruções) → JML 4 bytes.
;  M/X no ponto: m8,x16 (sonda exec em C0:3A8F, o laço da recarga)
; ════════════════════════════════════════════════════════════════════════════
org $00BA9A                      ; = C0:3A9A (PC 0x3A9A; LoROM $00:BA9A)
    autoclean jml RecargaPaleta

; ════════════════════════════════════════════════════════════════════════════
freecode

; ── espelho: $06C0-$06DF (pal 14) → $0660-$067F (pal 11 = sprite pal 3) ────
; Sempre copia; só na roupa preta (cor 2) os tons 14/15 viram a rampa da luva.
; ATENÇÃO ao tamanho dos imediatos: no ponto do hijack M = 8 bits e X = 16 bits, por isso
; todo imediato de 8 bits leva sufixo `.b` (sem ele o Asar monta 16 bits e o '00' sobrando
; vira BRK). Este erro custou uma rodada de depuração: o espelho ficava copiado pela metade.
CopiaEspelho:
    ldx #$001F                   ; 32 bytes: $06C0-$06DF (X = 16 bits aqui)
.copia
    lda.l $7E06C0,x
    sta.l $7E0660,x
    dex
    bpl .copia

    lda.l $7E07C8                ; cor do uniforme do P1
    cmp.b #$02                   ; roupa preta?
    bne .fim

    lda.b #!luva_realce&$FF      ; tom 14 do espelho = realce da luva
    sta.l $7E067C
    lda.b #!luva_realce>>8
    sta.l $7E067D
    lda.b #!luva_sombra&$FF      ; tom 15 do espelho = sombra da luva
    sta.l $7E067E
    lda.b #!luva_sombra>>8
    sta.l $7E067F
.fim
    rts

EspelhoPaleta:
    jsr CopiaEspelho
    ldy #$0500                   ; instruções originais do hijack
    sty $4302
    jml $C00318

RecargaPaleta:
    jsr CopiaEspelho
    inc $A2                      ; instruções originais do hijack
    plx
    rtl

; ── atributo do cel: (flags & $C2) ^ $0B, e a LUVA → paleta 6 vira paleta 3 ──
; A luva é reconhecida pelo TILE final do sprite (o motor já o gravou em $0015C2,X antes
; deste ponto). GloveTable diz quais tiles são luva, levantada por "grelha rotulada +
; partição" (README → Como os tiles das luvas foram achados): em cada frame pinta-se o
; ouro, separa-se o blob do cabelo do dos punhos e ficam como luva os tiles cuja caixa
; 16x16 toca um punho SEM tocar o cabelo (seguros por construção) nos 194 frames medidos.
AtributoCel:
    lda $0004,y                  ; flags do cel (DBR = banco dos cels)
    and.b #$C2
    eor $0B
    pha
    and.b #$0E
    cmp.b #$0C                   ; é a paleta 6 (o P1)? P2 (pal 7) fica intacto
    bne .normal
    lda.l $0015C2,x              ; tile final do sprite (já gravado pelo motor)
    cmp.b #$40                   ; acima da tabela? não é luva
    bcs .normal
    phx
    tax                          ; M=8: TAX limpa o byte alto de X
    lda.l GloveTable,x
    plx
    and.b #$01
    beq .normal
.luva
    pla
    eor.b #$0A                   ; paleta 6 → 3 (CGRAM 11 = espelho)
    sta.l $0015C3,x
    jml $C05CAF

.normal
    pla
    sta.l $0015C3,x
    jml $C05CAF

; 1 = o tile desenha luva (nos 194 frames analisados nunca encosta no cabelo)
GloveTable:
    db $00,$00,$00,$00,$01,$00,$01,$00   ; $00-$07
    db $00,$00,$00,$00,$01,$01,$01,$01   ; $08-$0F
    db $00,$00,$00,$00,$00,$00,$00,$00   ; $10-$17
    db $01,$01,$00,$00,$01,$00,$01,$00   ; $18-$1F
    db $01,$00,$00,$00,$00,$00,$00,$00   ; $20-$27
    db $00,$00,$00,$00,$00,$00,$00,$00   ; $28-$2F
    db $00,$00,$00,$00,$00,$01,$01,$00   ; $30-$37
    db $00,$00,$00,$01,$00,$00,$00,$00   ; $38-$3F
