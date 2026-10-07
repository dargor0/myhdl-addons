"""RV32I branch unit and jump-target helper (``RC-FR-023`` / ``RC-FR-029``).

Evaluates the six conditional-branch conditions on two operands using the
generic :class:`~myhdl_addons.components.Comparator` (``RC-FR-029``), and
provides the :func:`jalr_target` helper that clears bit 0 of a computed JALR
target (``RC-FR-023``).  The target arithmetic itself (``pc + imm`` for
branches/``JAL``, ``rs1 + imm`` for ``JALR``) is performed by the core's ALU and
:class:`Incrementer`; this module only resolves the condition and the
RISC-V-specific bit-0 rule.
"""

from myhdl import Signal, always_comb, block, intbv

from ..common.config import ComponentBase, check_positive
from ..common.views import SignalView
from ..components import Comparator

__all__ = ["AVAIL_BRANCH_OPS", "BranchUnit", "jalr_target"]

#: Conditional-branch ops, in :meth:`BranchUnit.get_op_intmap` order.
AVAIL_BRANCH_OPS = ("BEQ", "BNE", "BLT", "BGE", "BLTU", "BGEU")

#: RV32I branch funct3 code for each op (the decoder's ``branch_op``).
_BRANCH_CODES = {
    "BEQ": 0b000,
    "BNE": 0b001,
    "BLT": 0b100,
    "BGE": 0b101,
    "BLTU": 0b110,
    "BGEU": 0b111,
}

#: Comparator flags consumed by the conditions (``lt``/``ge`` are signed).
_CMP_OUTPUTS = ("eq", "ne", "lt", "ltu", "ge")

_LSB_CLEAR = 0xFFFF_FFFE


class BranchUnit(ComponentBase):
    """Combinational RV32I branch-condition evaluator (``RC-FR-023``).

    Ports: ``a`` / ``b`` (operands), ``op`` (branch ``funct3``, see
    :meth:`get_op_intmap`) and ``take`` (the condition is true).  ``BLT`` /
    ``BGE`` are signed, ``BLTU`` / ``BGEU`` unsigned (``RC-FR-023``); a reserved
    ``funct3`` yields ``take = 0``.
    """

    def __init__(self, width: int = 32) -> None:
        self._params = {"width": int(check_positive(width, "width"))}

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        width = self._params["width"]
        return SignalView(
            a=Signal(intbv(0)[width:]),
            b=Signal(intbv(0)[width:]),
            op=Signal(intbv(0)[3:]),
            take=Signal(bool(0)),
        )

    def get_op_intmap(self) -> dict[str, int]:
        """Return the branch ``funct3`` code for each op name."""
        return dict(_BRANCH_CODES)

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the branch unit onto *ports* and return its instances."""
        width = self._params["width"]
        op_map = self.get_op_intmap()

        comparator = Comparator(width=width, outputs=_CMP_OUTPUTS, signed=True)
        cmp_ports = comparator.ports()
        cmp_ports.a = ports.a
        cmp_ports.b = ports.b

        beq = op_map["BEQ"]
        bne = op_map["BNE"]
        blt = op_map["BLT"]
        bge = op_map["BGE"]
        bltu = op_map["BLTU"]
        bgeu = op_map["BGEU"]

        @always_comb
        def select():
            if ports.op == beq:
                ports.take.next = cmp_ports.eq
            elif ports.op == bne:
                ports.take.next = cmp_ports.ne
            elif ports.op == blt:
                ports.take.next = cmp_ports.lt
            elif ports.op == bge:
                ports.take.next = cmp_ports.ge
            elif ports.op == bltu:
                ports.take.next = cmp_ports.ltu
            elif ports.op == bgeu:
                ports.take.next = not cmp_ports.ltu
            else:
                ports.take.next = 0

        return [comparator.hdl(cmp_ports), select]


@block
def jalr_target(addr_i, jalr, addr_o):
    """Clear bit 0 of a computed target when *jalr* is set (``RC-FR-023``).

    The core adds ``rs1 + imm`` with the ALU and routes the result through this
    block; ``jalr`` selects the clearing, so a non-``JALR`` target passes
    through unchanged (its bit 0 is already zero).
    """

    @always_comb
    def p():
        if jalr:
            addr_o.next = addr_i & _LSB_CLEAR
        else:
            addr_o.next = addr_i

    return p
