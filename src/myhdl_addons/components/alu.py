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
from ..common.errors import HdlConfigError
from ..common.reset import make_reset
from ..common.views import SignalView
from .mux_tree import MuxTree

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
        # NOP is always present and always op 0.
        if ops is None:
            p_ops = AVAIL_OPS
        else:
            p_ops = tuple(["NOP", *[op for op in set(ops) if op != "NOP"]])
        p_flags = AVAIL_FLAGS if flags is None else tuple(set(flags))
        p_registered = bool(registered)
        p_en = bool(en)
        p_reset_value = reset_value
        self._params = {
            "width": p_width,
            "ops": p_ops,
            "ops_count": len(p_ops),
            "flags": p_flags,
            "registered": p_registered,
            "en": p_en,
            "reset_value": p_reset_value,
            "reset_signal": make_reset(reset_signal),
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
        op_map = self.get_op_intmap()

        # Partial in/out with a bit extra for carry/overflow
        partial_a = Signal(intbv(0)[width + 1 :])
        partial_b = Signal(intbv(0)[width + 1 :])

        # The op-result select is a balanced MuxTree (one input per op), so no
        # tuple/list of signals indexed by ``op`` (MyHDL does not convert that
        # cleanly).  ``default_value=0`` supplies the result for an unknown op.
        mux = MuxTree(
            width=width + 1,
            n=len(self._params["ops"]),
            policy="const",
            default_value=0,
        )
        mux_ports = mux.ports()
        partial_y = mux_ports.y

        proclist = [mux.hdl(mux_ports)]

        if mux.sel_bits:

            @always_comb
            def alu_op_sel():
                mux_ports.sel.next = ports.op

            proclist.append(alu_op_sel)

        # Only build the signed/unsigned compare when an op or flag consumes it,
        # so no signal is driven without a reader.
        use_lt = ("SLT" in self._params["ops"]) or ("lt" in self._params["flags"])
        use_ltu = ("SLTU" in self._params["ops"]) or ("ltu" in self._params["flags"])
        partial_lt = Signal(bool(0)) if use_lt else None
        partial_ltu = Signal(bool(0)) if use_ltu else None

        # NOP (op code 0 by convention) yields zero.  Folded into inputentry
        # because a constant-only @always_comb has an empty sensitivity list.
        nop_y = mux_ports[f"in{op_map['NOP']}"]

        @always_comb
        def inputentry():
            partial_a.next = concat(intbv(0)[1:], ports.a)
            partial_b.next = concat(intbv(0)[1:], ports.b)
            nop_y.next = 0

        proclist.append(inputentry)

        # standard operations
        if "ADD" in self._params["ops"]:
            add_y = mux_ports[f"in{op_map['ADD']}"]

            @always_comb
            def alu_proc_add():
                add_y.next = partial_a + partial_b

            proclist.append(alu_proc_add)

        if "SUB" in self._params["ops"]:
            sub_y = mux_ports[f"in{op_map['SUB']}"]

            @always_comb
            def alu_proc_sub():
                # mask so a<b wraps (MyHDL assignment forbids negatives)
                sub_y.next = (partial_a - partial_b) & ((1 << (width + 1)) - 1)

            proclist.append(alu_proc_sub)

        if "AND" in self._params["ops"]:
            and_y = mux_ports[f"in{op_map['AND']}"]

            @always_comb
            def alu_proc_and():
                and_y.next = partial_a & partial_b

            proclist.append(alu_proc_and)

        if "OR" in self._params["ops"]:
            or_y = mux_ports[f"in{op_map['OR']}"]

            @always_comb
            def alu_proc_or():
                or_y.next = partial_a | partial_b

            proclist.append(alu_proc_or)

        if "XOR" in self._params["ops"]:
            xor_y = mux_ports[f"in{op_map['XOR']}"]

            @always_comb
            def alu_proc_xor():
                xor_y.next = partial_a ^ partial_b

            proclist.append(alu_proc_xor)

        if "SLT" in self._params["ops"]:
            slt_y = mux_ports[f"in{op_map['SLT']}"]

            @always_comb
            def alu_proc_slt():
                if partial_lt == 1:
                    slt_y.next = 1
                else:
                    slt_y.next = 0

            proclist.append(alu_proc_slt)

        if "SLTU" in self._params["ops"]:
            sltu_y = mux_ports[f"in{op_map['SLTU']}"]

            @always_comb
            def alu_proc_sltu():
                if partial_ltu == 1:
                    sltu_y.next = 1
                else:
                    sltu_y.next = 0

            proclist.append(alu_proc_sltu)

        if "PASS_A" in self._params["ops"]:
            pass_a_y = mux_ports[f"in{op_map['PASS_A']}"]

            @always_comb
            def alu_proc_pass_a():
                pass_a_y.next = partial_a

            proclist.append(alu_proc_pass_a)

        if "PASS_B" in self._params["ops"]:
            pass_b_y = mux_ports[f"in{op_map['PASS_B']}"]

            @always_comb
            def alu_proc_pass_b():
                pass_b_y.next = partial_b

            proclist.append(alu_proc_pass_b)

        # extra operations (if defined)
        for extra_op_name, extra_op_cb in self._extraops.items():
            extra_y = mux_ports[f"in{op_map[extra_op_name]}"]
            proclist.append(extra_op_cb(partial_a, partial_b, extra_y))

        if use_lt:

            @always_comb
            def alu_lt_compute():
                # signed compare without a helper: MyHDL turns a helper's
                # ``return`` into a Verilog ``function`` with ``disable``, which
                # Yosys rejects.  Compare sign bits first, then fall back.
                if partial_a[width - 1] != partial_b[width - 1]:
                    partial_lt.next = partial_a[width - 1]
                else:
                    partial_lt.next = partial_a < partial_b

            proclist.append(alu_lt_compute)

        if use_ltu:

            @always_comb
            def alu_ltu_compute():
                if partial_a < partial_b:
                    partial_ltu.next = 1
                else:
                    partial_ltu.next = 0

            proclist.append(alu_ltu_compute)

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
            reset_value = self._params["reset_value"] & ((1 << width) - 1)

            # Synchronous reset; polarity from the ResetSignal's active level.
            active = int(ports.reset.active)

            # NOTE: @always_seq is not detecting the reset functionality,
            # Changing back to @always decorator
            if self._params["en"]:

                @always(ports.clk.posedge)
                def alu_reg_output():
                    if ports.reset == active:
                        ports.y.next = reset_value
                    elif ports.en:
                        ports.y.next = partial_y[width:]

            else:

                @always(ports.clk.posedge)
                def alu_reg_output():
                    if ports.reset == active:
                        ports.y.next = reset_value
                    else:
                        ports.y.next = partial_y[width:]

        else:

            @always_comb
            def alu_reg_output():
                ports.y.next = partial_y[width:]

        proclist.append(alu_reg_output)

        return proclist
