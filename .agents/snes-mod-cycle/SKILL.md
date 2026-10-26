---
name: snes-mod-cycle
description: Do código 65816 ao mod verificado no emulador — protocolo de engenharia reversa e de patch Asar (evidência, auditoria M/X, hijack de 4 bytes, freecode/expand_to, portões do build) e o ciclo autônomo de evolução (roda mod × base a partir do savestate, compara frames/RAM/checks, olha as imagens, registra o veredito e itera sozinho até cumprir o objetivo). Use ao investigar código 65816, escolher hijack, escrever/rever patch.asm, explicar uma rotina, e quando o pedido for "roda o ciclo", "itera até funcionar", "testa o mod no emulador", "verifica se evoluiu" — ou como passo 7 da snes-mod-factory. Argumento: o diretório do mod (ex.: mods/meu-mod).
---

# Patch 65816 + ciclo de evolução

**A** = escrever o patch sem quebrar o jogo. **B** = o loop que prova que ele funciona.
Fluxo completo (ROM → state → investigação → mod): skill **snes-mod-factory**. Cor/sprite/gráfico: **snes-sprite-paint**.

## A. Patch 65816

### A1. Evidência (antes de qualquer `org`)
- Todo endereço do `.asm` tem `evidence_id`. Separe **observação** (bytes, hits, xrefs), **inferência** (o que
  significa) e **incógnita** (M/X ambíguo, ponteiro indireto, DP/DB não resolvidos). Livro-razão: `fab re evidence <jogo>`.
- Dinâmico primeiro (é o que o jogo faz): `fab ram search/query` acha a variável → `fab probe writes|reads` acha
  a instrução (reconstruída do PC seguinte, com M/X reais) → `fab probe exec` audita o ponto.
- Estático para entender: `fab re cdl` (vários states) → `fab re analyze` → `fab re func|xrefs|search|decompile`
  (o decompile é aproximação: cruze com `func`).

### A2. M/X (SEP/REP) — obrigatório antes de hijack
- M = bit 5 (`$20`): A de 8 bits. X = bit 4 (`$10`): X/Y de 8 bits. Imediatos de `LDA ADC SBC AND ORA EOR CMP BIT`
  seguem M; de `LDX LDY CPX CPY` seguem X.
- Rastreie o último SEP/REP (`fab re func`) **e** confirme com `fab probe exec` (todas as execuções com o mesmo M/X;
  senão é incógnita: trate os dois casos ou escolha outro ponto).
- Declare em `mod.json → hijacks[]`: `{"addr", "m", "x", "evidence"}`. O build casa pelo offset no arquivo (qualquer
  espelho vale: `00:82CB` ≡ `80:82CB`; S-DD1 `C0:0312` ≡ `80:8312`).

### A3. Hijack e Asar
- Diretiva do `game.json`: `lorom | hirom | exhirom | sa1rom` (S-DD1 usa `lorom`: o `org` é o endereço do Asar, não o
  da CPU — `fab addr <jogo> 0x<pc> --pc` mostra os dois).
- **Regra dos 4 bytes**: `autoclean jml|jsl Rotina` sobre instruções INTEIRAS que somem ≥ 4 bytes, sem desvio para
  dentro da janela; sobra → `nop`. Reproduza as instruções sobrescritas, volte com `jml` numa fronteira de instrução,
  `php/plp` + `pha/phx/phy` se mexer em flags/registradores; `jsl` termina em `rtl`.
- **Todo imediato com sufixo** (`lda.b #$08`, `ldx.w #$0100`): sem ele o Asar escolhe o tamanho e `A9 08 00` com M=8
  vira BRK.
- Código novo depois de `freecode` (bancos $10-$3F), dado grande depois de `freedata`. Sem espaço → `"expand_to"` no
  mod.json (o build preenche com $00, corrige o cabeçalho e lista os emuladores que rodam a ROM maior).
  Valor fixo num lugar conhecido → `mod.json → data[]` com evidência.
- WRAM acima de $1FFF ou DB incerto → endereçamento long (`sta.l $7E1DF9`). Byte "livre" de WRAM só com evidência
  (nenhum hit de `probe writes/reads` em cenários variados **e** nenhum `re xrefs`).
- Geradores que já fazem tudo isso: `fab paint set|remap|oam-mirror` e `fab gfx override`.

### A4. Build
`./fab build mods/<id>` monta numa cópia (`build/<id>/`) e **recusa**: sobrescrita não declarada, hijack sem M/X ou
com operando órfão, imediato com tamanho errado para o M/X do ponto (aponta arquivo:linha). Saem regiões, labels,
BPS e, se a ROM cresceu, `rom_expandida` (emuladores recomendados).

## B. Ciclo de evolução — repita sem pedir confirmação

Entrada: `mods/<id>/mod.json` (cenários com `state`, `input`, `frames`, `watch`, `checks` + **um de regressão**) e o patch.

1. **Hipótese** numa frase, com `evidence_id`.
2. `./fab cycle run mods/<id> --note "<hipótese>"` (build falhou = ciclo `falhou`: leia o erro do Asar e corrija).
3. **Leia** `cycles/<id>/cycle-NNN/report.md`: pontuação, checks (os dois lados), M/X dinâmico do hijack (igual ao
   declarado), divergência.
4. **Olhe** (Read) `compare.png` e `trace_compare.png` de cada cenário; na dúvida `divergence.png` e os frames de
   `runs/cycles/<id>/cycle-NNN-<cenário>/frames/`. Checklist: `snes-mod-factory/references/video.md`.
5. `./fab cycle verdict mods/<id> --cycle N <evoluiu|regrediu|igual|objetivo-cumprido|inconclusivo> --notes "<frames: o que viu>"`.
6. **Decida**: `objetivo-cumprido` só com todos os checks ✅ + imagens sem colateral + regressão com 0 frames
   divergentes. `regrediu` → volte ao último patch bom. `igual`/`inconclusivo` → mais evidência ou checks melhores
   antes de mexer no patch.
7. **Pare** em `max_cycles` (padrão 8) ou 3 ciclos sem evolução: reporte o bloqueio e o melhor ciclo (`fab cycle status`).

Regras: uma hipótese por ciclo; nunca enfraqueça um check para passar (check errado → corrija e explique na nota; o
ledger é append-only); mod com código usa base **variante** (abaixo).

## Relatório e fechamento
Ao usuário: endereços com `evidence_id` · M/X (estático + dinâmico) · patch comentado · endereços finais (`.sym`) ·
ciclos (pontuação, imagens, veredito) · incógnitas. Depois: `games/<jogo>/notes.md`, skill `rom-<jogo>` (Estado,
Como continuar, Avanços) e `coala.py add` com o que for durável.

## FAQ
- **Checks contra a ROM limpa falham com o mod certo.** Todo hook muda o timing e o RNG: a luta "joga diferente"
  desde o frame 1. Base = o próprio mod com a mudança desligada por VALOR: `if defined("X_OFF")` no `.asm` +
  `mod.json → "baseline": {"variant": {"name": "off", "defines": {"X_OFF": "1"}}}`. O ciclo confere que a variante não
  muda opcode e mede a sincronia pela WRAM. Nunca desligue mudando uma comparação (o desvio muda o tempo).
- **`fab probe exec` no meu código dá 0 hits.** Sonde pelo rótulo do build atual (`fab probe exec <jogo> <Rótulo>
  --mod <id>`) e verifique por EFEITO (RAM/CGRAM/VRAM), não por "o código rodou".
- **Onde pôr um hook de paleta/OAM/gráfico?** `fab ppu dma` mostra a instrução que dispara cada DMA (com M/X).
  Código no VBlank tem de caber nele: `fab paint check` mede a linha de cada DMA.
- **`No freespace found`.** `expand_to` maior, ou menos código; no S-DD1 só os 2 MiB de baixo são LoROM (o resto é
  visto por janela — o `fab gfx override --expand` já trata).
- **O REA serve para a ROM?** Não: o REA 6.7.0 recusa ROM de SNES (`unsupported binary format`). Equivalências: `open_binary` →
  `fab re cdl` + `analyze`; `list_procedures`/`search` → `fab re funcs|search`; `xrefs` → `fab re xrefs` (+ `fab probe
  writes`); `decompile` → `fab re decompile|func`; `audit_residual_unknowns` → `fab probe exec`;
  `verify_reconstruction` → `fab build` + `fab cycle run`. O REA fica para PE/ELF/JS/.NET/APK.
- **Testes "falham" com `ModuleNotFoundError`.** Rode `./fab selftest` (usa a `.venv`), nunca o Python do sistema.
