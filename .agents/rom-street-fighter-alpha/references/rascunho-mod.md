# Rascunho do mod `sfa2-ken-gi-azul` (ainda não criado)

Tudo aqui foi desenhado a partir das evidências da `SKILL.md`; nada rodou ainda. Ao criar o mod, copie
os blocos para `mods/sfa2-ken-gi-azul/` e ajuste o que o primeiro baseline mostrar (sem enfraquecer
checks: se um estiver errado, corrija-o e explique na nota do ciclo).

## Objetivo (`--goal`)
O uniforme padrão do Ken (cor 0, escolhida com soco) passa de gi vermelho a gi azul royal na luta, no
sprite e no retrato da seleção e na tela VS; pele, cabelo, faixa, efeitos, a cor de chute (roxa) e os
outros personagens ficam iguais e a lógica da luta não muda.

## `patch.asm`
```asm
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
org $BE8272
    dw !gi_0, !gi_1, !gi_2, !gi_3, !gi_4

; Retrato do Ken, cor 0 (seleção: BG pal 6; tela VS: sprite pal 0): PC 0x1F4E60 = $BE:CE60; gi = cores 5-8
; ⚠ a cor 8 ($000F) também pinta os olhos do retrato — decidir no ciclo (print 15)
org $BECE6A
    dw $7E06, $7102, $5881, $3C20
```

## `mod.json`
```json
{
  "id": "sfa2-ken-gi-azul",
  "title": "Ken de gi azul",
  "game": "sfa2",
  "goal": "(o texto da seção Objetivo)",
  "patches": ["patch.asm"],
  "expand_to": null,
  "hijacks": [],
  "data": [
    {"addr": "BE:8272", "length": 10, "evidence": "paleta do lutador Ken cor 0, cores 9-13 (ev-dbaa2b8b4bf8)"},
    {"addr": "BE:CE6A", "length": 8, "evidence": "paleta do retrato do Ken cor 0, cores 5-8 (dump de CGRAM na seleção/VS)"}
  ],
  "max_cycles": 8,
  "scenarios": [
    {
      "id": "luta-soco",
      "desc": "Ken (cor 0) luta contra a Rose: anda, Hadouken, pulo, Shoryuken, golpes agachado",
      "state": "luta-ken-rose-fight",
      "input": "luta.txt",
      "frames": 600,
      "capture": {"every": 4},
      "watch": ["gi1=cgram:01D2:2", "gi2=cgram:01D4:2", "gi3=cgram:01D6:2", "gi4=cgram:01D8:2", "gi5=cgram:01DA:2",
                "pele=cgram:01C8:2", "cabelo=cgram:01DC:2", "contorno=cgram:01C2:2",
                "hadouken=cgram:0104:2", "rose=cgram:01F2:2",
                "x1=7E:0709:2", "hp1=7E:073E", "hp2=7E:09BE"],
      "checks": [
        {"id": "gi-azul", "expr": "all((baseline.gi1 != 0x011E) | ((gi1 == 0x7E06) & (gi2 == 0x7102) & (gi3 == 0x60A1) & (gi4 == 0x5060) & (gi5 == 0x4440)))", "desc": "sempre que a ROM original mostra o gi vermelho, o mod mostra os 5 tons azuis"},
        {"id": "gi-normal-na-tela", "expr": "count(baseline.gi1 == 0x011E) >= 0.8 * len(gi1)", "desc": "sanidade: o cenário mostra o uniforme normal na maior parte do tempo"},
        {"id": "efeitos-iguais", "expr": "all((baseline.gi1 == 0x011E) | (gi1 == baseline.gi1))", "desc": "nas paletas de efeito (choque, fogo) o mod é igual ao original"},
        {"id": "pele-cabelo-faixa", "expr": "all(pele == baseline.pele) and all(cabelo == baseline.cabelo) and all(contorno == baseline.contorno)", "desc": "o resto da paleta do Ken não muda"},
        {"id": "hadouken-e-rose", "expr": "all(hadouken == baseline.hadouken) and all(rose == baseline.rose)", "desc": "Hadouken e Rose intactos"},
        {"id": "logica-igual", "expr": "all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)", "desc": "a luta transcorre igual (só muda cor)"}
      ]
    },
    {
      "id": "selecao-e-vs",
      "desc": "cursor passa por Ryu, Adon, Chun-Li, Guy até o Ken; seleciona com Y até a tela KEN VS ROSE",
      "state": "selecao",
      "input": "selecao_vs.txt",
      "frames": 1100,
      "capture": {"every": 10},
      "watch": ["ret1=cgram:00CA:2", "ret2=cgram:00CC:2", "ret3=cgram:00CE:2", "ret4=cgram:00D0:2", "retpele=cgram:00D2:2",
                "spr1=cgram:01D2:2", "vs1=cgram:010A:2", "vs2=cgram:010C:2", "vs3=cgram:010E:2", "vs4=cgram:0110:2"],
      "checks": [
        {"id": "retrato-azul", "expr": "all((baseline.ret1 != 0x113E) | ((ret1 == 0x7E06) & (ret2 == 0x7102) & (ret3 == 0x5881) & (ret4 == 0x3C20)))", "desc": "retrato da seleção com gi azul"},
        {"id": "outros-retratos-iguais", "expr": "all((baseline.ret1 == 0x113E) | (ret1 == baseline.ret1))", "desc": "Ryu, Adon, Chun-Li e Guy iguais ao original"},
        {"id": "vs-azul", "expr": "all((baseline.vs1 != 0x113E) | ((vs1 == 0x7E06) & (vs2 == 0x7102) & (vs3 == 0x5881) & (vs4 == 0x3C20)))", "desc": "retrato da tela VS com gi azul"},
        {"id": "sprite-selecao-azul", "expr": "all((baseline.spr1 != 0x011E) | (spr1 == 0x7E06))", "desc": "o sprite pequeno da seleção também"},
        {"id": "retratos-na-tela", "expr": "count(baseline.ret1 == 0x113E) >= 20 and count(baseline.vs1 == 0x113E) >= 20", "desc": "sanidade: o Ken aparece na seleção e na VS (ajuste os números ao 1.º baseline)"},
        {"id": "pele-retrato", "expr": "all(retpele == baseline.retpele)", "desc": "a pele do retrato não muda"}
      ]
    },
    {
      "id": "regressao-chute",
      "desc": "regressão: Ken escolhido com chute (gi roxo) na mesma luta — nada pode mudar",
      "state": "luta-ken-chute-fight",
      "input": "luta.txt",
      "frames": 600,
      "capture": {"every": 4},
      "watch": ["gi1=cgram:01D2:2", "gi2=cgram:01D4:2", "gi3=cgram:01D6:2", "gi4=cgram:01D8:2", "gi5=cgram:01DA:2",
                "pele=cgram:01C8:2", "rose=cgram:01F2:2", "hadouken=cgram:0104:2",
                "x1=7E:0709:2", "hp1=7E:073E", "hp2=7E:09BE"],
      "checks": [
        {"id": "roxo-na-tela", "expr": "count(baseline.gi1 == 0x5910) >= 0.8 * len(gi1)", "desc": "sanidade: é mesmo o uniforme roxo (cor 1)"},
        {"id": "roxo-igual", "expr": "all(gi1 == baseline.gi1) and all(gi2 == baseline.gi2) and all(gi3 == baseline.gi3) and all(gi4 == baseline.gi4) and all(gi5 == baseline.gi5)", "desc": "a paleta roxa (vizinha na ROM) fica intacta"},
        {"id": "resto-igual", "expr": "all(pele == baseline.pele) and all(rose == baseline.rose) and all(hadouken == baseline.hadouken)", "desc": "nada mais muda"},
        {"id": "logica-igual", "expr": "all(x1 == baseline.x1) and all(hp1 == baseline.hp1) and all(hp2 == baseline.hp2)", "desc": "a luta transcorre igual"}
      ]
    }
  ]
}
```
Obs.: `"data"` depende do passo 1 de **Como continuar** (regiões de dados no `build.py`). Sem ele o build
funciona, mas relata as paletas como "hijack" e o ciclo põe sondas `exec` inúteis nelas.
`"gi1": 0x5910` na regressão = 1.º tom do gi roxo (cor 1, `0x1F0292`) — confira no baseline.

## `luta.txt`
```
# Ken (P1) faz de tudo um pouco para mostrar muitos quadros do sprite (Y=LP X=MP L=HP B=LK A=MK R=HK)
40 Right
10
4 Down
4 Down+Right
4 Right
1 Right+Y        # Hadouken fraco
50
4 Down
4 Down+Right
4 Right
1 Right+X        # Hadouken médio
60
30 Right
1 Up+Right
20
1 A              # chute no ar
40
4 Right
4 Down
4 Down+Right
1 Down+Right+L   # Shoryuken forte
80
20 Down
1 Down+Y
15
1 Down+B
30
1 X
30
1 A
60
```

## `selecao_vs.txt`
```
# do state `selecao`: cursor até o Ken, Y (cor 0) → MANUAL (Y) → SPEED (Y) → mapa → KEN VS ROSE
10
1 Right
20
1 Right
20
1 Right
20
1 Right
40
1 Y
100
1 Y
100
1 Y
784
```
