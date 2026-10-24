"""Fuzzing dos patches BPS (snesfab/bps.py): quem aplica um mod baixado entrega bytes não confiáveis.

Entrada: o 1.º byte escolhe o modo; o resto é o material.
  0 → ida e volta: apply(src, create(src, tgt)) == tgt, com src/tgt cortados do material
  1 → ações arbitrárias num patch com cabeçalho e CRCs válidos (chega ao laço de comandos)
  2 → patch cru ("BPS1" + material + CRC do patch): tamanhos, metadados e CRCs também variam
Contrato: apply() devolve bytes ou levanta FabError — nunca outra exceção, nunca trava.
"""

import zlib

import fuzzlib

with fuzzlib.instrumented():
    from snesfab import bps
    from snesfab.util import FabError

SOURCE = bytes(range(256)) * 4  # "ROM" de 1 KiB


def _crc(data: bytes) -> bytes:
    return (zlib.crc32(data) & 0xFFFFFFFF).to_bytes(4, "little")


def TestOneInput(data: bytes) -> None:
    if len(data) < 2:
        return
    mode, body = data[0] % 3, data[1:]
    if mode == 0:
        cut = body[0] * (len(body) - 1) // 255
        src, tgt = body[1:1 + cut], body[1 + cut:]
        assert bps.apply(src, bps.create(src, tgt, "fuzz")) == tgt
        return
    if mode == 1:
        size = int.from_bytes(body[:2], "little")
        patch = b"BPS1" + bps._enc(len(SOURCE)) + bps._enc(size) + bps._enc(0) + body[2:]
        patch += _crc(SOURCE) + _crc(b"")
    else:
        patch = b"BPS1" + body
    patch += _crc(patch)
    try:
        out = bps.apply(SOURCE, patch)
    except FabError:
        return
    assert isinstance(out, bytes)


if __name__ == "__main__":
    fuzzlib.main(TestOneInput)
