"""RV32I instruction decoder / control unit (``RC-FR-020/021/024/056/088``).

Decodes a (already decompressed) 32-bit instruction into the core's control
bundle: register addresses, write enables, ALU/shift/immediate selects, memory
access attributes, branch/jump controls and the ``illegal`` flag.

The decoder is **registry-driven** (``RC-FR-056``): for every selected extension
that implements the :meth:`~myhdl_addons.riscv.extensions.Extension.decode_stage`
hook, a decode stage is elaborated.  Each stage is handed a private
:class:`~myhdl_addons.common.views.SignalView` (``instr`` plus a full control
bundle including ``matched``) and drives it; the decoder then selects, per
signal, the **highest-priority matched** stage over the base decode
(base-then-extensions by priority, Q16).  Extensions with no decode stage — and
every extension that is not selected — add no logic (``RC-FR-033``).

Illegal detection (``RC-FR-024/088``) covers unknown 32-bit encodings and any
16-bit encoding (``inst[1:0] != 2'b11``): compressed instructions are expanded
ahead of the decoder when C is enabled, so a surviving 16-bit word is illegal
(and, with C disabled, every 16-bit word is).  The ALU op codes follow the
default :data:`myhdl_addons.components.AVAIL_OPS` order; shift instructions
raise ``shift``/``shift_mode`` for the barrel shifter instead.
"""

from myhdl import Signal, always_comb, block, intbv

from ..common.config import ComponentBase
from ..common.views import SignalView
from ..components.alu import AVAIL_OPS
from ..components.shifter import SLL, SRA, SRL
from .extensions import Extension
from .immgen import AVAIL_IMM_TYPES

__all__ = ["InstructionDecoder"]

#: ALU op codes (default ``Alu`` order) and immediate-format codes.
_ALU = {name: code for code, name in enumerate(AVAIL_OPS)}
_IMM = {name: code for code, name in enumerate(AVAIL_IMM_TYPES)}

_OP_LUI = 0x37
_OP_AUIPC = 0x17
_OP_JAL = 0x6F
_OP_JALR = 0x67
_OP_BRANCH = 0x63
_OP_LOAD = 0x03
_OP_STORE = 0x23
_OP_IMM = 0x13
_OP_ALU = 0x33
_OP_MISC = 0x0F
_OP_SYSTEM = 0x73

_BYTE = 0
_HALF = 1
_WORD = 2

#: Control-bundle signals and their widths (``1`` = a ``bool``).
_CONTROL_WIDTHS = {
    "rs1": 5,
    "rs2": 5,
    "rd": 5,
    "reg_write": 1,
    "alu_a_pc": 1,
    "alu_b_imm": 1,
    "alu_op": 4,
    "shift": 1,
    "shift_mode": 3,
    "imm_sel": 3,
    "mem_read": 1,
    "mem_write": 1,
    "mem_size": 2,
    "mem_unsigned": 1,
    "branch": 1,
    "branch_op": 3,
    "jump": 1,
    "jalr": 1,
    "ecall": 1,
    "ebreak": 1,
    "fence": 1,
    "illegal": 1,
}


def _make_bundle(widths: dict) -> SignalView:
    """Return a fresh control bundle with the given ``{name: width}``."""
    signals = {}
    for name, width in widths.items():
        signals[name] = Signal(bool(0)) if width == 1 else Signal(intbv(0)[width:])
    return SignalView(**signals)


def _overrides_decode_stage(extension: Extension) -> bool:
    """Return whether *extension* (or a base) overrides ``decode_stage``."""
    for klass in type(extension).__mro__:
        if "decode_stage" in klass.__dict__:
            return klass is not Extension
    return False


@block
def decode_override(prev, override, sel, out):
    """``out = override`` when *sel*, else *prev* (one control signal)."""

    @always_comb
    def p():
        if sel:
            out.next = override
        else:
            out.next = prev

    return p


@block
def decode_bind(src, dst):
    """Bind a private control signal to the decoder output."""

    @always_comb
    def p():
        dst.next = src

    return p


@block
def base_decode(instr, controls):
    """RV32I base decode into the control bundle *controls* (``RC-FR-020``)."""

    alu_nop = _ALU["NOP"]
    alu_add = _ALU["ADD"]
    alu_sub = _ALU["SUB"]
    alu_and = _ALU["AND"]
    alu_or = _ALU["OR"]
    alu_xor = _ALU["XOR"]
    alu_slt = _ALU["SLT"]
    alu_sltu = _ALU["SLTU"]
    alu_pass_a = _ALU["PASS_A"]
    alu_pass_b = _ALU["PASS_B"]
    imm_i = _IMM["I"]
    imm_s = _IMM["S"]
    imm_b = _IMM["B"]
    imm_u = _IMM["U"]
    imm_j = _IMM["J"]
    op_lui = _OP_LUI
    op_auipc = _OP_AUIPC
    op_jal = _OP_JAL
    op_jalr = _OP_JALR
    op_branch = _OP_BRANCH
    op_load = _OP_LOAD
    op_store = _OP_STORE
    op_imm = _OP_IMM
    op_alu = _OP_ALU
    op_misc = _OP_MISC
    op_system = _OP_SYSTEM

    @always_comb
    def p():
        controls.rd.next = instr[12:7]
        controls.rs1.next = instr[20:15]
        controls.rs2.next = instr[25:20]
        controls.reg_write.next = 0
        controls.alu_a_pc.next = 0
        controls.alu_b_imm.next = 0
        controls.alu_op.next = alu_nop
        controls.shift.next = 0
        controls.shift_mode.next = 0
        controls.imm_sel.next = imm_i
        controls.mem_read.next = 0
        controls.mem_write.next = 0
        controls.mem_size.next = _WORD
        controls.mem_unsigned.next = 0
        controls.branch.next = 0
        controls.branch_op.next = 0
        controls.jump.next = 0
        controls.jalr.next = 0
        controls.ecall.next = 0
        controls.ebreak.next = 0
        controls.fence.next = 0
        controls.illegal.next = 1

        if instr[2:0] == 0b11:  # compressed words are expanded ahead
            if instr[7:] == op_lui:
                controls.reg_write.next = 1
                controls.alu_b_imm.next = 1
                controls.alu_op.next = alu_pass_b
                controls.imm_sel.next = imm_u
                controls.illegal.next = 0
            elif instr[7:] == op_auipc:
                controls.reg_write.next = 1
                controls.alu_a_pc.next = 1
                controls.alu_b_imm.next = 1
                controls.alu_op.next = alu_add
                controls.imm_sel.next = imm_u
                controls.illegal.next = 0
            elif instr[7:] == op_jal:
                controls.reg_write.next = 1
                controls.jump.next = 1
                controls.alu_a_pc.next = 1
                controls.alu_b_imm.next = 1
                controls.alu_op.next = alu_add
                controls.imm_sel.next = imm_j
                controls.illegal.next = 0
            elif instr[7:] == op_jalr:
                if instr[15:12] == 0b000:
                    controls.reg_write.next = 1
                    controls.jump.next = 1
                    controls.jalr.next = 1
                    controls.alu_b_imm.next = 1
                    controls.alu_op.next = alu_add
                    controls.imm_sel.next = imm_i
                    controls.illegal.next = 0
            elif instr[7:] == op_branch:
                if instr[15:12] != 0b010 and instr[15:12] != 0b011:
                    controls.branch.next = 1
                    controls.branch_op.next = instr[15:12]
                    controls.alu_a_pc.next = 1
                    controls.alu_b_imm.next = 1
                    controls.alu_op.next = alu_add
                    controls.imm_sel.next = imm_b
                    controls.illegal.next = 0
            elif instr[7:] == op_load:
                if (
                    instr[15:12] == 0b000
                    or instr[15:12] == 0b001
                    or instr[15:12] == 0b010
                    or instr[15:12] == 0b100
                    or instr[15:12] == 0b101
                ):
                    controls.reg_write.next = 1
                    controls.mem_read.next = 1
                    controls.alu_b_imm.next = 1
                    controls.alu_op.next = alu_add
                    controls.imm_sel.next = imm_i
                    controls.mem_size.next = instr[14:12]
                    controls.mem_unsigned.next = instr[14]
                    controls.illegal.next = 0
            elif instr[7:] == op_store:
                if (
                    instr[15:12] == 0b000
                    or instr[15:12] == 0b001
                    or instr[15:12] == 0b010
                ):
                    controls.mem_write.next = 1
                    controls.alu_b_imm.next = 1
                    controls.alu_op.next = alu_add
                    controls.imm_sel.next = imm_s
                    controls.mem_size.next = instr[14:12]
                    controls.illegal.next = 0
            elif instr[7:] == op_imm:
                controls.reg_write.next = 1
                controls.alu_b_imm.next = 1
                controls.imm_sel.next = imm_i
                if instr[15:12] == 0b001:  # slli
                    if instr[32:25] == 0:
                        controls.alu_op.next = alu_pass_a
                        controls.shift.next = 1
                        controls.shift_mode.next = SLL
                        controls.illegal.next = 0
                elif instr[15:12] == 0b101:  # srli / srai
                    if instr[32:25] == 0:
                        controls.alu_op.next = alu_pass_a
                        controls.shift.next = 1
                        controls.shift_mode.next = SRL
                        controls.illegal.next = 0
                    elif instr[32:25] == 0b0100000:
                        controls.alu_op.next = alu_pass_a
                        controls.shift.next = 1
                        controls.shift_mode.next = SRA
                        controls.illegal.next = 0
                elif instr[15:12] == 0b000:
                    controls.alu_op.next = alu_add
                    controls.illegal.next = 0
                elif instr[15:12] == 0b010:
                    controls.alu_op.next = alu_slt
                    controls.illegal.next = 0
                elif instr[15:12] == 0b011:
                    controls.alu_op.next = alu_sltu
                    controls.illegal.next = 0
                elif instr[15:12] == 0b100:
                    controls.alu_op.next = alu_xor
                    controls.illegal.next = 0
                elif instr[15:12] == 0b110:
                    controls.alu_op.next = alu_or
                    controls.illegal.next = 0
                elif instr[15:12] == 0b111:
                    controls.alu_op.next = alu_and
                    controls.illegal.next = 0
            elif instr[7:] == op_alu:
                controls.reg_write.next = 1
                if instr[15:12] == 0b000:  # add / sub
                    if instr[32:25] == 0:
                        controls.alu_op.next = alu_add
                        controls.illegal.next = 0
                    elif instr[32:25] == 0b0100000:
                        controls.alu_op.next = alu_sub
                        controls.illegal.next = 0
                elif instr[15:12] == 0b001:  # sll
                    if instr[32:25] == 0:
                        controls.alu_op.next = alu_pass_a
                        controls.shift.next = 1
                        controls.shift_mode.next = SLL
                        controls.illegal.next = 0
                elif instr[15:12] == 0b010:
                    if instr[32:25] == 0:
                        controls.alu_op.next = alu_slt
                        controls.illegal.next = 0
                elif instr[15:12] == 0b011:
                    if instr[32:25] == 0:
                        controls.alu_op.next = alu_sltu
                        controls.illegal.next = 0
                elif instr[15:12] == 0b100:
                    if instr[32:25] == 0:
                        controls.alu_op.next = alu_xor
                        controls.illegal.next = 0
                elif instr[15:12] == 0b101:  # srl / sra
                    if instr[32:25] == 0:
                        controls.alu_op.next = alu_pass_a
                        controls.shift.next = 1
                        controls.shift_mode.next = SRL
                        controls.illegal.next = 0
                    elif instr[32:25] == 0b0100000:
                        controls.alu_op.next = alu_pass_a
                        controls.shift.next = 1
                        controls.shift_mode.next = SRA
                        controls.illegal.next = 0
                elif instr[15:12] == 0b110:
                    if instr[32:25] == 0:
                        controls.alu_op.next = alu_or
                        controls.illegal.next = 0
                elif instr[15:12] == 0b111 and instr[32:25] == 0:
                    controls.alu_op.next = alu_and
                    controls.illegal.next = 0
            elif instr[7:] == op_misc:
                if instr[15:12] == 0b000 or instr[15:12] == 0b001:
                    controls.fence.next = 1
                    controls.illegal.next = 0
            elif instr[7:] == op_system:
                if instr[15:12] == 0b000:
                    if instr[32:20] == 0 and instr[20:15] == 0 and instr[12:7] == 0:
                        controls.ecall.next = 1
                        controls.illegal.next = 0
                    elif instr[32:20] == 1 and instr[20:15] == 0 and instr[12:7] == 0:
                        controls.ebreak.next = 1
                        controls.illegal.next = 0

    return p


class InstructionDecoder(ComponentBase):
    """Combinational RV32I decoder / control unit (``RC-FR-020``).

    Args:
        registry: the :class:`ExtensionRegistry` whose selected extensions may
            contribute a decode stage (default: none).  Only the selected set
            is honoured.
    """

    def __init__(self, registry=None) -> None:
        self._extensions = tuple(registry.selected) if registry is not None else ()
        self._params = {"extensions": tuple(ext.name for ext in self._extensions)}

    def ports(self) -> SignalView:
        """Allocate and return the control-bundle interface."""
        signals = {"instr": Signal(intbv(0)[32:])}
        signals.update(_make_bundle(_CONTROL_WIDTHS).signals)
        return SignalView(**signals)

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the decoder onto *ports* and return its instances."""
        instr = ports.instr
        # ascending priority so a later (higher-priority) stage overrides
        stages = [
            ext for ext in reversed(self._extensions) if _overrides_decode_stage(ext)
        ]

        proclist = []
        base = _make_bundle(_CONTROL_WIDTHS)
        proclist.append(base_decode(instr, base))

        current = base
        for extension in stages:
            ext_bundle = _make_bundle({**_CONTROL_WIDTHS, "matched": 1})
            context = SignalView(
                instr=instr,
                **{name: ext_bundle[name] for name in ext_bundle.names},
            )
            proclist.append(extension.decode_stage(context))
            merged = _make_bundle(_CONTROL_WIDTHS)
            for name in _CONTROL_WIDTHS:
                proclist.append(
                    decode_override(
                        current[name],
                        ext_bundle[name],
                        ext_bundle["matched"],
                        merged[name],
                    )
                )
            current = merged

        for name in _CONTROL_WIDTHS:
            proclist.append(decode_bind(current[name], ports[name]))

        return proclist
