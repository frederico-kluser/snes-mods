---
name: snes-rea-modder
description: Protocolo de engenharia reversa de ROMs de Super Nintendo (WDC 65C816) e de engenharia de patches Asar, adaptado do guia "REA + Ghidra + Asar" à realidade verificada deste repositório (REA 6.7.0 não abre ROMs de SNES; o lane estático é Ghidra 12.1.4 + ghidra-snes via `fab re`, o dinâmico é o MesenCE via `fab probe/ram`). Regras de evidência, auditoria obrigatória das flags M/X (SEP/REP), geometria de hijack (regra dos 4 bytes), autoclean/freecode e verificação do build. Use ao investigar código 65816, escolher pontos de hijack, escrever/rever patch.asm ou explicar o que uma rotina faz.
---

# SNES REA Modder — protocolo 65816 e de patches

## 1. Regras de ouro
- **Asar ≠ .asar**: aqui `asar` é o montador 65816/SPC700/SuperFX (RPGHacker/asar 1.91). No REA,
  `.asar` é arquivo Electron — nunca use ferramentas de JavaScript/Electron em ROM ou patch de SNES.
- **Imutabilidade**: a ROM original e `roms/<id>/<id>.sfc` são sagradas (só leitura). O Asar sempre
  escreve numa cópia em `build/<mod>/` (o `fab build` faz isso).
- **Evidência**: toda conclusão separa **observações** (bytes, instruções, xrefs, hits de sonda),
  **inferências** (o que um endereço significa) e **incógnitas residuais** (M/X ambíguo, ponteiros
  indiretos, DP/DB não resolvidos). Os comandos `fab re …` e `fab probe …` devolvem `evidence_id`,
  `analysis_profile`, `normalized_result` e `limitations` (o contrato Evidence do REA) e gravam o
  livro-razão em `work/evidence/<jogo>.jsonl` (`fab re evidence <jogo>`).

## 2. REA: o que vale aqui (verificado em 2026-10-24)
- O MCP `rea` (rea-agents 6.7.0, 207 ferramentas) está registrado **só neste projeto** (`.mcp.json`,
  gerado por `fab setup`) com o provedor Ghidra 12.1.4 + JDK 21 **disponível** (`fab doctor --rea`).
- Para ROM de SNES ele **não serve**: `rea inspect rom.sfc` → `unsupported binary format`;
  `--target-format raw-binary --architecture 65816` → validação recusa (só `6502|x86|x86_64|arm|arm64|m68k`).
  O suporte a 65816 está no PR morluto/rea#4911 (aberto; mesmo nele o Windows recusa raw 65816 e o
  carregamento é contíguo, sem LoROM/HiROM). Use o REA para binários PE/ELF/JS/.NET/APK.
- Mapa do guia → comandos daqui:

| fase do guia (REA) | aqui |
|---|---|
| `binary_session` / `rea doctor` | `./fab doctor --rea` |
| `open_binary` (ghidra + ghidra-snes) | `./fab re cdl <jogo> --state …` (sementes M/X) → `./fab re analyze <jogo>` |
| `list_procedures` / `search` | `./fab re funcs <jogo>` / `./fab re search <jogo> "<regex>"` |
| `xrefs` | `./fab re xrefs <jogo> <addr>` (+ espelhos WRAM e operandos DP) e, mais confiável, `./fab probe writes/reads` |
| `analyze_function` / `decompile` / `instructions` | `./fab re func` / `./fab re decompile` / `./fab disasm` |
| `audit_residual_unknowns` | `./fab probe exec <jogo> <addr>` (M/X/E reais em cada execução) + mais CDL |
| `verify_reconstruction` | `./fab build mods/<id>` (diff, hijack, labels, BPS) + `./fab cycle run` |
| `close_binary` | não se aplica (o export fica em `work/ghidra/<jogo>/export/`) |

## 3. Pré-voo (automático no `fab rom add`)
Cabeçalho SMC (tamanho % 1024 == 512 → remove 512 bytes), mapa (pontuação de cabeçalhos em
$7FC0/$FFC0/$40FFC0: checksum+complemento, map mode, vetor de reset, título, tamanho), chipset e
vetores ficam em `games/<jogo>/game.json`. Confira `checksum.valid` e `mapping` antes de tudo.

## 4. Investigação (do resumo para o detalhe)
1. **Âncoras de hardware/RAM**: controle $4218-$421F (JOY1H = `B Y Sel St U D L R`), PPU $2100-$2133,
   DMA $420B/$420C/$43xx, APU $2140-$2143, WRAM $7E:0000-$7F:FFFF (espelho $0000-$1FFF).
2. **Dinâmico primeiro** (é o que o jogo faz de verdade): `fab ram search/query` para achar a variável,
   `fab probe writes <jogo> 7E:xxxx` para achar quem escreve (a instrução vem reconstruída do PC
   seguinte, com M/X reais), `fab probe exec` para auditar um endereço.
3. **Estático para entender**: `fab re cdl` com vários states (mais cobertura = mais sementes),
   `fab re analyze`, depois `fab re func <addr>` (instruções com m8/m16·x8/x16, chamadores, chamadas)
   e `fab re decompile` (aproximação — cruze sempre com as instruções).
4. Registre endereço, significado, evidência e incertezas em `games/<jogo>/notes.md`.

## 5. Auditoria obrigatória M/X (regra SEP/REP)
A largura dos imediatos depende de M (bit 5, $20: A) e X (bit 4, $10: X/Y) em runtime. Antes de
escolher um hijack ou escrever código que roda no contexto do jogo:
- `SEP #$20` → A 8 bits · `REP #$20` → A 16 bits · `SEP/REP #$10` → índices · `#$30` → ambos.
- Rastreie para trás até o último SEP/REP do fluxo (`fab re func`) **e confirme dinamicamente** com
  `fab probe exec <jogo> <addr>` (todas as execuções precisam ter o mesmo M/X; senão, é incógnita:
  trate os dois estados ou escolha outro ponto).
- Registre em `mod.json → hijacks: [{"addr", "m", "x", "evidence"}]`; o ciclo confere M/X na baseline.

## 6. Engenharia do patch (Asar)
- Comece com `lorom`/`hirom`/`exhirom`/`sa1rom` conforme `game.json`.
- **Regra dos 4 bytes**: `jml`/`jsl` ocupam 4 bytes; o `org` substitui instruções **inteiras** que somem
  ≥ 4 bytes; sobrando bytes (5, 6, 7…) complete com `nop` — nunca deixe operando órfão
  (o `fab build` aponta `orphan_bytes_after` e reprova JSL com órfãos).
- `autoclean jml/jsl Rotina` no hijack; código novo depois de `freecode` (bancos $10-$3F, com espelho de
  RAM/I-O) e tabelas grandes depois de `freedata`. ROM sem bancos $10+ livres → `"expand_to": "1MB"`.
- Na rotina nova: reproduza as instruções sobrescritas; se mudar M/X ou registradores que o original
  espera, use `php`/`plp` e `pha/phx/phy` ↔ `ply/plx/pla`; chamada por `jsl` termina com `rtl`;
  volte com `jml` para uma **fronteira de instrução** verificada.
- WRAM acima de $1FFF ou DB incerto → endereçamento long (`sta.l $7E1DF9`).
- Byte de WRAM "livre" só com evidência: `fab probe writes/reads` sem hits em cenários variados
  **e** `fab re xrefs` sem referências.

## 7. Build, verificação e relatório
`./fab build mods/<id>`: Asar com `--fix-checksum=on --symbols=wla` na cópia; verifica código de saída e
avisos (`Wfreespace_leaked`), lista regiões (hijacks com desmontagem antes/depois e checagem de
fronteira; freespace com tag RATS), labels do `.sym` e gera o BPS. Depois `./fab cycle run` (snes-mod-cycle).
Relatório final ao usuário: (a) endereços de ROM/WRAM com `evidence_id`; (b) M/X auditado (estático +
dinâmico); (c) o `patch.asm` comentado; (d) endereços finais do `.sym`/freespace; (e) resultado dos
ciclos (pontuação, imagens, veredito); (f) incógnitas residuais.

## 8. Legal
Nunca versionar nem distribuir a ROM comercial, savestates ou dumps de código descompilado. Distribua
`patch.asm` e/ou o `.bps`.
