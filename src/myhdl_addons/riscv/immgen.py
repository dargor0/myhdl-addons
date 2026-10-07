"""RV32I immediate generator (``RC-FR-022``).

Decodes the instruction-embedded immediate from a 32-bit word for the five base
formats and sign-extends it (except U, whose 20-bit upper field is
zero-extended and placed in bits 31:12).  The format is selected by the
``imm_sel`` input using :meth:`ImmGen.get_imm_intmap`, so the decoder drives it
without the block knowing any opcode:

* **I** — ``inst[31:20]`` (OP-IMM, ``JALR``, loads);
* **S** — ``inst[31:25]:inst[11:7]`` (stores);
* **B** — ``inst[31]:inst[7]:inst[30:25]:inst[11:8]:0`` (branches);
* **U** — ``inst[31:12]`` (``LUI``/``AUIPC``);
* **J** — ``inst[31]:inst[19:12]:inst[20]:inst[30:21]:0`` (``JAL``).

The block is purely combinational.  Sign extension uses the same
"sign-filled wide constant + field" concatenation as the barrel shifter, so it
stays inside the MyHDL convertible subset.
"""

from myhdl import Signal, always_comb, block, concat, intbv

from ..common.config import ComponentBase, ceil_log2
from ..common.views import SignalView

__all__ = ["AVAIL_IMM_TYPES", "ImmGen"]

#: RV32I immediate formats, in ``imm_sel`` code order.
AVAIL_IMM_TYPES = ("I", "S", "B", "U", "J")

_FULL = 0xFFFF_FFFF


class ImmGen(ComponentBase):
    """Combinational RV32I immediate generator (``RC-FR-022``).

    Ports: ``instr`` (32-bit), ``imm_sel`` (format selector, see
    :meth:`get_imm_intmap`) and ``imm`` (32-bit, sign/zero-extended).
    """

    def __init__(self) -> None:
        self._params = {"imm_types": AVAIL_IMM_TYPES}

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        sel_bits = max(1, ceil_log2(len(AVAIL_IMM_TYPES)))
        return SignalView(
            instr=Signal(intbv(0)[32:]),
            imm_sel=Signal(intbv(0)[sel_bits:]),
            imm=Signal(intbv(0)[32:]),
        )

    def get_imm_intmap(self) -> dict[str, int]:
        """Return the ``imm_sel`` code for each format name."""
        return {name: code for code, name in enumerate(AVAIL_IMM_TYPES)}

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the generator onto *ports* and return its instances."""
        instr = ports.instr
        imm_map = self.get_imm_intmap()
        sel_i = imm_map["I"]
        sel_s = imm_map["S"]
        sel_b = imm_map["B"]
        sel_u = imm_map["U"]
        sel_j = imm_map["J"]

        imm_i = Signal(intbv(0)[32:])
        imm_s = Signal(intbv(0)[32:])
        imm_b = Signal(intbv(0)[32:])
        imm_u = Signal(intbv(0)[32:])
        imm_j = Signal(intbv(0)[32:])

        @always_comb
        def gen_i():
            if instr[31]:
                imm_i.next = concat(intbv(_FULL)[20:], instr[32:20])
            else:
                imm_i.next = concat(intbv(0)[20:], instr[32:20])

        @always_comb
        def gen_s():
            if instr[31]:
                imm_s.next = concat(intbv(_FULL)[20:], instr[32:25], instr[12:7])
            else:
                imm_s.next = concat(intbv(0)[20:], instr[32:25], instr[12:7])

        @always_comb
        def gen_b():
            if instr[31]:
                imm_b.next = concat(
                    intbv(_FULL)[19:],
                    instr[32:31],
                    instr[8:7],
                    instr[31:25],
                    instr[12:8],
                    intbv(0)[1:],
                )
            else:
                imm_b.next = concat(
                    intbv(0)[19:],
                    instr[32:31],
                    instr[8:7],
                    instr[31:25],
                    instr[12:8],
                    intbv(0)[1:],
                )

        @always_comb
        def gen_u():
            imm_u.next = concat(instr[32:12], intbv(0)[12:])

        @always_comb
        def gen_j():
            if instr[31]:
                imm_j.next = concat(
                    intbv(_FULL)[11:],
                    instr[32:31],
                    instr[20:12],
                    instr[21:20],
                    instr[31:21],
                    intbv(0)[1:],
                )
            else:
                imm_j.next = concat(
                    intbv(0)[11:],
                    instr[32:31],
                    instr[20:12],
                    instr[21:20],
                    instr[31:21],
                    intbv(0)[1:],
                )

        @always_comb
        def select_imm():
            if ports.imm_sel == sel_i:
                ports.imm.next = imm_i
            elif ports.imm_sel == sel_s:
                ports.imm.next = imm_s
            elif ports.imm_sel == sel_b:
                ports.imm.next = imm_b
            elif ports.imm_sel == sel_u:
                ports.imm.next = imm_u
            elif ports.imm_sel == sel_j:
                ports.imm.next = imm_j
            else:
                ports.imm.next = 0

        return [gen_i, gen_s, gen_b, gen_u, gen_j, select_imm]
