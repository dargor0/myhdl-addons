"""Barrel shifter (``IC-FR-030..039``).

Supports logical/arithmetic shifts and rotates with a selectable mode subset,
three implementation structures, three shift-amount behaviours and an
optional constant shift amount.

Convertibility is the reason for the shape of this file: a runtime shift amount
is decomposed into a chain of small stages, each of which shifts by a *constant*
amount (``1 << k`` for the bit-sliced structures, ``1`` for ``serial``).  Every
stage is its own tiny ``@always_comb`` process, and an optional registered
output stage reuses the same priority as the rest of the library.
"""

from myhdl import (
    ResetSignal,
    Signal,
    SignalType,
    always,
    always_comb,
    block,
    concat,
    intbv,
)

from ..common.config import (
    ComponentBase,
    ceil_log2,
    check_bool,
    check_choice,
    check_non_negative,
    check_positive,
    check_registered,
    mask,
    normalize_subset,
)
from ..common.views import SignalView

__all__ = [
    "MODES",
    "MODE_NAMES",
    "ROL",
    "ROR",
    "SLL",
    "SRA",
    "SRL",
    "STRUCTURES",
    "BarrelShifter",
]

SLL, SRL, SRA, ROL, ROR = range(5)

MODES = (SLL, SRL, SRA, ROL, ROR)

MODE_NAMES = {SLL: "SLL", SRL: "SRL", SRA: "SRA", ROL: "ROL", ROR: "ROR"}

STRUCTURES = ("logarithmic", "two_stage", "serial")
SHAMT_MODES = ("modulo", "saturate", "zero")


@block
def wide_extend(data, sx, width, full):
    """Sign-extend ``data`` into the ``2 * width`` bit signal ``sx``."""

    @always_comb
    def ext():
        if data[width - 1]:
            sx.next = concat(intbv(full)[width:], data)
        else:
            sx.next = concat(intbv(0)[width:], data)

    return ext


@block
def slice_ext(src, dst, width):
    """Drop the sign-extension (keep the low ``width`` bits of a wide value)."""

    @always_comb
    def p():
        dst.next = src[width:]

    return p


@block
def reg_stage(d, q, clk, reset, en, reset_value):
    """Registered output stage: reset > en-hold > capture."""

    @always(clk.posedge)
    def logic():
        if not reset:
            if en:
                q.next = d
        else:
            q.next = reset_value

    return logic


@block
def bit_step(mode, src, dst, amt, k, amount, width, full):
    """Conditional shift by the constant ``amount`` gated by shamt bit ``k``.

    ``src``/``dst`` are ``width`` bits, except for ``SRA`` where they are
    ``2 * width`` bits holding a sign-extended value.
    """

    if mode == SLL:

        @always_comb
        def step():
            if amt[k]:
                dst.next = (src << amount) & full
            else:
                dst.next = src

    elif mode in (SRL, SRA):

        @always_comb
        def step():
            if amt[k]:
                dst.next = src >> amount
            else:
                dst.next = src

    elif mode == ROL:

        @always_comb
        def step():
            if amt[k]:
                dst.next = ((src << amount) | (src >> (width - amount))) & full
            else:
                dst.next = src

    else:  # ROR

        @always_comb
        def step():
            if amt[k]:
                dst.next = ((src >> amount) | (src << (width - amount))) & full
            else:
                dst.next = src

    return step


@block
def unit_step(mode, src, dst, amt, j, width, full):
    """Conditional single-bit shift, applied while the amount exceeds ``j``.

    A ``serial`` shifter is a cascade of these; each stage contributes one unit
    of shift when ``amt > j``.
    """

    if mode == SLL:

        @always_comb
        def step():
            if int(amt) > j:
                dst.next = (src << 1) & full
            else:
                dst.next = src

    elif mode in (SRL, SRA):

        @always_comb
        def step():
            if int(amt) > j:
                dst.next = src >> 1
            else:
                dst.next = src

    elif mode == ROL:

        @always_comb
        def step():
            if int(amt) > j:
                dst.next = ((src << 1) | (src >> (width - 1))) & full
            else:
                dst.next = src

    else:  # ROR

        @always_comb
        def step():
            if int(amt) > j:
                dst.next = ((src >> 1) | (src << (width - 1))) & full
            else:
                dst.next = src

    return step


@block
def const_step(mode, src, dst, amount, width, full):
    """Unconditional shift by the elaboration-time constant ``amount``."""

    if mode == SLL:

        @always_comb
        def step():
            dst.next = (src << amount) & full

    elif mode in (SRL, SRA):

        @always_comb
        def step():
            dst.next = src >> amount

    elif mode == ROL:

        @always_comb
        def step():
            dst.next = ((src << amount) | (src >> (width - amount))) & full

    else:  # ROR

        @always_comb
        def step():
            dst.next = ((src >> amount) | (src << (width - amount))) & full

    return step


@block
def runtime_output(mode, shamt_mode, part, last, data, oor, width, full):
    """Runtime out-of-range override for ``zero``/``saturate`` (reads ``oor``).

    ``zero`` forces ``0``; ``saturate`` clamps per mode (sign fill for ``SRA``,
    unchanged data for rotates, ``0`` for logical shifts).
    """

    if shamt_mode == "zero":

        @always_comb
        def out():
            if oor:
                part.next = 0
            else:
                part.next = last

    elif mode == SRA:

        @always_comb
        def out():
            if oor:
                if data[width - 1]:
                    part.next = full
                else:
                    part.next = 0
            else:
                part.next = last

    elif mode in (ROL, ROR):

        @always_comb
        def out():
            if oor:
                part.next = data
            else:
                part.next = last

    else:  # SLL / SRL

        @always_comb
        def out():
            if oor:
                part.next = 0
            else:
                part.next = last

    return out


@block
def sra_const_output(part, data, width, full):
    """Constant out-of-range ``saturate`` clamp for ``SRA`` (sign fill)."""

    @always_comb
    def out():
        if data[width - 1]:
            part.next = full
        else:
            part.next = 0

    return out


class BarrelShifter(ComponentBase):
    """Configurable barrel shifter (``IC-FR-030..039``).

    Args:
        width: datapath width.
        modes: enabled mode subset (default all of ``MODES``).
        structure: ``logarithmic`` / ``two_stage`` / ``serial``.
        registered: output register latency (``0``/``1``).
        en: add an output enable when registered.
        reset_value: registered reset value for ``y``.
        reset_signal: reuse a specific ``ResetSignal``, or ``None`` to create one.
        shamt_const: fixed shift amount; when set the ``shamt`` port is omitted.
        shamt_bits: shift-amount port width (default ``ceil(log2 width)``).
        shamt_mode: ``modulo`` / ``saturate`` / ``zero``.
    """

    def __init__(
        self,
        width: int = 32,
        modes=None,
        structure: str = "logarithmic",
        registered: int = 0,
        en: bool = False,
        reset_value: int = 0,
        reset_signal: ResetSignal | None = None,
        shamt_const: int | None = None,
        shamt_bits: int | None = None,
        shamt_mode: str = "modulo",
    ) -> None:
        p_width = int(check_positive(width, "width"))
        p_modes = normalize_subset(
            modes, MODES, "modes", default=MODES, names=MODE_NAMES
        )
        p_structure = check_choice(structure, STRUCTURES, "structure")
        p_registered = check_registered(registered)
        p_en = check_bool(en, "en")
        p_reset_value = check_non_negative(reset_value, "reset_value") & mask(p_width)
        p_reset_signal = reset_signal if isinstance(reset_signal, ResetSignal) else None
        if shamt_const is not None:
            p_shamt_const = check_non_negative(shamt_const, "shamt_const")
        else:
            p_shamt_const = None
        if shamt_bits is None:
            p_shamt_bits = max(1, ceil_log2(p_width))
        else:
            p_shamt_bits = check_positive(shamt_bits, "shamt_bits")
        p_shamt_mode = check_choice(shamt_mode, SHAMT_MODES, "shamt_mode")

        self._params = {
            "width": p_width,
            "modes": p_modes,
            "structure": p_structure,
            "registered": p_registered,
            "en": p_en,
            "reset_value": p_reset_value,
            "reset_signal": p_reset_signal,
            "shamt_const": p_shamt_const,
            "shamt_bits": p_shamt_bits,
            "shamt_mode": p_shamt_mode,
        }

    @property
    def shamt_bits(self) -> int:
        """Physical/base width of the shift amount."""
        return self._params["shamt_bits"]

    @property
    def shamt_width(self) -> int:
        """Physical width of the ``shamt`` port (``saturate`` uses one extra bit)."""
        extra = 1 if self._params["shamt_mode"] == "saturate" else 0
        return self._params["shamt_bits"] + extra

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        width = self._params["width"]
        sig = {
            "data": Signal(intbv(0)[width:]),
            "mode": Signal(intbv(0, min=0, max=8)),
            "y": Signal(intbv(0)[width:]),
        }
        if self._params["shamt_const"] is None:
            sig["shamt"] = Signal(intbv(0, min=0, max=1 << self.shamt_width))
        if self._params["registered"]:
            sig["clk"] = Signal(bool(0))
            if self._params["reset_signal"] is None:
                self._params["reset_signal"] = ResetSignal(0, active=0, isasync=False)
            sig["reset"] = self._params["reset_signal"]
            if self._params["en"]:
                sig["en"] = Signal(bool(0))
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the shifter onto *ports* and return its instances."""
        width = self._params["width"]
        modes = self._params["modes"]
        structure = self._params["structure"]
        shamt_mode = self._params["shamt_mode"]
        shamt_const = self._params["shamt_const"]
        nbits = self._params["shamt_bits"]
        registered = self._params["registered"]
        full = mask(width)
        wide = 2 * width

        proclist = []

        # --- effective shift-amount source and out-of-range handling ---
        oor = None
        const_shift = None
        if shamt_const is not None:
            const_oor = shamt_mode != "modulo" and shamt_const >= width
            const_shift = (
                shamt_const & (width - 1) if shamt_mode == "modulo" else shamt_const
            )
            override = "none" if shamt_mode == "modulo" or not const_oor else "const"
        else:
            if shamt_mode == "modulo":
                masked = Signal(intbv(0)[self.shamt_width :])
                amt = masked

                @always_comb
                def amt_proc():
                    masked.next = ports.shamt & (width - 1)

                proclist.append(amt_proc)
            else:
                amt = ports.shamt
                oor = Signal(bool(0))

                @always_comb
                def oor_proc():
                    oor.next = int(ports.shamt) >= width

                proclist.append(oor_proc)
            override = "none" if shamt_mode == "modulo" else "runtime"

        # --- per-mode datapath + final value ---
        # A runtime amount is decomposed into a chain of constant-shift stages.
        # Each stage is its own small block; ``serial`` uses unit stages while
        # ``logarithmic``/``two_stage`` use ``1 << k`` stages.
        parts = []
        for mode in modes:
            stage_bits = wide if mode == SRA else width
            chain = []
            if mode == SRA:
                start = Signal(intbv(0)[wide:])
                chain.append(wide_extend(ports.data, start, width, full))
            else:
                start = ports.data
            cur = start

            if shamt_const is not None:
                if structure == "serial":
                    for _ in range(const_shift):
                        nxt = Signal(intbv(0)[stage_bits:])
                        chain.append(const_step(mode, cur, nxt, 1, width, full))
                        cur = nxt
                else:
                    for k in range(nbits):
                        if (const_shift >> k) & 1:
                            nxt = Signal(intbv(0)[stage_bits:])
                            chain.append(
                                const_step(mode, cur, nxt, 1 << k, width, full)
                            )
                            cur = nxt
            elif structure == "serial":
                for j in range(width):
                    nxt = Signal(intbv(0)[stage_bits:])
                    chain.append(unit_step(mode, cur, nxt, amt, j, width, full))
                    cur = nxt
            else:
                if structure == "two_stage":
                    half = nbits // 2
                    order = list(range(half, nbits)) + list(range(0, half))
                else:  # logarithmic
                    order = list(range(nbits))
                for k in order:
                    nxt = Signal(intbv(0)[stage_bits:])
                    chain.append(bit_step(mode, cur, nxt, amt, k, 1 << k, width, full))
                    cur = nxt

            if mode == SRA:
                last = Signal(intbv(0)[width:])
                chain.append(slice_ext(cur, last, width))
            else:
                last = cur

            proclist.extend(chain)

            if override == "none":
                source = last
            elif override == "runtime":
                part = Signal(intbv(0)[width:])
                proclist.append(
                    runtime_output(
                        mode, shamt_mode, part, last, ports.data, oor, width, full
                    )
                )
                source = part
            elif shamt_mode == "zero":
                source = 0
            elif mode == SRA:
                part = Signal(intbv(0)[width:])
                proclist.append(sra_const_output(part, ports.data, width, full))
                source = part
            elif mode in (ROL, ROR):
                source = ports.data
            else:  # SLL / SRL
                source = 0

            parts.append((mode, source))

        # --- mode select (canonical codes; disabled/unknown modes read 0) ---
        y_dst = ports.y if not registered else Signal(intbv(0)[width:])
        sources = {SLL: 0, SRL: 0, SRA: 0, ROL: 0, ROR: 0}
        part_list = []
        for mode, source in parts:
            sources[mode] = source
            if isinstance(source, SignalType):
                part_list.append(source)
        sll_src = sources[SLL]
        srl_src = sources[SRL]
        sra_src = sources[SRA]
        rol_src = sources[ROL]
        ror_src = sources[ROR]

        @always(ports.mode, *part_list)
        def mode_mux():
            if int(ports.mode) == SLL:
                y_dst.next = sll_src
            elif int(ports.mode) == SRL:
                y_dst.next = srl_src
            elif int(ports.mode) == SRA:
                y_dst.next = sra_src
            elif int(ports.mode) == ROL:
                y_dst.next = rol_src
            elif int(ports.mode) == ROR:
                y_dst.next = ror_src
            else:
                y_dst.next = 0

        proclist.append(mode_mux)

        if registered:
            en_sig = ports.en if self._params["en"] else Signal(bool(1))
            proclist.append(
                reg_stage(
                    y_dst,
                    ports.y,
                    ports.clk,
                    ports.reset,
                    en_sig,
                    self._params["reset_value"],
                )
            )

        return proclist
