"""Arithmetic/logic unit (``IC-FR-010..019``).

A generic, ISA-neutral ALU covering arithmetic and bitwise operations only
(shifts live in :mod:`~myhdl_addons.components.shifter`).  The enabled op set
and flag set are elaboration-time parameters; disabled logic is not built.
"""

from collections.abc import Callable, Sequence

from myhdl import (
    ResetSignal,
    Signal,
    always,
    always_comb,
    block,
    concat,
    intbv,
)

from ..common.config import (
    ComponentBase,
    ceil_log2,
    check_positive,
)
from ..common.errors import HdlConfigError, HdlTypeError
from ..common.views import SignalView

__all__ = [
    "AVAIL_FLAGS",
    "AVAIL_OPS",
    "Alu",
]

AVAIL_OPS = ("NOP", "ADD", "SUB", "AND", "OR", "XOR", "SLT", "SLTU", "PASS_A", "PASS_B")

AVAIL_FLAGS = ("zero", "lt", "ltu", "carry")


class Alu(ComponentBase):
    """Combinational (or registered) arithmetic/logic unit.

    Args:
        width: datapath width.
        ops: enabled op subset (names, or ``None`` = all).
        flags: enabled flag subset, or ``None`` = all.
        registered: if true, use register output
        en: add an output enable when registered.
        reset_value: registered reset value for ``y``.
        reset_signal: use the specific ResetSignal, or ``None`` to create a default.
    """

    def __init__(
        self,
        width: int = 32,
        ops: Sequence[str] | None = None,
        flags: Sequence[str] | None = None,
        registered: bool = False,
        en: bool = False,
        reset_value: int = 0,
        reset_signal: ResetSignal | None = None,
    ) -> None:
        p_width = int(check_positive(width, "width"))
        p_ops = AVAIL_OPS if ops is None else tuple(set(ops))
        # add NOP as required 0-index operation
        if "NOP" not in p_ops:
            p_ops = tuple(["NOP", *list(set(ops))])
        p_flags = AVAIL_FLAGS if flags is None else tuple(set(flags))
        p_registered = bool(registered)
        p_en = bool(en)
        p_reset_value = reset_value
        p_reset_signal = reset_signal if isinstance(reset_signal, ResetSignal) else None
        self._params = {
            "width": p_width,
            "ops": p_ops,
            "ops_count": len(p_ops),
            "flags": p_flags,
            "registered": p_registered,
            "en": p_en,
            "reset_value": p_reset_value,
            "reset_signal": p_reset_signal,
        }
        self._extraops = {}

    def ports(self) -> SignalView:
        """Allocate a fresh :class:`SignalView` view matching the configuration."""

        ops_width = ceil_log2(self._params["ops_count"])
        sig = {
            "a": Signal(intbv(0)[self._params["width"] :]),
            "b": Signal(intbv(0)[self._params["width"] :]),
            "op": Signal(intbv(0)[ops_width:]),
            "y": Signal(intbv(0)[self._params["width"] :]),
        }
        for flag in self._params["flags"]:
            sig[flag] = Signal(bool(0))
        if self._params["registered"]:
            sig["clk"] = Signal(bool(0))
            if self._params["reset_signal"] is None:
                self._params["reset_signal"] = ResetSignal(0, active=0, isasync=False)
                sig["reset"] = self._params["reset_signal"]
            if self._params["en"]:
                sig["en"] = Signal(bool(0))
        return SignalView(**sig)

    def register_op(self, opname: str, proc_cb: Callable):
        if opname in self._params["ops"]:
            raise HdlConfigError(
                f"Trying to register ALU op already included by default ({opname})"
            )
        if opname in self._extraops:
            raise HdlConfigError(
                f"Trying to register ALU op already registered ({opname})"
            )
        self._extraops[opname] = proc_cb
        self._params["ops"] = tuple([*list(self.ops), opname])
        self._params["ops_count"] += 1

    def get_op_intmap(self) -> dict[str, int]:
        return {k: i for i, k in enumerate(self._params["ops"])}

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the ALU onto *ports* and return its instances."""

        width = self._params["width"]

        # Partial in/out with a bit extra for carry/overflow
        partial_a = Signal(intbv(0)[width + 1 :])
        partial_b = Signal(intbv(0)[width + 1 :])
        partial_y = Signal(intbv(0)[width + 1 :])

        # partial subops
        partial_ops_y = tuple(
            [Signal(intbv(0)[width + 1 :]) for _ in self._params["ops"]]
        )

        op_map = self.get_op_intmap()
        op_idx_max = len(partial_ops_y)

        partial_lt = Signal(bool(0))
        partial_ltu = Signal(bool(0))

        proclist = []

        @always_comb
        def inputentry():
            partial_a.next = concat(intbv(0)[1:], ports.a)
            partial_b.next = concat(intbv(0)[1:], ports.b)

        proclist.append(inputentry)

        # standard operations
        if "ADD" in self._params["ops"]:
            op_idx_add = op_map["ADD"]

            @always_comb
            def alu_proc_add():
                partial_ops_y[op_idx_add].next = partial_a + partial_b

            proclist.append(alu_proc_add)

        if "SUB" in self._params["ops"]:
            op_idx_sub = op_map["SUB"]

            @always_comb
            def alu_proc_sub():
                # mask so a<b wraps (MyHDL assignment forbids negatives)
                partial_ops_y[op_idx_sub].next = (partial_a - partial_b) & (
                    (1 << (width + 1)) - 1
                )

            proclist.append(alu_proc_sub)

        if "AND" in self._params["ops"]:
            op_idx_and = op_map["AND"]

            @always_comb
            def alu_proc_and():
                partial_ops_y[op_idx_and].next = partial_a & partial_b

            proclist.append(alu_proc_and)

        if "OR" in self._params["ops"]:
            op_idx_or = op_map["OR"]

            @always_comb
            def alu_proc_or():
                partial_ops_y[op_idx_or].next = partial_a | partial_b

            proclist.append(alu_proc_or)

        if "XOR" in self._params["ops"]:
            op_idx_xor = op_map["XOR"]

            @always_comb
            def alu_proc_xor():
                partial_ops_y[op_idx_xor].next = partial_a ^ partial_b

            proclist.append(alu_proc_xor)

        if "SLT" in self._params["ops"]:
            op_idx_slt = op_map["SLT"]

            @always_comb
            def alu_proc_slt():
                if partial_lt == 1:
                    partial_ops_y[op_idx_slt].next = 1
                else:
                    partial_ops_y[op_idx_slt].next = 0

            proclist.append(alu_proc_slt)

        if "SLTU" in self._params["ops"]:
            op_idx_sltu = op_map["SLTU"]

            @always_comb
            def alu_proc_sltu():
                if partial_ltu == 1:
                    partial_ops_y[op_idx_sltu].next = 1
                else:
                    partial_ops_y[op_idx_sltu].next = 0

            proclist.append(alu_proc_sltu)

        if "PASS_A" in self._params["ops"]:
            op_idx_pass_a = op_map["PASS_A"]

            @always_comb
            def alu_proc_pass_a():
                partial_ops_y[op_idx_pass_a].next = partial_a

            proclist.append(alu_proc_pass_a)

        if "PASS_B" in self._params["ops"]:
            op_idx_pass_b = op_map["PASS_B"]

            @always_comb
            def alu_proc_pass_b():
                partial_ops_y[op_idx_pass_b].next = partial_b

            proclist.append(alu_proc_pass_b)

        # extra operations (if defined)
        for extra_op_name, extra_op_cb in self._extraops.items():
            op_idx_extra = op_map[extra_op_name]
            proclist.append(
                extra_op_cb(partial_a, partial_b, partial_ops_y[op_idx_extra])
            )

        # NOTE: always_comb is not including signal's tuple in sensitivity list
        # fall back to always decorator with manual sensitivity list
        @always(ports.op, *partial_ops_y)
        def alu_mux():
            if int(ports.op) == 0 or int(ports.op) >= op_idx_max:
                partial_y.next = 0
            else:
                partial_y.next = partial_ops_y[int(ports.op)]

        proclist.append(alu_mux)

        @always_comb
        def alu_lt_compute():
            # signed compare without a helper: MyHDL turns a helper's ``return``
            # into a Verilog ``function`` with ``disable``, which Yosys rejects.
            # Compare the sign bits first, then fall back to unsigned.
            if partial_a[width - 1] != partial_b[width - 1]:
                partial_lt.next = partial_a[width - 1]
            else:
                partial_lt.next = partial_a < partial_b
            if partial_a < partial_b:
                partial_ltu.next = 1
            else:
                partial_ltu.next = 0

        proclist.append(alu_lt_compute)

        if "carry" in self._params["flags"]:

            @always_comb
            def alu_flag_carry():
                ports.carry.next = partial_y[width]

            proclist.append(alu_flag_carry)

        if "lt" in self._params["flags"]:

            @always_comb
            def alu_flag_lt():
                ports.lt.next = partial_lt

            proclist.append(alu_flag_lt)

        if "ltu" in self._params["flags"]:

            @always_comb
            def alu_flag_ltu():
                ports.ltu.next = partial_ltu

            proclist.append(alu_flag_ltu)

        if "zero" in self._params["flags"]:

            @always_comb
            def alu_flag_zero():
                if partial_y[width:] == 0:
                    ports.zero.next = 1
                else:
                    ports.zero.next = 0

            proclist.append(alu_flag_zero)

        if self._params["registered"]:
            en_sig = ports.en if self._params["en"] else Signal(bool(1))
            reset_y_val = intbv(self._params["reset_value"])[width:]

            # NOTE: reset signal level and async is hardcoded to active high synchronous.
            if not isinstance(ports.reset, ResetSignal):
                raise HdlTypeError("Reset signal must be of ResetSignal type")

            # NOTE: @always_seq is not detecting the reset functionality,
            # Changing back to @always decorator

            @always(ports.clk.posedge)
            def alu_reg_output():
                if not ports.reset:
                    if en_sig:
                        ports.y.next = partial_y[width:]
                else:
                    ports.y.next = reset_y_val

        else:

            @always_comb
            def alu_reg_output():
                ports.y.next = partial_y[width:]

        proclist.append(alu_reg_output)

        return proclist
