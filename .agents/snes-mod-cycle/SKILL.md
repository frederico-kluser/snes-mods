---
name: snes-mod-cycle
description: Ciclo autônomo de evolução de um mod de SNES — roda o emulador a partir do savestate do cenário, grava frames/vídeo/RAM do mod e da ROM original, compara, avalia os critérios, olha as imagens, registra o veredito (evoluiu / regrediu / igual / objetivo-cumprido) e itera no patch sozinho até cumprir o objetivo ou esgotar os ciclos. Use quando o pedido for "roda o ciclo", "itera até funcionar", "modo ciclo", "verifica se evoluiu", "testa o mod no emulador", ou como passo 7 da snes-mod-factory. Argumento: o diretório do mod (ex.: mods/meu-mod).
---

# Ciclo de evolução (`fab cycle`)

Entrada: `mods/<id>/` com `mod.json` válido (cenários com `state`, `input`, `frames`, `watch`,
`checks`) e `patch.asm`. Se faltar um cenário de regressão, crie-o antes do primeiro ciclo.

## Loop — repita sem pedir confirmação

1. **Hipótese**: escreva em uma frase o que esta iteração muda e por quê (com `evidence_id`).
2. **Rodar**: `./fab cycle run mods/<id> --note "<hipótese>"`. Build falhou → leia os erros do Asar,
   corrija e rode de novo (conta como ciclo, veredito automático `falhou`/`regrediu`).
3. **Ler** `cycles/<id>/cycle-NNN/report.md`: pontuação, checks (valores dos dois lados), M/X dinâmico
   no hijack (precisa ser consistente e igual ao assumido em `mod.json → hijacks`), divergência.
4. **Olhar** com Read, para cada cenário: `compare.png` e `trace_compare.png`; na dúvida
   `divergence.png`, a folha/vídeo do mod e frames individuais (`runs/cycles/<id>/cycle-NNN-<cenário>/frames/`).
   Use o checklist de `snes-mod-factory/references/video.md`.
5. **Registrar o veredito visual**:
   `./fab cycle verdict mods/<id> --cycle N <evoluiu|regrediu|igual|objetivo-cumprido|inconclusivo> --notes "<o que viu, com frames>"`.
6. **Decidir**:
   - `objetivo-cumprido` só com TODOS os checks ✅ **e** imagens confirmando o efeito sem colaterais
     **e** regressão com 0 frames divergentes → pare e entregue (passo 8 da snes-mod-factory).
   - `regrediu` → volte o `patch.asm` para o último ciclo bom (`git diff`/`git checkout -- mods/<id>/patch.asm`
     se estiver commitado; senão desfaça a mudança) e tente outra hipótese.
   - `igual`/`inconclusivo` → antes de mexer no patch, colete evidência nova (`fab probe`, `fab ram`,
     `fab re`) ou acrescente checks/cenários que meçam melhor o objetivo.
7. **Parar** também quando: `max_cycles` do mod.json (padrão 8) for atingido, ou 3 ciclos seguidos sem
   evolução. Nesses casos, reporte ao usuário o bloqueio com as evidências e o melhor ciclo
   (`./fab cycle status mods/<id>` → `best_cycle`).

## Regras
- Uma hipótese por ciclo; mudanças pequenas e atribuíveis.
- Nunca enfraquecer ou apagar checks para "passar"; se um check estava errado, corrija-o, explique na
  nota e rode de novo (o ledger é append-only e guarda o histórico).
- A baseline é a ROM limpa com o mesmo state/macro (cache automático); se o cenário mudar, ela é refeita.
- O veredito automático compara a pontuação dos checks com o ciclo anterior; o visual é seu.
- Ao terminar: atualize `games/<jogo>/notes.md` e grave na memória CoALA os fatos verificados
  (endereços, M/X, o que funcionou e o que não funcionou).
