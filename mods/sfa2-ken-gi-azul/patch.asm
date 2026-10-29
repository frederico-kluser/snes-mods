; ════════════════════════════════════════════════════════════════════════════
;  Ken de gi azul — Street Fighter Alpha 2 (USA)
;  Patch só de DADOS (paletas BGR555): nenhum código muda → sem hijack e sem M/X.
;  S-DD1: os 2 primeiros MiB ficam em LoROM fixa ($80-$BF:8000-FFFF) = o `lorom` do Asar.
; ════════════════════════════════════════════════════════════════════════════
lorom

; ── tons novos do gi (troque aqui para outra cor; formato 0bbbbbgggggrrrrr) ──
!gi_0 = $7E06   ; r6  g16 b31 — era $011E (realce)
!gi_1 = $7102   ; r2  g8  b28 — era $001B
!gi_2 = $60A1   ; r1  g5  b24 — era $0017
!gi_3 = $5060   ; r0  g3  b20 — era $0013
!gi_4 = $4440   ; r0  g2  b17 — era $0011 (sombra mais escura)

; Lutador Ken, cor 0: $DF:0260 (tabela $BF:B6C8, id 1) = PC 0x1F0260 = $BE:8260; gi = cores 9-13
; evidência: ev-dbaa2b8b4bf8 (lida em C0:3982 no início do round) + dump de CGRAM (pal 14)
; valores originais conferidos byte a byte na base limpa: $011E $001B $0017 $0013 $0011
org $BE8272
    dw !gi_0, !gi_1, !gi_2, !gi_3, !gi_4

; Retrato do Ken, cor 0 (seleção: BG pal 6; tela VS: sprite pal 0): PC 0x1F4E60 = $BE:CE60; gi = cores 5-8
; valores originais conferidos byte a byte na base limpa: $113E $0C7B $0855 $000F
; ⚠ a cor 8 ($000F) também pinta os olhos do retrato — opção A ($3C20) neste ciclo; rever no compare
org $BECE6A
    dw $7E06, $7102, $5881, $3C20
