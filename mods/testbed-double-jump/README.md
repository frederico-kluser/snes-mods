# Pulo duplo (patch do guia REA/Asar) — exemplo de referência

Jogo: `testbed` (ROM homebrew de `fixtures/testbed/`, LoROM 1 MB) · Objetivo: permitir um segundo pulo
no ar, uma vez por voo, sem alterar o pulo simples.

O `patch.asm` é o patch de "Salto Duplo" do guia, praticamente literal. O testbed coloca a rotina de
pulo exatamente nos endereços que o guia descreve, então o patch roda sem adaptação.

## Evidências
Reproduzíveis com o state `parado` e o macro `20;1 B;18;1 B;100` (140 frames). Os `evidence_id`
são determinísticos para as mesmas entradas (`./fab re evidence testbed <id>` mostra o registro).

| fato | tipo | evidence_id | comando |
|---|---|---|---|
| `$80:A420` executa 140×, sempre com **M=8, X=16** (ps=$26) | dinâmico | `ev-8fa6f3731b33` | `fab probe exec testbed 80:A420 …` |
| `$7E:007D` (vel. Y) é escrito por `80:8250 STA $7D` (física), `80:8276 STZ $7D` (aterrissagem) e `80:A42C STA $7D` (pulo) | dinâmico | `ev-6647b8abb9ce` | `fab probe writes testbed 7E:007D …` |
| `$7E:1DF9` nunca é escrito nem lido pelo jogo original | dinâmico | `ev-56a36448f853`, `ev-cdf39fc03d1a` | `fab probe writes/reads testbed 7E:1DF9 …` |
| nenhuma referência estática a `$1DF9` | estático | `ev-7146a5cb849b` | `fab re xrefs testbed 7E:1DF9` |
| rotina `80:A41E`: `SEP #$20` na entrada; `LDA $72 : BNE` = 4 bytes em `80:A420`; `LDA $16` em `80:A424` e `RTS` em `80:A438` são fronteiras de instrução | estático | `ev-3ef14abf2597` | `fab re func testbed 80:A420` |
| papéis de `$72` (no ar), `$16` (botões novos), `$7D` (vel. Y), `$96` (Y 12.4) | dinâmico | (ram query) | `fab ram search testbed --state parado --macro "20;1 B;40" --frames 61` + `fab ram query <run> --unchanged 0:19 --changed 19:30` |

Incógnitas residuais: nenhuma relevante (M/X idêntico em todas as execuções; um único chamador).

## Cenários e critérios (`mod.json`)
- `pulo-duplo`: ápice ≥ 20 px acima do original, dois impulsos de subida, aterrissa, flag usada e
  reiniciada.
- `pulo-simples` (regressão): trajetória X/Y idêntica à da ROM original.

## Resultado
`./fab cycle run mods/testbed-double-jump` → 6/6 checks ✅; hijack `80:A420` OK (JML `$90:8008`,
4 bytes, sem bytes órfãos); freecode em `$90:8000` (RATS, 40 bytes); imagens divergem a partir do f40
(2º B no f39 + 1 frame de exibição); regressão com 0/35 frames divergentes; veredito visual
`objetivo-cumprido`. BPS: `build/testbed-double-jump/testbed-double-jump.bps` (165 bytes).
