; ════════════════════════════════════════════════════════════════════════════
;  Ken de gi azul e rosa (Dan) — Street Fighter Alpha 2 (USA)
;  Patch só de DADOS (paletas BGR555): nenhum código muda → sem hijack e sem M/X.
;  cor 0 (soco) = azul royal · cor 1 (chute) = rosa do Dan · cor 2 (2+ socos) = preta do Akuma
;  cores 3-5 intactas.
; ════════════════════════════════════════════════════════════════════════════
lorom

; ── tons novos (formato 0bbbbbgggggrrrrr) ────────────────────────────────────
; cor 0 — azul royal (continua do mod sfa2-ken-gi-azul)
!azul_0 = $7E06   ; r6  g16 b31 — era $011E (realce)
!azul_1 = $7102   ; r2  g8  b28 — era $001B
!azul_2 = $60A1   ; r1  g5  b24 — era $0017
!azul_3 = $5060   ; r0  g3  b20 — era $0013
!azul_4 = $4440   ; r0  g2  b17 — era $0011 (sombra)

; cor 1 — rosa do Dan: CÓPIA FIEL dos tons do gi do Dan (id 12, $DF:1E40 = PC 0x1F1E40)
; Dan = id 12 confirmado na grade de seleção (nome "DAN" + $7E:07A2 = 12; varredura 2026-10-25)
!rosa_0 = $6ADC   ; r6  g22 b27 — era $5910 (realce)
!rosa_1 = $521E   ; r30 g16 b20 — era $488C
!rosa_2 = $419C   ; r28 g12 b16 — era $404A
!rosa_3 = $311A   ; r26 g8  b12 — era $3828
!rosa_4 = $2098   ; r24 g4  b10 — era $3006 (sombra)

; cor 2 — preta do Akuma: CÓPIA FIEL dos tons do gi do Akuma (id 2, $DF:0460 = PC 0x1F0460)
; Akuma = id 2 confirmado na grade (nome "AKUMA" + $7E:07A2 = 2)
!preta_0 = $2908   ; r0 g2  b2  (realce) — era $7BDE
!preta_1 = $18C6   ; r0 g1  b1  — era $7B58
!preta_2 = $14A5   ; r1 g1  b1  — era $7AD4
!preta_3 = $1084   ; r0 g1  b1  — era $6A50
!preta_4 = $1084   ; r0 g1  b1  (sombra) — era $518C

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
