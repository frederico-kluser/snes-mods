"""Desmontador linear do WDC 65C816 com rastreio das flags M/X (SEP/REP).

Usado para: olhar rotinas rapidamente, verificar a geometria de hijacks (JSL/JML de 4 bytes
sobre fronteiras de instrução) e reconstruir o PC de instruções de escrita a partir do PC
seguinte reportado pelo emulador. Não substitui o Ghidra: não segue fluxo, só desmonta em linha.
"""

from __future__ import annotations

from dataclasses import dataclass

# Modos de endereçamento → tamanho total da instrução (None = depende de M ou X)
MODE_SIZE = {
    "imp": 1, "acc": 1, "imm8": 2, "immM": None, "immX": None, "imm16": 3, "sig": 2,
    "dp": 2, "dpx": 2, "dpy": 2, "idp": 2, "idpx": 2, "idpy": 2, "ildp": 2, "ildpy": 2,
    "abs": 3, "absx": 3, "absy": 3, "long": 4, "longx": 4, "iabs": 3, "iabsx": 3, "ilabs": 3,
    "rel8": 2, "rel16": 3, "sr": 2, "isry": 2, "blk": 3,
}

_T = """
00 BRK sig   01 ORA idpx  02 COP sig   03 ORA sr    04 TSB dp    05 ORA dp    06 ASL dp    07 ORA ildp
08 PHP imp   09 ORA immM  0A ASL acc   0B PHD imp   0C TSB abs   0D ORA abs   0E ASL abs   0F ORA long
10 BPL rel8  11 ORA idpy  12 ORA idp   13 ORA isry  14 TRB dp    15 ORA dpx   16 ASL dpx   17 ORA ildpy
18 CLC imp   19 ORA absy  1A INC acc   1B TCS imp   1C TRB abs   1D ORA absx  1E ASL absx  1F ORA longx
20 JSR abs   21 AND idpx  22 JSL long  23 AND sr    24 BIT dp    25 AND dp    26 ROL dp    27 AND ildp
28 PLP imp   29 AND immM  2A ROL acc   2B PLD imp   2C BIT abs   2D AND abs   2E ROL abs   2F AND long
30 BMI rel8  31 AND idpy  32 AND idp   33 AND isry  34 BIT dpx   35 AND dpx   36 ROL dpx   37 AND ildpy
38 SEC imp   39 AND absy  3A DEC acc   3B TSC imp   3C BIT absx  3D AND absx  3E ROL absx  3F AND longx
40 RTI imp   41 EOR idpx  42 WDM imm8  43 EOR sr    44 MVP blk   45 EOR dp    46 LSR dp    47 EOR ildp
48 PHA imp   49 EOR immM  4A LSR acc   4B PHK imp   4C JMP abs   4D EOR abs   4E LSR abs   4F EOR long
50 BVC rel8  51 EOR idpy  52 EOR idp   53 EOR isry  54 MVN blk   55 EOR dpx   56 LSR dpx   57 EOR ildpy
58 CLI imp   59 EOR absy  5A PHY imp   5B TCD imp   5C JML long  5D EOR absx  5E LSR absx  5F EOR longx
60 RTS imp   61 ADC idpx  62 PER rel16 63 ADC sr    64 STZ dp    65 ADC dp    66 ROR dp    67 ADC ildp
68 PLA imp   69 ADC immM  6A ROR acc   6B RTL imp   6C JMP iabs  6D ADC abs   6E ROR abs   6F ADC long
70 BVS rel8  71 ADC idpy  72 ADC idp   73 ADC isry  74 STZ dpx   75 ADC dpx   76 ROR dpx   77 ADC ildpy
78 SEI imp   79 ADC absy  7A PLY imp   7B TDC imp   7C JMP iabsx 7D ADC absx  7E ROR absx  7F ADC longx
80 BRA rel8  81 STA idpx  82 BRL rel16 83 STA sr    84 STY dp    85 STA dp    86 STX dp    87 STA ildp
88 DEY imp   89 BIT immM  8A TXA imp   8B PHB imp   8C STY abs   8D STA abs   8E STX abs   8F STA long
90 BCC rel8  91 STA idpy  92 STA idp   93 STA isry  94 STY dpx   95 STA dpx   96 STX dpy   97 STA ildpy
98 TYA imp   99 STA absy  9A TXS imp   9B TXY imp   9C STZ abs   9D STA absx  9E STZ absx  9F STA longx
A0 LDY immX  A1 LDA idpx  A2 LDX immX  A3 LDA sr    A4 LDY dp    A5 LDA dp    A6 LDX dp    A7 LDA ildp
A8 TAY imp   A9 LDA immM  AA TAX imp   AB PLB imp   AC LDY abs   AD LDA abs   AE LDX abs   AF LDA long
B0 BCS rel8  B1 LDA idpy  B2 LDA idp   B3 LDA isry  B4 LDY dpx   B5 LDA dpx   B6 LDX dpy   B7 LDA ildpy
B8 CLV imp   B9 LDA absy  BA TSX imp   BB TYX imp   BC LDY absx  BD LDA absx  BE LDX absy  BF LDA longx
C0 CPY immX  C1 CMP idpx  C2 REP imm8  C3 CMP sr    C4 CPY dp    C5 CMP dp    C6 DEC dp    C7 CMP ildp
C8 INY imp   C9 CMP immM  CA DEX imp   CB WAI imp   CC CPY abs   CD CMP abs   CE DEC abs   CF CMP long
D0 BNE rel8  D1 CMP idpy  D2 CMP idp   D3 CMP isry  D4 PEI idp   D5 CMP dpx   D6 DEC dpx   D7 CMP ildpy
D8 CLD imp   D9 CMP absy  DA PHX imp   DB STP imp   DC JML ilabs DD CMP absx  DE DEC absx  DF CMP longx
E0 CPX immX  E1 SBC idpx  E2 SEP imm8  E3 SBC sr    E4 CPX dp    E5 SBC dp    E6 INC dp    E7 SBC ildp
E8 INX imp   E9 SBC immM  EA NOP imp   EB XBA imp   EC CPX abs   ED SBC abs   EE INC abs   EF SBC long
F0 BEQ rel8  F1 SBC idpy  F2 SBC idp   F3 SBC isry  F4 PEA imm16 F5 SBC dpx   F6 INC dpx   F7 SBC ildpy
F8 SED imp   F9 SBC absy  FA PLX imp   FB XCE imp   FC JSR iabsx FD SBC absx  FE INC absx  FF SBC longx
"""

OPCODES: dict[int, tuple[str, str]] = {}
_parts = _T.split()
for _i in range(0, len(_parts), 3):
    OPCODES[int(_parts[_i], 16)] = (_parts[_i + 1], _parts[_i + 2])
assert len(OPCODES) == 256

# Instruções que ESCREVEM em memória (excluindo pilha), por opcode.
_WRITE_MNEMONICS = {"STA", "STX", "STY", "STZ", "TSB", "TRB"}
_RMW_MNEMONICS = {"INC", "DEC", "ASL", "LSR", "ROL", "ROR"}
STACK_WRITERS = {"PHA", "PHX", "PHY", "PHP", "PHB", "PHD", "PHK", "PEA", "PEI", "PER", "JSR", "JSL", "BRK", "COP"}
BRANCHES = {"BPL", "BMI", "BVC", "BVS", "BCC", "BCS", "BNE", "BEQ", "BRA", "BRL"}
ENDS_FLOW = {"RTS", "RTL", "RTI", "JMP", "JML", "BRA", "BRL", "STP"}


def is_memory_write(op: int) -> bool:
    mn, mode = OPCODES[op]
    if mn in _WRITE_MNEMONICS:
        return True
    if mn in _RMW_MNEMONICS and mode != "acc":
        return True
    return mn in ("MVN", "MVP")


_READ_MNEMONICS = {"LDA", "LDX", "LDY", "ADC", "SBC", "AND", "ORA", "EOR", "CMP", "CPX", "CPY", "BIT", "PEI"}
_MEM_MODES = {"dp", "dpx", "dpy", "idp", "idpx", "idpy", "ildp", "ildpy", "abs", "absx", "absy",
              "long", "longx", "sr", "isry"}


def is_memory_read(op: int) -> bool:
    mn, mode = OPCODES[op]
    if mode not in _MEM_MODES:
        return mn in ("MVN", "MVP")
    return mn in _READ_MNEMONICS or mn in _RMW_MNEMONICS or mn in ("TSB", "TRB")


def instr_size(op: int, m8: bool, x8: bool) -> int:
    mn, mode = OPCODES[op]
    size = MODE_SIZE[mode]
    if size is None:
        wide = (not m8) if mode == "immM" else (not x8)
        return 3 if wide else 2
    return size


@dataclass
class Instr:
    addr: int          # endereço de CPU de 24 bits
    size: int
    raw: bytes
    mnemonic: str
    mode: str
    operand: str       # texto do operando estilo Asar
    target: int | None  # destino de saltos/branches (24 bits) ou endereço absoluto referenciado
    m8: bool
    x8: bool
    flags_uncertain: bool

    @property
    def text(self) -> str:
        return f"{self.mnemonic} {self.operand}".strip()

    def fmt(self) -> str:
        hexb = " ".join(f"{b:02X}" for b in self.raw)
        flags = ("m8" if self.m8 else "m16") + "," + ("x8" if self.x8 else "x16") + ("?" if self.flags_uncertain else "")
        return f"{(self.addr >> 16) & 0xFF:02X}:{self.addr & 0xFFFF:04X}  {hexb:<12} {self.text:<22} ; {flags}"


def _operand(mn: str, mode: str, b: bytes, addr: int, size: int) -> tuple[str, int | None]:
    bank = addr & 0xFF0000
    if mode == "imp":
        return "", None
    if mode == "acc":
        return "A", None
    if mode == "sig":
        return f"#${b[1]:02X}", None
    if mode in ("imm8", "immM", "immX", "imm16"):
        if size == 2:
            return f"#${b[1]:02X}", None
        v = b[1] | (b[2] << 8)
        return (f"${v:04X}" if mn == "PEA" else f"#${v:04X}"), None
    if mode in ("dp", "dpx", "dpy", "idp", "idpx", "idpy", "ildp", "ildpy", "sr", "isry"):
        v = b[1]
        fmt = {"dp": "${:02X}", "dpx": "${:02X},X", "dpy": "${:02X},Y", "idp": "(${:02X})",
               "idpx": "(${:02X},X)", "idpy": "(${:02X}),Y", "ildp": "[${:02X}]", "ildpy": "[${:02X}],Y",
               "sr": "${:02X},S", "isry": "(${:02X},S),Y"}[mode]
        return fmt.format(v), None
    if mode in ("abs", "absx", "absy", "iabs", "iabsx", "ilabs"):
        v = b[1] | (b[2] << 8)
        fmt = {"abs": "${:04X}", "absx": "${:04X},X", "absy": "${:04X},Y", "iabs": "(${:04X})",
               "iabsx": "(${:04X},X)", "ilabs": "[${:04X}]"}[mode]
        target = None
        if mn in ("JMP", "JSR") and mode == "abs":
            target = bank | v
        return fmt.format(v), target
    if mode in ("long", "longx"):
        v = b[1] | (b[2] << 8) | (b[3] << 16)
        return (f"${v:06X}" + (",X" if mode == "longx" else "")), (v if mn in ("JSL", "JML") else None)
    if mode == "rel8":
        off = b[1] - 256 if b[1] >= 128 else b[1]
        t = bank | ((addr + 2 + off) & 0xFFFF)
        return f"${t & 0xFFFF:04X}", t
    if mode == "rel16":
        off = (b[1] | (b[2] << 8))
        off = off - 65536 if off >= 32768 else off
        t = bank | ((addr + 3 + off) & 0xFFFF)
        return f"${t & 0xFFFF:04X}", t
    if mode == "blk":
        # codificação: opcode, banco destino, banco origem; sintaxe Asar: MVN origem,destino
        return f"${b[2]:02X},${b[1]:02X}", None
    return "?", None


def decode(buf: bytes, pos: int, addr: int, m8: bool, x8: bool, uncertain: bool = False) -> Instr | None:
    if pos >= len(buf):
        return None
    op = buf[pos]
    mn, mode = OPCODES[op]
    size = instr_size(op, m8, x8)
    raw = bytes(buf[pos:pos + size])
    if len(raw) < size:
        return None
    operand, target = _operand(mn, mode, raw, addr, size)
    return Instr(addr, size, raw, mn, mode, operand, target, m8, x8, uncertain)


def apply_flags(ins: Instr, m8: bool, x8: bool, uncertain: bool) -> tuple[bool, bool, bool]:
    """Estado M/X depois de executar `ins` (análise linear)."""
    if ins.mnemonic == "SEP":
        v = ins.raw[1]
        return (m8 or bool(v & 0x20)), (x8 or bool(v & 0x10)), uncertain
    if ins.mnemonic == "REP":
        v = ins.raw[1]
        return (m8 and not (v & 0x20)), (x8 and not (v & 0x10)), uncertain
    if ins.mnemonic in ("PLP", "RTI", "XCE"):
        return m8, x8, True
    return m8, x8, uncertain


def disassemble(buf: bytes, start_addr: int, count: int | None = None, length: int | None = None,
                m8: bool = True, x8: bool = True, pos: int = 0, stop_at_flow_end: bool = False) -> list[Instr]:
    """Desmonta linearmente `buf` (bytes a partir de `start_addr`, pos=offset em buf)."""
    out: list[Instr] = []
    addr = start_addr
    uncertain = False
    end = pos + length if length is not None else len(buf)
    while pos < end and (count is None or len(out) < count):
        ins = decode(buf, pos, addr, m8, x8, uncertain)
        if ins is None:
            break
        out.append(ins)
        m8, x8, uncertain = apply_flags(ins, m8, x8, uncertain)
        pos += ins.size
        addr = (addr & 0xFF0000) | ((addr + ins.size) & 0xFFFF)
        if stop_at_flow_end and ins.mnemonic in ENDS_FLOW:
            break
    return out


def find_access_before(buf: bytes, pos_next: int, addr_next: int, m8: bool, x8: bool,
                       write: bool = True) -> list[Instr]:
    """Dado o PC da instrução SEGUINTE a um acesso (o que o emulador reporta nos callbacks de
    escrita/leitura), devolve as instruções candidatas que terminam exatamente em pos_next."""
    pred = is_memory_write if write else is_memory_read
    cands = []
    for size in (1, 2, 3, 4):
        p = pos_next - size
        if p < 0:
            continue
        for mm, xx in ((m8, x8), (not m8, x8), (m8, not x8)):
            ins = decode(buf, p, (addr_next & 0xFF0000) | ((addr_next - size) & 0xFFFF), mm, xx)
            if ins and ins.size == size and pred(buf[p]):
                if all(c.addr != ins.addr for c in cands):
                    cands.append(ins)
    return cands


def find_writer_before(buf: bytes, pos_next: int, addr_next: int, m8: bool, x8: bool) -> list[Instr]:
    return find_access_before(buf, pos_next, addr_next, m8, x8, write=True)
