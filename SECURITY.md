# Política de segurança

Segurança importa no **snes-mods** (`frederico-kluser/snes-mods`): a ferramenta baixa e executa
toolchains, roda um emulador com scripts Lua e processa arquivos não confiáveis (ROMs, savestates,
vídeos). Obrigado por ajudar a mantê-la segura.

## Versões suportadas

Só a linha mais recente (`main` / última release) recebe correções de segurança.

| Versão | Suportada |
| --- | --- |
| Última release (`main`) | :white_check_mark: |
| Anteriores | :x: |

## Como reportar uma vulnerabilidade

**Não abra issue, discussão nem PR públicos para vulnerabilidades.**

Use o **Private Vulnerability Reporting** do GitHub:
aba **Security** → **Advisories** → **Report a vulnerability**
(<https://github.com/frederico-kluser/snes-mods/security/advisories/new>).

Inclua, se possível: descrição e impacto, passos de reprodução ou prova de conceito, commit/versão
afetados e uma sugestão de correção. Não anexe ROMs comerciais (use `fixtures/testbed/` para
reproduzir).

### Prazos

| Etapa | Meta |
| --- | --- |
| Confirmação de recebimento | **48 horas** |
| Triagem e severidade inicial | **3 dias úteis** |
| Atualizações de status | a cada **7 dias** |
| Correção de achados críticos | **30 dias** |
| Correção dos demais | **90 dias** |

## Divulgação coordenada

Mantenha o achado confidencial até a correção sair e o advisory ser publicado. Combinamos a data de
divulgação, damos crédito no advisory (salvo se preferir anonimato) e avisamos quando a correção for
publicada. Embargo máximo de 90 dias a partir da confirmação.

## Escopo

Dentro do escopo:

- O código deste repositório: CLI `fab` (`snesfab/`), `lua/harness.lua`, `ghidra_scripts/`,
  wrappers (`fab`, `fab.cmd`, `fab.ps1`) e os workflows de `.github/`.
- O processo de instalação do `fab setup` — por exemplo, um artefato do `tools/manifest.json` cujo
  sha256 deixasse de ser verificado ou que fosse substituído na origem.

Fora do escopo (reporte ao projeto de origem):

- Vulnerabilidades no MesenCE, Ghidra, ghidra-snes, Asar, ffmpeg, Temurin JDK ou REA.
- Problemas que só afetem versões não suportadas.

## Avisos importantes para quem usa

- O harness do emulador precisa de **I/O liberado no Lua** (`AllowIoOsAccess` no `settings.json`
  portátil do MesenCE, configurado pelo `fab setup`). Rode apenas scripts Lua em que você confia.
- ROMs, savestates e vídeos de terceiros são entradas não confiáveis processadas por emuladores e
  decodificadores; use arquivos de origem conhecida.
- O `.mcp.json` gerado localmente registra o servidor MCP do REA com caminhos da sua máquina; ele
  fica fora do git.

## Proteções do repositório

- Secret scanning e **push protection** ativos.
- **Dependabot** (pip, npm e GitHub Actions) e revisão de dependências nos PRs.
- **Rulesets** na `main`: PR obrigatório, squash-only, histórico linear, sem force-push e sem
  delete, status check `build` obrigatório; nomes de branch `<tipo>/<slug>`; tags `v*` imutáveis.
- **CodeQL** (Python) e **OpenSSF Scorecard** com resultados publicados.
- Actions fixadas por **SHA** e `permissions` mínimas em todos os workflows.

## Contato

Segurança: o canal privado acima. Dúvidas gerais: issues ou Discussions do repositório.
