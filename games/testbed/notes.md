# SNESFAB TESTBED (`testbed`)

> Notas duráveis sobre este jogo. Cada fato leva a evidência (como foi verificado: sonda
> dinâmica, xref do Ghidra, teste no emulador). Nada de dumps de código comercial aqui.
> (O testbed é código próprio — `fixtures/testbed/testbed.asm` — e serve de exemplo do formato.)

## Identificação
- Mapa: lorom · ROM: 1024 KiB · região: $01 (América do Norte)
- SHA-256 (base limpa): `5e7ba251cc1693579094978f3f69e23cf66b9bf7a299c06c70d57c6e1169a08a`
- Cabeçalho SMC no original: não

## Mapa de RAM (verificado)
| endereço | tam. | significado | evidência |
|---|---|---|---|
| 7E:0015 / 7E:0016 | 1 / 1 | botões mantidos / novos neste frame (B Y Sel St U D L R) | código-fonte; `fab re func` em 80:81E8 |
| 7E:0072 | 1 | 0 = no chão, 1 = no ar | `fab ram query` (muda 1× no pulo) |
| 7E:007D | 1 (s) | velocidade Y em 1/16 px/frame (negativo = sobe) | `ev-6647b8abb9ce` (3 escritores) |
| 7E:0094 | 2 | X do jogador (px) | cenário `pulo-simples` (+2/frame com →) |
| 7E:0096 | 2 | Y do jogador (12.4 fixo; chão = $0C00 = 192 px) | `fab ram query`, traço do ciclo |
| 7E:1DF9 | 1 | livre no original (usado pelo mod de pulo duplo) | `ev-56a36448f853`, `ev-cdf39fc03d1a`, `ev-7146a5cb849b` |
| 7E:1DFA | 1 | pedido de som de pulo (só escrito) | `fab ram query` |

## Rotinas
| endereço | o que faz | M/X à entrada | evidência |
|---|---|---|---|
| 80:8000 | reset + loop principal (WAI → leitura do controle → pulo → movimento → física → OAM) | E=1 | vetor de reset |
| 80:A41E | verificação de pulo (SEP #$20; LDA $72; BNE; LDA $16; AND #$80; BEQ; LDA #$B0; STA $7D …) | m8,x16 | `ev-3ef14abf2597`, `ev-8fa6f3731b33` |
| 80:8241 | física: gravidade +3, teto de queda $40, integra Y, aterrissa | m8,x16 | `fab re funcs` + sonda de escrita em $7D |
| 80:82D1 | NMI: DMA da OAM | m8,x16 (CDL) | CDL |

## Savestates (`games/testbed/states/`)
| nome | o que mostra | criado como |
|---|---|---|
| parado | jogador parado no chão, x=64 | `fab state boot` (power-on + 30 frames) — `fab testbed` recria |

## Hijacks usados por mods
| endereço | bytes originais | mod | notas |
|---|---|---|---|
| 80:A420 | `A5 72 D0 14` (LDA $72 : BNE $A438) | testbed-double-jump | JML para freecode; retornos em 80:A424 e 80:A438 |

## Perguntas em aberto
- (nenhuma)
