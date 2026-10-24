# Análise visual: vídeos, frames e veredito

O agente não "assiste" vídeo: o pipeline transforma vídeo em imagens que se leem com a ferramenta
Read (folhas de contato, frames individuais, gráficos). Imagens até ~1100 px de largura leem bem.

## Fontes de imagem
1. **Runs headless** (`fab run`, `fab cycle run`): captura direta do framebuffer do MesenCE, sem perda,
   256x224 (corte de overscan igual ao Mesen: linhas 7..230 do buffer 256x239). Frame N mostra a
   lógica do frame N-1 (a OAM é enviada no NMI) — atraso constante de 1 frame; RAM e imagem
   ficam alinhadas porque o frame skipping está desligado (`Snes.DisableFrameSkipping`).
2. **Gravações do usuário** (`media/inbox/` → `fab media inbox` ou `fab media analyze`): MP4/MKV/WEBM/
   MOV/GIF ou pasta de PNG/JPG. Saem: `sheet_uniform.png` (N frames igualmente espaçados),
   `sheet_scenes_*.png` (cortes de cena, marcados com ✂), `motion.png` (picos = ação) e
   `frames/t<ms>.png`. Use `--at 12.5,13.0` para extrair instantes específicos.

## Como olhar (ordem)
1. `compare.png` do ciclo: linhas = frames; colunas = baseline · mod · diferença (magenta = pixels
   que mudaram). A primeira linha com magenta deve coincidir com o momento em que o mod deveria agir
   (ex.: 1 frame depois do botão). Magenta ANTES disso = efeito colateral.
2. `trace_compare.png`: RAM mod (vermelho) × baseline (cinza) + linha de input. Confirma a mecânica.
3. `divergence.png`: % de pixels diferentes por frame — picos isolados vs. divergência sustentada.
4. Na dúvida, abra frames individuais: `runs/<run>/frames/fNNNNN.png` (baseline e mod, mesmo N).
5. Para gravações do usuário: comece pela folha uniforme, depois os cortes de cena e `motion.png`
   para achar o instante; extraia instantes com `--at`.

## Checklist do veredito visual
- O efeito pedido aparece, no momento certo, com a intensidade esperada? (descreva frames/pixels)
- Nada a mais mudou? (HUD, paleta, sprites errados, tela preta, tremor, "lixo" gráfico, travamento —
  frames idênticos no fim de um cenário que deveria mover = possível softlock)
- O cenário de regressão continua idêntico (0 frames divergentes)?
- Melhor, pior ou igual ao ciclo anterior? (`fab cycle status`)
Registre: `fab cycle verdict mods/<id> --cycle N <veredito> --notes "f40: …; f78: …"`.

## Armadilhas
- Gravações de celular: perspectiva/moiré/brilho — compare formas e posições relativas, não cores exatas.
- Vídeos com frame rate diferente de 60 fps: use os timestamps, não os índices de frame.
- Jogos com hi-res/entrelaçado (512 px / 478 linhas): as folhas normalizam o tamanho por vizinho mais próximo.
- Efeitos de 1 frame (flash) podem cair entre capturas: use `capture.every: 1` no cenário.
