"""Patches BPS (formato beat/Flips) — distribuir o mod sem distribuir a ROM.

Codificação linear simples (SourceRead/TargetRead), válida em qualquer aplicador BPS.
"""

from __future__ import annotations

import zlib

from .util import FabError


def _enc(n: int) -> bytes:
    out = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return bytes(out)
        out.append(x)
        n -= 1


def _dec(buf: bytes, pos: int) -> tuple[int, int]:
    data, shift = 0, 1
    while True:
        x = buf[pos]
        pos += 1
        data += (x & 0x7F) * shift
        if x & 0x80:
            return data, pos
        shift <<= 7
        data += shift


def create(source: bytes, target: bytes, metadata: str = "") -> bytes:
    out = bytearray(b"BPS1")
    meta = metadata.encode("utf-8")
    out += _enc(len(source)) + _enc(len(target)) + _enc(len(meta)) + meta
    i, n = 0, len(target)
    while i < n:
        same = i < len(source) and source[i] == target[i]
        j = i
        if same:
            while j < n and j < len(source) and source[j] == target[j]:
                j += 1
            out += _enc(((j - i - 1) << 2) | 0)          # SourceRead
        else:
            while j < n and not (j < len(source) and source[j] == target[j]
                                 and j + 1 < n and j + 1 < len(source) and source[j + 1] == target[j + 1]):
                j += 1
            out += _enc(((j - i - 1) << 2) | 1)          # TargetRead
            out += target[i:j]
        i = j
    out += (zlib.crc32(source) & 0xFFFFFFFF).to_bytes(4, "little")
    out += (zlib.crc32(target) & 0xFFFFFFFF).to_bytes(4, "little")
    out += (zlib.crc32(bytes(out)) & 0xFFFFFFFF).to_bytes(4, "little")
    return bytes(out)


def apply(source: bytes, patch: bytes) -> bytes:
    if patch[:4] != b"BPS1":
        raise FabError("não é um patch BPS")
    if (zlib.crc32(patch[:-4]) & 0xFFFFFFFF) != int.from_bytes(patch[-4:], "little"):
        raise FabError("BPS corrompido (crc do patch)")
    pos = 4
    src_size, pos = _dec(patch, pos)
    tgt_size, pos = _dec(patch, pos)
    meta_size, pos = _dec(patch, pos)
    pos += meta_size
    if len(source) != src_size or (zlib.crc32(source) & 0xFFFFFFFF) != int.from_bytes(patch[-12:-8], "little"):
        raise FabError("a ROM de origem não corresponde a este BPS (tamanho/crc)")
    out = bytearray(tgt_size)
    o = src_rel = tgt_rel = 0
    end = len(patch) - 12
    while pos < end:
        v, pos = _dec(patch, pos)
        cmd, length = v & 3, (v >> 2) + 1
        if cmd == 0:
            out[o:o + length] = source[o:o + length]
        elif cmd == 1:
            out[o:o + length] = patch[pos:pos + length]
            pos += length
        elif cmd == 2:
            d, pos = _dec(patch, pos)
            src_rel += (-1 if d & 1 else 1) * (d >> 1)
            out[o:o + length] = source[src_rel:src_rel + length]
            src_rel += length
        else:
            d, pos = _dec(patch, pos)
            tgt_rel += (-1 if d & 1 else 1) * (d >> 1)
            for k in range(length):
                out[o + k] = out[tgt_rel + k]
            tgt_rel += length
        o += length
    if (zlib.crc32(out) & 0xFFFFFFFF) != int.from_bytes(patch[-8:-4], "little"):
        raise FabError("resultado do BPS não confere (crc do alvo)")
    return bytes(out)
