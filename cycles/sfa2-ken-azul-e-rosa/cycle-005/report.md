# Ciclo 5 — Ken de gi azul, rosa (Dan) e preta (Akuma)

- quando: 2026-10-25T18:01:51-03:00 · nota: base A/B = variante LUVA_OFF (mesmo código, só a cor da luva volta ao ouro): resolve a dificuldade 9 (RNG descola contra a ROM limpa); checks reescritos: absolutos + iguais à variante + sincronia (x1/hp); corrigidos os que comparavam índices errados (esp1 vs gi1, esp14 vs 0x339E na cor 0)
- objetivo: As três primeiras roupas do Ken ganham novas cores: cor 0 (soco) continua de gi azul royal, cor 1 (chute) passa de roxa para rosa como o do Dan e cor 2 (2+ socos) passa de branca para preta como a do Akuma (tons copiados das paletas deles na ROM), no sprite da luta e nos retratos (seleção e tela VS); pele, cabelo, faixas, efeitos, as cores 3-5 do Ken e os outros personagens ficam iguais e a lógica da luta não muda.
- estado: **ok** · pontuação: **0.9796** (anterior: 0.4461) · veredito automático: **evoluiu**

## Build
- ROM: `build/sfa2-ken-azul-e-rosa/sfa2-ken-azul-e-rosa.sfc` · BPS: `build/sfa2-ken-azul-e-rosa/sfa2-ken-azul-e-rosa.bps` (1216 bytes)
- avisos do Asar: 0
- tamanho das instruções × M/X: 48 conferidas, 0 problema(s)

## Base A/B (variante do próprio mod)
- ROM da base: `build/sfa2-ken-azul-e-rosa/sfa2-ken-azul-e-rosa.off.sfc` · defines: `{'LUVA_OFF': '1'}`
- variante muda só valores? ✅ sim (8 bytes diferentes)
- por que: mod com código desloca o timing/RNG; contra a ROM limpa a cena descola e os checks alinhados não valem. A variante tem o MESMO código: só a cor muda.
- hijack 80:8312 (6 B, m8,x16, mod.json hijacks[] (m/x verificados)): OK 
  - original: A0 00 05     LDY #$0500             ; m8,x16 | 8C 02 43     STY $4302              ; m8,x16 | A0 00 02     LDY #$0200             ; m8,x16
  - patch:    5C 78 FF A7  JML $A7FF78            ; m8,x16 | EA           NOP                    ; m8,x16
- hijack 80:BA9A (4 B, m8,x16, mod.json hijacks[] (m/x verificados)): OK 
  - original: E6 A2        INC $A2                ; m8,x16 | FA           PLX                    ; m8,x16 | 6B           RTL                    ; m8,x16
  - patch:    5C 85 FF A7  JML $A7FF85            ; m8,x16 | 08           PHP                    ; m8,x16
- hijack 80:DCA9 (6 B, m8,x16, mod.json hijacks[] (m/x verificados)): OK 
  - original: 45 0B        EOR $0B                ; m8,x16 | 9F C3 15 00  STA $0015C3,X          ; m8,x16 | E8           INX                    ; m8,x16
  - patch:    5C 8C FF A7  JML $A7FF8C            ; m8,x16 | EA           NOP                    ; m8,x16
- freespace A7:FF31–A7:FFB4 (RATS 124 B, código em A7:FF39)
- dados BE:8272–BE:827B (10 B, declarado em 'data[]'): gi cor 0 do lutador (cores 9-13) — azul royal (ev-dbaa2b8b4bf8)
- dados BE:8292–BE:829B (10 B, declarado em 'data[]'): gi cor 1 do lutador (cores 9-13) — rosa do Dan, id 12, bloco 0x1F1E40 (nome DAN + 7E:07A2=12 na grade)
- dados BE:82B2–BE:82BB (10 B, declarado em 'data[]'): gi cor 2 do lutador (cores 9-13) — preta do Akuma, id 2, bloco 0x1F0460 (nome AKUMA + 7E:07A2=2 na grade)
- dados BE:CE6A–BE:CE71 (8 B, declarado em 'data[]'): retrato cor 0 (cores 5-8) — azul (dump de CGRAM na seleção/VS)
- dados BE:CE8A–BE:CE91 (8 B, declarado em 'data[]'): retrato cor 1 (cores 5-8) — rosa do Dan (rampa sem o realce; simulação de 3 rampas)
- dados BE:CEAA–BE:CEB1 (8 B, declarado em 'data[]'): retrato cor 2 (cores 5-8) — preta do Akuma (rampa do gi COM o realce; simulação)
- dados FC:49B1–FC:49B1 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:49B5–FC:49B5 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:49B9–FC:49B9 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:49BD–FC:49BD (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:49C1–FC:49C1 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:49CD–FC:49CD (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:49D1–FC:49D1 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:49D5–FC:49D5 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:49D9–FC:49D9 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:49DD–FC:49DD (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:49E1–FC:49E1 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:49FA–FC:49FA (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A06–FC:4A06 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A0A–FC:4A0A (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A0E–FC:4A0E (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A12–FC:4A12 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A16–FC:4A16 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A1A–FC:4A1A (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A1E–FC:4A1E (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A22–FC:4A22 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A2A–FC:4A2A (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A57–FC:4A57 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A5B–FC:4A5B (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A5F–FC:4A5F (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A63–FC:4A63 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A67–FC:4A67 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A6B–FC:4A6B (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A73–FC:4A73 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A94–FC:4A94 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A98–FC:4A98 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4A9C–FC:4A9C (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4AA0–FC:4AA0 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4AA4–FC:4AA4 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4AA8–FC:4AA8 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4AAC–FC:4AAC (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4AB0–FC:4AB0 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4AB4–FC:4AB4 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4AB8–FC:4AB8 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4AC9–FC:4AC9 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4ACD–FC:4ACD (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4AD1–FC:4AD1 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4ADD–FC:4ADD (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4AE1–FC:4AE1 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4AE5–FC:4AE5 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4AE9–FC:4AE9 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4AED–FC:4AED (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4AFD–FC:4AFD (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4B01–FC:4B01 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4B05–FC:4B05 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4B09–FC:4B09 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4B0D–FC:4B0D (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4B3A–FC:4B3A (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4B3E–FC:4B3E (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4B46–FC:4B46 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4B6F–FC:4B6F (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4B7F–FC:4B7F (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4B83–FC:4B83 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4B87–FC:4B87 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4B8B–FC:4B8B (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4BAC–FC:4BAC (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4BBC–FC:4BBC (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4BC0–FC:4BC0 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4BC4–FC:4BC4 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4BC8–FC:4BC8 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4BCC–FC:4BCC (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4BD0–FC:4BD0 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4BE5–FC:4BE5 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4BED–FC:4BED (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4BF1–FC:4BF1 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4BF5–FC:4BF5 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4BF9–FC:4BF9 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4BFD–FC:4BFD (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4C01–FC:4C01 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4C05–FC:4C05 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4C09–FC:4C09 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4C0D–FC:4C0D (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4C11–FC:4C11 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4C15–FC:4C15 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4C21–FC:4C21 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4C31–FC:4C31 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4C35–FC:4C35 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4C39–FC:4C39 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4C3D–FC:4C3D (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4C87–FC:4C87 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4C93–FC:4C93 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4C9B–FC:4C9B (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4C9F–FC:4C9F (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4CA3–FC:4CA3 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4CA7–FC:4CA7 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4CAB–FC:4CAB (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4CAF–FC:4CAF (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4CB3–FC:4CB3 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4CB7–FC:4CB7 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4CBF–FC:4CBF (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4CE4–FC:4CE4 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4CF0–FC:4CF0 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4CF4–FC:4CF4 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4CF8–FC:4CF8 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4CFC–FC:4CFC (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D00–FC:4D00 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D04–FC:4D04 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D0C–FC:4D0C (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D10–FC:4D10 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D14–FC:4D14 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D18–FC:4D18 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D1C–FC:4D1C (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D24–FC:4D24 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D41–FC:4D41 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D49–FC:4D49 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D4D–FC:4D4D (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D51–FC:4D51 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D55–FC:4D55 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D59–FC:4D59 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D5D–FC:4D5D (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D61–FC:4D61 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D65–FC:4D65 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D7D–FC:4D7D (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4D85–FC:4D85 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4DFB–FC:4DFB (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4DFF–FC:4DFF (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4E03–FC:4E03 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4E0B–FC:4E0B (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4E1B–FC:4E1B (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4E1F–FC:4E1F (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4E75–FC:4E75 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4E89–FC:4E89 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4E8D–FC:4E8D (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4E91–FC:4E91 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4E95–FC:4E95 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EA1–FC:4EA1 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EA5–FC:4EA5 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EA9–FC:4EA9 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EAD–FC:4EAD (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EB2–FC:4EB2 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EB6–FC:4EB6 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EBA–FC:4EBA (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EBE–FC:4EBE (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EC2–FC:4EC2 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EC6–FC:4EC6 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4ECA–FC:4ECA (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4ED2–FC:4ED2 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4ED6–FC:4ED6 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EDA–FC:4EDA (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EDE–FC:4EDE (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EE2–FC:4EE2 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EE6–FC:4EE6 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EEA–FC:4EEA (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EF2–FC:4EF2 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EF6–FC:4EF6 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4EFA–FC:4EFA (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:4F0A–FC:4F0A (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:516B–FC:516B (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:516F–FC:516F (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5173–FC:5173 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5177–FC:5177 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:517B–FC:517B (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:517F–FC:517F (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5183–FC:5183 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5187–FC:5187 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:518B–FC:518B (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:518F–FC:518F (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5193–FC:5193 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:51B3–FC:51B3 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:51B7–FC:51B7 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:51C4–FC:51C4 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:51C8–FC:51C8 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:51CC–FC:51CC (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:51D0–FC:51D0 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:51D8–FC:51D8 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:51E0–FC:51E0 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:51E8–FC:51E8 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5211–FC:5211 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5215–FC:5215 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5219–FC:5219 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:521D–FC:521D (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5221–FC:5221 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5239–FC:5239 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:523D–FC:523D (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5241–FC:5241 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5249–FC:5249 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:524D–FC:524D (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5251–FC:5251 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5255–FC:5255 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:578A–FC:578A (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:578E–FC:578E (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5792–FC:5792 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5796–FC:5796 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:579A–FC:579A (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:579E–FC:579E (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:57B2–FC:57B2 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:57B6–FC:57B6 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C18–FC:5C18 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C20–FC:5C20 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C28–FC:5C28 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C2C–FC:5C2C (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C38–FC:5C38 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C3C–FC:5C3C (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C40–FC:5C40 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C5D–FC:5C5D (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C65–FC:5C65 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C69–FC:5C69 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C6D–FC:5C6D (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C79–FC:5C79 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C7D–FC:5C7D (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C81–FC:5C81 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C96–FC:5C96 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C9A–FC:5C9A (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5C9E–FC:5C9E (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5CA2–FC:5CA2 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5CA6–FC:5CA6 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5CAA–FC:5CAA (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5CAE–FC:5CAE (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5CB2–FC:5CB2 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5CB6–FC:5CB6 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5CBA–FC:5CBA (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5CBE–FC:5CBE (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5CCE–FC:5CCE (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5CDA–FC:5CDA (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5CEA–FC:5CEA (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5CEE–FC:5CEE (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5CFA–FC:5CFA (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D0F–FC:5D0F (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D17–FC:5D17 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D1B–FC:5D1B (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D1F–FC:5D1F (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D23–FC:5D23 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D27–FC:5D27 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D43–FC:5D43 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D47–FC:5D47 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D4B–FC:5D4B (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D4F–FC:5D4F (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D5B–FC:5D5B (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D63–FC:5D63 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D77–FC:5D77 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D8C–FC:5D8C (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D90–FC:5D90 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D94–FC:5D94 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D98–FC:5D98 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5D9C–FC:5D9C (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DA0–FC:5DA0 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DA4–FC:5DA4 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DA8–FC:5DA8 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DAC–FC:5DAC (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DB0–FC:5DB0 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DB4–FC:5DB4 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DBC–FC:5DBC (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DCC–FC:5DCC (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DDC–FC:5DDC (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DE0–FC:5DE0 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DE5–FC:5DE5 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DE9–FC:5DE9 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DED–FC:5DED (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DF1–FC:5DF1 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DF5–FC:5DF5 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DF9–FC:5DF9 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5DFD–FC:5DFD (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5E01–FC:5E01 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5E05–FC:5E05 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5E11–FC:5E11 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5E15–FC:5E15 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5E1D–FC:5E1D (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5E25–FC:5E25 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:5E29–FC:5E29 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:675A–FC:675A (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:676E–FC:676E (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:6772–FC:6772 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:677A–FC:677A (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:677F–FC:677F (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:679F–FC:679F (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:67A3–FC:67A3 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:67A7–FC:67A7 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:67AB–FC:67AB (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:67C0–FC:67C0 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:67C4–FC:67C4 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:67C8–FC:67C8 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:67D0–FC:67D0 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:67D8–FC:67D8 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:67E0–FC:67E0 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:67E8–FC:67E8 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:67FC–FC:67FC (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:6800–FC:6800 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:6804–FC:6804 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:680C–FC:680C (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)
- dados FC:6814–FC:6814 (1 B, declarado em 'data[]'): MARCAS de luva por CEL nas flags (bits 2-5 livres): 217 cels em 28 listas de pose, derivadas de 530 frames com o ouro pintado + OAM + ponteiro de cels (um cel entra se a caixa toca um punho e nunca toca o cabelo)

## Cenário `luta-soco` — pontuação 1.0
- state: `games/sfa2/states/luta-ken-rose-fight.mss` · baseline: `runs/baselines/sfa2/luta-soco-b13ebe8b0aa52437` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-luta-soco`
- divergência visual: 0/140 frames (primeira fNone, pico 0.0% em f40)
- sincronia mod × variante (WRAM): ✅ em sincronia (só buffers mudam) — f40: 0 B, f320: 0 B, f599: 0 B
- M/X dinâmico no hijack 80:8312 (baseline): 300 execuções, {'m8,x16': 300}
- M/X dinâmico no hijack 80:BA9A (baseline): 27 execuções, {'m8,x16': 27}
- M/X dinâmico no hijack 80:DCA9 (baseline): 300 execuções, {'m8,x16': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `count((gi1 == 0x7E06) & (gi2 == 0x7102) & (gi3 == 0x60A1) & (gi4 == 0x5060) & (gi5 == 0x4440)) >= 0.8 * len(gi1)` | ✅ | 560 vs 448.0 | cor 0: gi azul royal (5 tons) na maior parte da luta |
| `all(esp14 == cabelo) and all(esp15 == cab15) and all(esp1 == contorno) and all(esp9 == gi1)` | ✅ | True | espelho (CGRAM 11) = cópia fiel da paleta do Ken (CGRAM 14) nesta cor: as luvas continuam loiras |
| `all(esp14 == baseline.esp14) and all(esp15 == baseline.esp15)` | ✅ | True | fora da cor 2 a regra da luva não age (igual à base) |
| `all(pele == baseline.pele) and all(contorno == baseline.contorno) and all(hadouken == baseline.hadouken) and all(rose == baseline.rose)` | ✅ | True | pele, contorno, Hadouken e Rose iguais à base variante |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ✅ | True | SINCRONIA: a luta joga igual à base variante (mesmo código → mesmo timing/RNG); contra a ROM limpa isto descolava no frame 1 |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-005/luta-soco/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-005/luta-soco/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-005/luta-soco/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-luta-soco/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-luta-soco/video.mp4`

## Cenário `luta-rosa` — pontuação 1.0
- state: `games/sfa2/states/luta-ken-chute-fight.mss` · baseline: `runs/baselines/sfa2/luta-rosa-dfd5da2cf5121980` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-luta-rosa`
- divergência visual: 0/140 frames (primeira fNone, pico 0.0% em f40)
- sincronia mod × variante (WRAM): ✅ em sincronia (só buffers mudam) — f40: 0 B, f320: 0 B, f599: 0 B
- M/X dinâmico no hijack 80:8312 (baseline): 300 execuções, {'m8,x16': 300}
- M/X dinâmico no hijack 80:BA9A (baseline): 27 execuções, {'m8,x16': 27}
- M/X dinâmico no hijack 80:DCA9 (baseline): 300 execuções, {'m8,x16': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `count((gi1 == 0x6ADC) & (gi2 == 0x521E) & (gi3 == 0x419C) & (gi4 == 0x311A) & (gi5 == 0x2098)) >= 0.8 * len(gi1)` | ✅ | 560 vs 448.0 | cor 1: gi rosa do Dan (5 tons) na maior parte da luta |
| `all(esp14 == cabelo) and all(esp15 == cab15) and all(esp1 == contorno) and all(esp9 == gi1)` | ✅ | True | espelho (CGRAM 11) = cópia fiel da paleta do Ken (CGRAM 14) nesta cor: as luvas continuam loiras |
| `all(esp14 == baseline.esp14) and all(esp15 == baseline.esp15)` | ✅ | True | fora da cor 2 a regra da luva não age (igual à base) |
| `all(pele == baseline.pele) and all(contorno == baseline.contorno) and all(hadouken == baseline.hadouken) and all(rose == baseline.rose)` | ✅ | True | pele, contorno, Hadouken e Rose iguais à base variante |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ✅ | True | SINCRONIA: a luta joga igual à base variante (mesmo código → mesmo timing/RNG); contra a ROM limpa isto descolava no frame 1 |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-005/luta-rosa/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-005/luta-rosa/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-005/luta-rosa/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-luta-rosa/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-luta-rosa/video.mp4`

## Cenário `luta-preta` — pontuação 0.8571
- state: `games/sfa2/states/luta-ken-2socos-fight.mss` · baseline: `runs/baselines/sfa2/luta-preta-15877d1d5087727e` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-luta-preta`
- divergência visual: 81/140 frames (primeira f44, pico 0.208% em f316)
- sincronia mod × variante (WRAM): ✅ em sincronia (só buffers mudam) — f40: 4 B, f320: 4 B, f599: 4 B
- M/X dinâmico no hijack 80:8312 (baseline): 300 execuções, {'m8,x16': 300}
- M/X dinâmico no hijack 80:BA9A (baseline): 83 execuções, {'m8,x16': 83}
- M/X dinâmico no hijack 80:DCA9 (baseline): 300 execuções, {'m8,x16': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `count((gi1 == 0x2908) & (gi2 == 0x18C6) & (gi3 == 0x14A5) & (gi4 == 0x1084) & (gi5 == 0x1084)) >= 0.8 * len(gi1)` | ✅ | 456 vs 448.0 | cor 2: gi preto do Akuma (5 tons) na maior parte da luta |
| `count(gi1 == 0x2908) >= 0.5 * len(gi1) and all((gi1 != 0x2908) | ((esp14 == 0x2908) & (esp15 == 0x1084)))` | ✅ | True | LUVAS: com o gi preto, os tons 14/15 do espelho são a rampa preta de 2 tons ($2908 realce, $1084 sombra) |
| `all((baseline.gi1 != 0x2908) | ((baseline.esp14 == 0x339E) & (baseline.esp15 == 0x029C)))` | ✅ | True | na base variante (LUVA_OFF) a luva continua no ouro original: a ÚNICA diferença A/B é a luva |
| `all(esp1 == contorno) and all(esp9 == gi1)` | ❌ | False | o resto do espelho é cópia fiel (pele/contorno/gi não mudam nos cels da luva) |
| `all(cabelo == baseline.cabelo) and count(cabelo == 0x339E) >= 0.8 * len(cabelo)` | ✅ | True | o CABELO (paleta 14, tom 14) continua loiro |
| `all(pele == baseline.pele) and all(contorno == baseline.contorno) and all(hadouken == baseline.hadouken) and all(rose == baseline.rose)` | ✅ | True | pele, contorno, Hadouken e Rose iguais à base variante |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ✅ | True | SINCRONIA: a luta joga igual à base variante (mesmo código → mesmo timing/RNG); contra a ROM limpa isto descolava no frame 1 |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-005/luta-preta/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-005/luta-preta/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-005/luta-preta/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-luta-preta/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-luta-preta/video.mp4`

## Cenário `selecao-e-vs` — pontuação 1.0
- state: `games/sfa2/states/selecao.mss` · baseline: `runs/baselines/sfa2/selecao-e-vs-e3e887f548768e6c` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-selecao-e-vs`
- divergência visual: 0/110 frames (primeira fNone, pico 0.0% em f0)
- sincronia mod × variante (WRAM): ✅ em sincronia (só buffers mudam) — f0: 0 B, f550: 0 B, f1099: 0 B
- M/X dinâmico no hijack 80:8312 (baseline): 300 execuções, {'m8,x16': 300}
- M/X dinâmico no hijack 80:BA9A (baseline): 9 execuções, {'m8,x16': 9}
- M/X dinâmico no hijack 80:DCA9 (baseline): 300 execuções, {'m8,x16': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `count(ret1 == 0x7E06) >= 20 and all((ret1 != 0x7E06) | ((ret2 == 0x7102) & (ret3 == 0x5881) & (ret4 == 0x3C20)))` | ✅ | True | retrato da seleção com gi azul (4 tons) quando o cursor está no Ken |
| `count(vs1 == 0x7E06) >= 20 and all((vs1 != 0x7E06) | ((vs2 == 0x7102) & (vs3 == 0x5881) & (vs4 == 0x3C20)))` | ✅ | True | retrato da tela VS com gi azul (4 tons) |
| `all(ret1 != 0x113E) and all(vs1 != 0x113E) and all(spr1 != 0x011E)` | ✅ | True | o vermelho original nunca aparece (retrato, VS, sprite pequeno) |
| `all(retpele == baseline.retpele) and all(ret1 == baseline.ret1)` | ✅ | True | outros personagens e sincronia iguais à base variante |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-005/selecao-e-vs/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-005/selecao-e-vs/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-005/selecao-e-vs/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-selecao-e-vs/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-selecao-e-vs/video.mp4`

## Cenário `selecao-e-vs-rosa` — pontuação 1.0
- state: `games/sfa2/states/selecao.mss` · baseline: `runs/baselines/sfa2/selecao-e-vs-rosa-d1374f8e31038af4` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-selecao-e-vs-rosa`
- divergência visual: 0/110 frames (primeira fNone, pico 0.0% em f0)
- sincronia mod × variante (WRAM): ✅ em sincronia (só buffers mudam) — f0: 0 B, f550: 0 B, f1099: 0 B
- M/X dinâmico no hijack 80:8312 (baseline): 300 execuções, {'m8,x16': 300}
- M/X dinâmico no hijack 80:BA9A (baseline): 9 execuções, {'m8,x16': 9}
- M/X dinâmico no hijack 80:DCA9 (baseline): 300 execuções, {'m8,x16': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `count(ret1 == 0x521E) >= 20 and all((ret1 != 0x521E) | ((ret2 == 0x419C) & (ret3 == 0x311A) & (ret4 == 0x2098)))` | ✅ | True | retrato da seleção (cor 1) com rosa do Dan (4 tons) |
| `count(vs1 == 0x521E) >= 20 and all((vs1 != 0x521E) | ((vs2 == 0x419C) & (vs3 == 0x311A) & (vs4 == 0x2098)))` | ✅ | True | retrato da tela VS (cor 1) com rosa do Dan |
| `count(ret1 == 0x7E06) >= 1 and all(ret1 != 0x6952) and all(vs1 != 0x6952) and all(ret1 != 0x113E)` | ✅ | True | o preview (cor 0) fica azul e o roxo/vermelho originais nunca aparecem |
| `all(spr1 != 0x5910) and all(spr1 != 0x011E)` | ✅ | True | sprite pequeno sem o roxo nem o vermelho originais |
| `all(retpele == baseline.retpele) and all(ret1 == baseline.ret1)` | ✅ | True | outros personagens e sincronia iguais à base variante |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-005/selecao-e-vs-rosa/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-005/selecao-e-vs-rosa/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-005/selecao-e-vs-rosa/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-selecao-e-vs-rosa/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-selecao-e-vs-rosa/video.mp4`

## Cenário `selecao-e-vs-preta` — pontuação 1.0
- state: `games/sfa2/states/selecao.mss` · baseline: `runs/baselines/sfa2/selecao-e-vs-preta-db9f95e4595085dd` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-selecao-e-vs-preta`
- divergência visual: 1/110 frames (primeira f120, pico 0.126% em f120)
- sincronia mod × variante (WRAM): ✅ em sincronia (só buffers mudam) — f0: 0 B, f550: 4 B, f1099: 0 B
- M/X dinâmico no hijack 80:8312 (baseline): 300 execuções, {'m8,x16': 300}
- M/X dinâmico no hijack 80:BA9A (baseline): 9 execuções, {'m8,x16': 9}
- M/X dinâmico no hijack 80:DCA9 (baseline): 300 execuções, {'m8,x16': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `count(ret1 == 0x2908) >= 20 and all((ret1 != 0x2908) | ((ret2 == 0x18C6) & (ret3 == 0x14A5) & (ret4 == 0x1084)))` | ✅ | True | retrato da seleção (cor 2) com preto do Akuma (4 tons, com realce) |
| `count(vs1 == 0x2908) >= 20 and all((vs1 != 0x2908) | ((vs2 == 0x18C6) & (vs3 == 0x14A5) & (vs4 == 0x1084)))` | ✅ | True | retrato da tela VS (cor 2) com preto do Akuma |
| `count(ret1 == 0x7E06) >= 1 and all(ret1 != 0x7B58) and all(vs1 != 0x7B58) and all(ret1 != 0x113E)` | ✅ | True | o preview (cor 0) fica azul e o branco/vermelho originais nunca aparecem |
| `all((spr1 != 0x7BDE) | (spr2 != 0x7B58))` | ✅ | True | sprite pequeno nunca com o PAR de tons do gi branco (o $7BDE sozinho é o gi do Ryu) |
| `all(retpele == baseline.retpele) and all(ret1 == baseline.ret1)` | ✅ | True | outros personagens e sincronia iguais à base variante |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-005/selecao-e-vs-preta/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-005/selecao-e-vs-preta/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-005/selecao-e-vs-preta/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-selecao-e-vs-preta/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-selecao-e-vs-preta/video.mp4`

## Cenário `regressao-verde` — pontuação 1.0
- state: `games/sfa2/states/luta-ken-2chutes-fight.mss` · baseline: `runs/baselines/sfa2/regressao-verde-eb5dc3a639417a94` · mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-regressao-verde`
- divergência visual: 0/140 frames (primeira fNone, pico 0.0% em f40)
- sincronia mod × variante (WRAM): ✅ em sincronia (só buffers mudam) — f40: 0 B, f320: 0 B, f599: 0 B
- M/X dinâmico no hijack 80:8312 (baseline): 300 execuções, {'m8,x16': 300}
- M/X dinâmico no hijack 80:BA9A (baseline): 27 execuções, {'m8,x16': 27}
- M/X dinâmico no hijack 80:DCA9 (baseline): 300 execuções, {'m8,x16': 300}

| check | resultado | valores | descrição |
|---|---|---|---|
| `count((gi1 == 0x39C8) & (gi2 == 0x2946) & (gi3 == 0x2104) & (gi4 == 0x1CE4) & (gi5 == 0x18C2)) >= 0.8 * len(gi1)` | ✅ | 560 vs 448.0 | cor 3: gi verde-escuro ORIGINAL (5 tons), intocado |
| `all(gi1 == baseline.gi1) and all(gi5 == baseline.gi5)` | ✅ | True | igual à base variante |
| `all(esp14 == cabelo) and all(esp15 == cab15) and all(esp1 == contorno) and all(esp9 == gi1)` | ✅ | True | espelho (CGRAM 11) = cópia fiel da paleta do Ken (CGRAM 14) nesta cor: as luvas continuam loiras |
| `all(pele == baseline.pele) and all(contorno == baseline.contorno) and all(hadouken == baseline.hadouken) and all(rose == baseline.rose)` | ✅ | True | pele, contorno, Hadouken e Rose iguais à base variante |
| `all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)` | ✅ | True | SINCRONIA: a luta joga igual à base variante (mesmo código → mesmo timing/RNG); contra a ROM limpa isto descolava no frame 1 |

**Olhar (ferramenta de leitura de imagens):**
- lado a lado: `cycles/sfa2-ken-azul-e-rosa/cycle-005/regressao-verde/compare.png`
- RAM mod × baseline: `cycles/sfa2-ken-azul-e-rosa/cycle-005/regressao-verde/trace_compare.png`
- divergência: `cycles/sfa2-ken-azul-e-rosa/cycle-005/regressao-verde/divergence.png`
- folha do mod: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-regressao-verde/sheet.png` · vídeo: `runs/cycles/sfa2-ken-azul-e-rosa/cycle-005-regressao-verde/video.mp4`

## Próximo passo
1. Ver as imagens acima e decidir o veredito visual: `fab cycle verdict mods/sfa2-ken-azul-e-rosa --cycle 5 <evoluiu|regrediu|igual|objetivo-cumprido|inconclusivo> --notes "…"`
2. Se não cumpriu: ajustar `patch.asm` (com evidência nova) e correr outro ciclo.
