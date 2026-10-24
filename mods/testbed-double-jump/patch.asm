; Arquivo: mods/testbed-double-jump/patch.asm
; Alvo: ROM LoROM de Super Nintendo (WDC 65816) — o testbed homebrew do repositório
; É o patch de "Salto Duplo" do guia REA/Asar, literalmente, rodando sobre a rotina de pulo
; que o testbed coloca nos mesmos endereços ($80:A41E-$80:A438).
lorom

; Definições com evidência (ver mods/testbed-double-jump/README.md → Evidências)
!AirStateFlag     = $72       ; Direct Page ($7E:0072): 0 = no chão, != 0 = no ar
!JoypadPressed    = $16       ; Direct Page ($7E:0016): botões pressionados neste frame
!PlayerYVelocity  = $7D       ; Direct Page ($7E:007D): velocidade vertical (negativo = subir)
!DoubleJumpUsed   = $7E1DF9   ; WRAM livre (0 = disponível, 1 = usado) — ninguém lê/escreve: sonda + xrefs

; Ponto de hijack: $80:A420 (substitui 'LDA $72 : BNE $A438' → exatamente 4 bytes)
; Estado à entrada (evidência dinâmica e estática): M = 8 bits, X = 16 bits
org $80A420
    autoclean jml DoubleJumpCheck

; Pontos de retorno na rotina original (fronteiras de instrução verificadas)
org $80A424
ContinueGroundJump:

org $80A438
ExitJumpRoutine:

; Espaço livre em bancos com espelho de RAM ($10-$3F), protegido por RATS
freecode

DoubleJumpCheck:
    ; Estado garantido à entrada (auditado em $80:A41E): M = 1 (acumulador de 8 bits)
    lda !AirStateFlag
    bne .InAir                ; no ar → verifica se ainda há salto duplo

    ; No chão: reinicia o salto duplo e segue o fluxo normal
    lda #$00
    sta.l !DoubleJumpUsed
    jml ContinueGroundJump    ; volta a $80:A424 (teste normal do botão de salto)

.InAir:
    lda.l !DoubleJumpUsed
    bne .AbortJump            ; já usou o salto duplo

    lda !JoypadPressed
    and #$80                  ; B pressionado neste frame?
    beq .AbortJump

    ; Salto duplo!
    lda #$01
    sta.l !DoubleJumpUsed
    lda #$B8                  ; impulso um pouco mais curto (-72)
    sta !PlayerYVelocity

.AbortJump:
    jml ExitJumpRoutine       ; volta a $80:A438 (fim da verificação de salto)
