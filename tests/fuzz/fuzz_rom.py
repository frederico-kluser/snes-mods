"""Fuzzing do leitor de ROM e da conversão de endereços (snesfab/rom.py): a ROM é sempre arquivo de fora.

Entrada: o 1.º byte escolhe o caso.
  bit 7 ligado → parse_addr() sobre o resto (texto); o endereço volta igual por fmt_addr()
  senão → ROM sintética: bits 0-1 = tamanho, bit 2 = cabeçalho SMC; os 80 bytes seguintes vão para
          os três lugares de cabeçalho interno ($FFB0 de LoROM/HiROM/ExHiROM) e o resto para o código
Contrato: parse_rom() devolve a imagem ou levanta FabError; pc → endereço SNES → pc é a identidade em
todo o espaço que o mapa cobre (é o que garante que o patch cai no byte certo).
"""

import fuzzlib

with fuzzlib.instrumented():
    from snesfab import rom
    from snesfab.util import FabError

SIZES = (0x8000, 0x10000, 0x40000, 0x410000)
MAP_LIMIT = {"lorom": 0x400000, "hirom": 0x400000, "exhirom": 0x800000, "sa1": 0x400000, "sdd1": 0x400000}


def _addr_case(text: str) -> None:
    try:
        addr = rom.parse_addr(text)
    except FabError:
        return
    assert 0 <= addr <= 0xFFFFFF
    assert rom.parse_addr(rom.fmt_addr(addr)) == addr
    rom.wram_offset(addr)
    rom.is_mmio(addr)


def _round_trip(img, pc: int) -> None:
    snes = img.to_snes(pc)
    assert img.to_pc(snes) == pc, (img.mapping, hex(pc), hex(snes))


def TestOneInput(data: bytes) -> None:
    if len(data) < 2:
        return
    if data[0] & 0x80:
        _addr_case(data[1:].decode("latin-1"))
        return
    size, smc = SIZES[data[0] & 3], 0x200 if data[0] & 4 else 0
    head, code = data[1:81], data[81:]
    raw = bytearray(smc + size)
    for off in (0x7FB0, 0xFFB0, 0x40FFB0):
        if off + len(head) <= size:
            raw[smc + off:smc + off + len(head)] = head
    for off in (0x0000, 0x8000):
        chunk = code[:max(0, min(len(code), size - off, 0x7FB0))]
        raw[smc + off:smc + off + len(chunk)] = chunk
    try:
        img = rom.parse_rom(bytes(raw))
    except FabError:
        return
    img.header.describe()
    img.checksum_info()
    img.hashes()
    limit = min(len(img.data), MAP_LIMIT[img.mapping])
    for pc in {0, limit - 1, int.from_bytes(head[:3], "little") % limit}:
        _round_trip(img, pc)
    for vec in img.header.vectors.values():
        try:
            pc = img.to_pc(vec)
        except FabError:
            continue
        assert 0 <= pc < len(img.data)
        _round_trip(img, pc)


if __name__ == "__main__":
    fuzzlib.main(TestOneInput)
