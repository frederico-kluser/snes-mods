"""snesfab — fábrica de mods de SNES.

ROM → análise (dinâmica no MesenCE + estática no Ghidra/ghidra-snes) → patch Asar →
emulação headless a partir de savestate → vídeo/frames/traços de RAM → veredito de evolução.
"""

__version__ = "0.1.0"  # x-release-please-version

# Sobe quando o protocolo job.lua ↔ harness.lua ou a semântica de captura muda
# (invalida o cache de baselines). v2: DisableFrameSkipping → frames alinhados com a RAM.
HARNESS_VERSION = 2
