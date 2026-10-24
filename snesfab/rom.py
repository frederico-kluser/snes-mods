"""Imagens de ROM de SNES: cabeçalho SMC, detecção LoROM/HiROM/ExHiROM, cabeçalho interno,
checksum e conversão de endereços (CPU de 24 bits ↔ offset no arquivo sem cabeçalho)."""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from .util import FabError, sha1_bytes, sha256_bytes

SMC_HEADER = 0x200

# Offsets (no arquivo limpo) do início do cabeçalho interno ($xx:FFC0) para cada mapa.
HEADER_CANDIDATES = {"lorom": 0x7FC0, "hirom": 0xFFC0, "exhirom": 0x40FFC0}

MAP_MODE_NAMES = {
    0x20: "LoROM", 0x21: "HiROM", 0x22: "LoROM+S-DD1", 0x23: "LoROM+SA-1", 0x25: "ExHiROM",
    0x2A: "HiROM+SPC7110", 0x30: "LoROM FastROM", 0x31: "HiROM FastROM", 0x32: "LoROM+S-DD1 FastROM",
    0x35: "ExHiROM FastROM", 0x3A: "HiROM+SPC7110 FastROM",
}

CHIPSETS = {
    0x00: "ROM", 0x01: "ROM+RAM", 0x02: "ROM+RAM+bateria",
    0x03: "ROM+DSP", 0x04: "ROM+DSP+RAM", 0x05: "ROM+DSP+RAM+bateria",
    0x13: "ROM+SuperFX", 0x14: "ROM+SuperFX+RAM", 0x15: "ROM+SuperFX+RAM+bateria", 0x1A: "ROM+SuperFX+RAM+bateria",
    0x25: "ROM+OBC1+RAM+bateria",
    0x33: "ROM+SA-1", 0x34: "ROM+SA-1+RAM", 0x35: "ROM+SA-1+RAM+bateria",
    0x43: "ROM+S-DD1", 0x45: "ROM+S-DD1+RAM+bateria",
    0x55: "ROM+RTC+RAM+bateria", 0xE3: "ROM+Super Game Boy", 0xE5: "ROM+Satellaview",
    0xF5: "ROM+custom(SPC7110/ST018)+RAM+bateria", 0xF6: "ROM+custom(ST010/ST011)+RAM+bateria",
    0xF9: "ROM+SPC7110+RTC+RAM+bateria",
}

REGIONS = {
    0x00: "Japão", 0x01: "América do Norte", 0x02: "Europa", 0x03: "Suécia/Escandinávia", 0x04: "Finlândia",
    0x05: "Dinamarca", 0x06: "França", 0x07: "Holanda", 0x08: "Espanha", 0x09: "Alemanha", 0x0A: "Itália",
    0x0B: "China", 0x0C: "Indonésia", 0x0D: "Coreia", 0x0E: "Internacional", 0x0F: "Canadá",
    0x10: "Brasil", 0x11: "Austrália",
}

VECTORS = {
    # nome: endereço em $00:FFxx (o valor guardado é um ponteiro de 16 bits para o banco $00)
    "native_cop": 0xFFE4, "native_brk": 0xFFE6, "native_abort": 0xFFE8, "native_nmi": 0xFFEA,
    "native_irq": 0xFFEE, "emu_cop": 0xFFF4, "emu_abort": 0xFFF8, "emu_nmi": 0xFFFA,
    "emu_reset": 0xFFFC, "emu_irqbrk": 0xFFFE,
}


def parse_addr(text: str | int) -> int:
    """Aceita 80:A412, $80A412, 0x80A412, 80A412, 7E:007D ou int. Devolve o endereço de 24 bits."""
    if isinstance(text, int):
        return text & 0xFFFFFF
    s = str(text).strip().replace("_", "")
    m = re.fullmatch(r"\$?([0-9A-Fa-f]{1,2}):\$?([0-9A-Fa-f]{1,4})", s)
    if m:
        return (int(m.group(1), 16) << 16) | int(m.group(2), 16)
    s = s.lstrip("$")
    if s.lower().startswith("0x"):
        s = s[2:]
    if not re.fullmatch(r"[0-9A-Fa-f]{1,6}", s):
        raise FabError(f"endereço inválido: {text!r}", "use BB:AAAA (ex.: 80:A412) ou $BBAAAA")
    return int(s, 16)


def fmt_addr(addr: int) -> str:
    return f"{(addr >> 16) & 0xFF:02X}:{addr & 0xFFFF:04X}"


def wram_offset(addr: int) -> int | None:
    """Offset na WRAM (0..0x1FFFF) para um endereço de CPU, ou None se não for WRAM.
    Cobre $7E-$7F:0000-FFFF e os espelhos baixos $00-$3F/$80-$BF:0000-1FFF."""
    bank, off = (addr >> 16) & 0xFF, addr & 0xFFFF
    if bank in (0x7E, 0x7F):
        return ((bank - 0x7E) << 16) | off
    if (bank <= 0x3F or 0x80 <= bank <= 0xBF) and off < 0x2000:
        return off
    return None


def is_mmio(addr: int) -> bool:
    bank, off = (addr >> 16) & 0xFF, addr & 0xFFFF
    return (bank <= 0x3F or 0x80 <= bank <= 0xBF) and 0x2100 <= off <= 0x5FFF


def snes_checksum(data: bytes) -> int:
    """Checksum interno do SNES: soma de bytes mod 0x10000, espelhando a parte não potência de 2."""
    size = len(data)
    if size == 0:
        return 0
    base = 1 << (size.bit_length() - 1)
    if base == size:
        return sum(data) & 0xFFFF
    total = sum(data[:base])
    rest = data[base:]
    rest_len = len(rest)
    # a parte restante é espelhada até completar outro bloco de `base` bytes
    reps = base // rest_len if rest_len else 0
    total += sum(rest) * reps
    return total & 0xFFFF


@dataclass
class Header:
    offset: int
    map_name: str
    title: str
    map_mode: int
    chipset: int
    rom_size_kb: int
    sram_size_kb: int
    region: int
    dev_id: int
    version: int
    checksum_complement: int
    checksum: int
    vectors: dict = field(default_factory=dict)
    score: int = 0
    extended: dict = field(default_factory=dict)

    @property
    def fastrom(self) -> bool:
        return bool(self.map_mode & 0x10)

    def describe(self) -> dict:
        return {
            "title": self.title,
            "map": self.map_name,
            "map_mode": f"${self.map_mode:02X} ({MAP_MODE_NAMES.get(self.map_mode, 'desconhecido')})",
            "fastrom": self.fastrom,
            "chipset": f"${self.chipset:02X} ({CHIPSETS.get(self.chipset, 'desconhecido')})",
            "rom_size_kb": self.rom_size_kb,
            "sram_size_kb": self.sram_size_kb,
            "region": f"${self.region:02X} ({REGIONS.get(self.region, '?')})",
            "dev_id": f"${self.dev_id:02X}",
            "version": f"1.{self.version}",
            "checksum": f"${self.checksum:04X}",
            "checksum_complement": f"${self.checksum_complement:04X}",
            "vectors": {k: f"00:{v:04X}" for k, v in self.vectors.items()},
            "extended": self.extended,
            "header_offset": f"0x{self.offset:06X}",
            "detection_score": self.score,
        }


def _read_header(data: bytes, offset: int, map_name: str) -> Header | None:
    if offset + 0x40 > len(data):
        return None
    h = data[offset:offset + 0x40]
    title_raw = h[0:21]
    title = "".join(chr(b) if 0x20 <= b < 0x7F else "·" for b in title_raw).rstrip()
    vec = {}
    for name, vaddr in VECTORS.items():
        o = offset + (vaddr - 0xFFC0)
        vec[name] = data[o] | (data[o + 1] << 8)
    hdr = Header(
        offset=offset, map_name=map_name, title=title, map_mode=h[0x15], chipset=h[0x16],
        rom_size_kb=(1 << h[0x17]) if h[0x17] < 16 else 0,
        sram_size_kb=(1 << h[0x18]) if 0 < h[0x18] < 16 else 0,
        region=h[0x19], dev_id=h[0x1A], version=h[0x1B],
        checksum_complement=h[0x1C] | (h[0x1D] << 8), checksum=h[0x1E] | (h[0x1F] << 8),
        vectors=vec,
    )
    if hdr.dev_id == 0x33 and offset >= 0x10:
        e = data[offset - 0x10:offset]
        hdr.extended = {
            "maker_code": "".join(chr(b) if 0x20 <= b < 0x7F else "·" for b in e[0:2]),
            "game_code": "".join(chr(b) if 0x20 <= b < 0x7F else "·" for b in e[2:6]),
            "expansion_ram_kb": (1 << e[0x0D]) if 0 < e[0x0D] < 16 else 0,
            "special_version": e[0x0E], "cart_subtype": e[0x0F],
        }
    return hdr


def _score(data: bytes, hdr: Header) -> int:
    score = 0
    if (hdr.checksum ^ hdr.checksum_complement) == 0xFFFF:
        score += 3
    low = hdr.map_mode & 0x0F
    expected = {"lorom": {0x0, 0x2, 0x3}, "hirom": {0x1, 0xA}, "exhirom": {0x5, 0xA}}[hdr.map_name]
    if (hdr.map_mode & 0xE0) == 0x20 and low in expected:
        score += 2
    reset = hdr.vectors["emu_reset"]
    if reset >= 0x8000:
        score += 1
        # opcode típico de arranque no destino do reset
        try:
            pc = snes_to_pc(reset, hdr.map_name, len(data))
            if data[pc] in (0x78, 0x18, 0x5C, 0xC2, 0xE2, 0x9C, 0x4B, 0xA9, 0xAD, 0x8B, 0x20, 0x22, 0xDC, 0x80):
                score += 1
        except FabError:
            pass
    printable = sum(1 for c in hdr.title if c != "·")
    if printable >= 12:
        score += 1
    if hdr.rom_size_kb and (len(data) // 2048) <= hdr.rom_size_kb <= (len(data) // 512):
        score += 1
    return score


def snes_to_pc(addr: int, mapping: str, rom_size: int | None = None) -> int:
    """Endereço de CPU → offset no arquivo sem cabeçalho. Levanta FabError se não for ROM."""
    bank, off = (addr >> 16) & 0xFF, addr & 0xFFFF
    if bank in (0x7E, 0x7F):
        raise FabError(f"{fmt_addr(addr)} é WRAM, não ROM")
    if mapping == "sa1":
        # MMC padrão do SA-1 (o `sa1rom` do Asar): blocos de 1 MiB C/D/E/F = 0/1/2/3, vistos em
        # $00-$1F/$20-$3F/$80-$9F/$A0-$BF:8000-FFFF (LoROM) e em $C0-$FF (HiROM). $80+ NÃO espelha $00+.
        if bank >= 0xC0:
            pc = ((bank & 0x3F) << 16) | off
        elif off >= 0x8000 and (bank <= 0x3F or 0x80 <= bank <= 0xBF):
            pc = (0x200000 if bank >= 0x80 else 0) | ((bank & 0x3F) << 15) | (off - 0x8000)
        else:
            raise FabError(f"{fmt_addr(addr)} não mapeia ROM em SA-1")
    elif mapping in ("lorom", "sdd1"):
        if off >= 0x8000:
            pc = ((bank & 0x7F) << 15) | (off - 0x8000)
        elif 0x40 <= (bank & 0x7F) <= 0x7D and rom_size and rom_size > 0x200000:
            pc = ((bank & 0x7F) << 15) | off  # LoROM grandes espelham a metade baixa
        else:
            raise FabError(f"{fmt_addr(addr)} não mapeia ROM em LoROM (metade baixa = RAM/MMIO)")
    elif mapping == "hirom":
        if bank >= 0xC0 or 0x40 <= bank <= 0x7D:
            pc = ((bank & 0x3F) << 16) | off
        elif off >= 0x8000:
            pc = ((bank & 0x3F) << 16) | off
        else:
            raise FabError(f"{fmt_addr(addr)} não mapeia ROM em HiROM")
    elif mapping == "exhirom":
        if bank >= 0xC0:
            pc = ((bank & 0x3F) << 16) | off
        elif 0x40 <= bank <= 0x7D:
            pc = 0x400000 | ((bank & 0x3F) << 16) | off
        elif off >= 0x8000:
            pc = (0 if bank >= 0x80 else 0x400000) | ((bank & 0x3F) << 16) | off
        else:
            raise FabError(f"{fmt_addr(addr)} não mapeia ROM em ExHiROM")
    else:
        raise FabError(f"mapa desconhecido: {mapping}")
    if rom_size is not None and pc >= rom_size:
        raise FabError(f"{fmt_addr(addr)} → 0x{pc:X} está fora da ROM (0x{rom_size:X} bytes)")
    return pc


def pc_to_snes(pc: int, mapping: str, fast: bool = True) -> int:
    """Offset no arquivo → endereço de CPU canônico (FastROM $80+ para LoROM, $C0+ para HiROM; SA-1 como o
    Asar: $00-$3F para os 2 primeiros MiB, $80-$BF para os 2 seguintes). Fora do que o mapa cobre: FabError."""
    if mapping not in ("lorom", "sa1", "sdd1", "hirom", "exhirom"):
        raise FabError(f"mapa desconhecido: {mapping}")
    limit = 0x800000 if mapping == "exhirom" else 0x400000
    if not 0 <= pc < limit:
        raise FabError(f"0x{pc:X} está fora dos {limit >> 20} MiB que o mapa {mapping} cobre")
    if mapping == "sa1":
        bank = (0x80 if pc >= 0x200000 else 0) | ((pc >> 15) & 0x3F)
        return (bank << 16) | 0x8000 | (pc & 0x7FFF)
    if mapping in ("lorom", "sdd1"):
        bank = (pc >> 15) & 0x7F
        return ((bank | (0x80 if fast else 0)) << 16) | (0x8000 + (pc & 0x7FFF))
    if mapping == "hirom" or pc < 0x400000:
        return ((0xC0 | ((pc >> 16) & 0x3F)) << 16) | (pc & 0xFFFF)
    bank = 0x40 | ((pc >> 16) & 0x3F)                    # ExHiROM, 2.º bloco de 4 MiB
    if bank >= 0x7E:                                     # $7E-$7F são WRAM: só a metade alta, por $3E-$3F
        if pc & 0xFFFF < 0x8000:
            raise FabError(f"0x{pc:X} não tem endereço de CPU em ExHiROM (metade baixa de $3E-$3F)")
        bank &= 0x3F
    return (bank << 16) | (pc & 0xFFFF)


@dataclass
class RomImage:
    path: Path
    raw: bytes
    data: bytes
    had_smc_header: bool
    header: Header
    candidates: list[dict]

    @property
    def mapping(self) -> str:
        if self.header.map_mode & 0x0F == 0x3 and self.header.map_name == "lorom":
            return "sa1"
        if self.header.map_mode & 0x0F == 0x2 and self.header.map_name == "lorom":
            return "sdd1"
        return self.header.map_name

    def to_pc(self, addr: int) -> int:
        return snes_to_pc(addr, self.mapping, len(self.data))

    def to_snes(self, pc: int) -> int:
        return pc_to_snes(pc, self.mapping, fast=True)

    def read(self, addr: int, n: int) -> bytes:
        pc = self.to_pc(addr)
        return self.data[pc:pc + n]

    def checksum_info(self) -> dict:
        calc = snes_checksum(self.data)
        return {"stored": f"${self.header.checksum:04X}", "computed": f"${calc:04X}",
                "valid": calc == self.header.checksum and (self.header.checksum ^ self.header.checksum_complement) == 0xFFFF}

    def hashes(self) -> dict:
        return {
            "raw_sha256": sha256_bytes(self.raw), "clean_sha256": sha256_bytes(self.data),
            "clean_sha1": sha1_bytes(self.data), "clean_crc32": f"{zlib.crc32(self.data) & 0xFFFFFFFF:08x}",
        }


def load_rom(path: Path | str) -> RomImage:
    path = Path(path)
    if not path.is_file():
        raise FabError(f"ROM não encontrada: {path}", "confirme o caminho")
    return parse_rom(path.read_bytes(), path)


def parse_rom(raw: bytes, path: Path | str = "<memória>") -> RomImage:
    """Cabeçalho SMC, mapa e cabeçalho interno de uma ROM já lida (o arquivo é entrada não confiável)."""
    if len(raw) < 0x8000:
        raise FabError(f"arquivo demasiado pequeno para ser ROM de SNES ({len(raw)} bytes)")
    had_smc = len(raw) % 1024 == SMC_HEADER
    data = raw[SMC_HEADER:] if had_smc else raw
    best, cands = None, []
    for name, off in HEADER_CANDIDATES.items():
        hdr = _read_header(data, off, name)
        if hdr is None:
            continue
        hdr.score = _score(data, hdr)
        cands.append({"map": name, "offset": f"0x{off:06X}", "score": hdr.score, "title": hdr.title})
        if best is None or hdr.score > best.score:
            best = hdr
    if best is None:
        raise FabError("não encontrei cabeçalho interno de SNES", "a ROM pode estar corrompida ou intercalada")
    return RomImage(path=Path(path), raw=raw, data=data, had_smc_header=had_smc, header=best, candidates=cands)
