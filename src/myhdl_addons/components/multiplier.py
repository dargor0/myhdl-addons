"""Multiplier components (``MD-FR-001..034``).

Two independent synthesizable multipliers:

* :class:`Multiplier` — pure combinational; produces the full ``2*width``-bit
  product.  ``impl="dsp"`` (default) is a portable ``a * b`` so vendor tools
  infer an FPGA hard multiplier; ``impl="luts"`` is a soft partial-product
  array with no ``*`` (LUTs only).
* :class:`SequentialMultiplier` — radix-2/radix-4 shift-and-add; LUTs + a
  small adder, one ``a * b`` result every ``ceil(width / log2(radix))`` cycles.

Multiplication is always performed on the raw bit patterns (a plain unsigned
``*`` / partial-product sum), so the ``*`` maps to the (unsigned) hard
multiplier; two's-complement results are obtained by an explicit sign
correction (``signed=True``) rather than signed signal arithmetic.
"""

from myhdl import ResetSignal, Signal, always, always_comb, block, concat, intbv

from ..common.config import (
    ComponentBase,
    check_bool,
    check_choice,
    check_non_negative,
    check_positive,
)
from ..common.reset import make_reset
from ..common.views import SignalView

__all__ = [
    "AVAIL_DSP_TYPES",
    "AVAIL_MUL_IMPL",
    "AVAIL_RADIX",
    "Multiplier",
    "SequentialMultiplier",
]

#: Selectable implementation styles for :class:`Multiplier`.
AVAIL_MUL_IMPL = ("dsp", "luts")

#: Optional target hard-multiplier shapes (``dsptype``).
AVAIL_DSP_TYPES = ("9x9", "18x18", "25x18", "27x18")

#: Chunk width used when decomposing a multiply for a given ``dsptype``.
_DSP_CHUNK = {"9x9": 9, "18x18": 18, "25x18": 18, "27x18": 18}

#: Supported sequential radices (bits of the multiplier consumed per cycle).
AVAIL_RADIX = (2, 4)

_RADIX_SHIFT = {2: 1, 4: 2}


def _chunk_specs(width: int, chunk: int) -> list[tuple[int, int]]:
    """Return ``(bit_offset, size)`` for each ``chunk``-wide slice of *width*."""
    specs = []
    lo = 0
    while lo < width:
        size = min(chunk, width - lo)
        specs.append((lo, size))
        lo += size
    return specs


# -- convertible leaf stages ----------------------------------------------


@block
def mul_mul(x, y, out):
    """``out = x * y`` (the single multiply a tool maps to a hard multiplier)."""

    @always_comb
    def p():
        out.next = x * y

    return p


@block
def mul_add(x, y, out):
    """``out = x + y`` (wraps in *out*'s width)."""

    @always_comb
    def p():
        out.next = x + y

    return p


@block
def mul_slice(src, hi, lo, out):
    """``out = src[hi:lo]`` (a constant-width slice of a signal)."""

    @always_comb
    def p():
        out.next = src[hi:lo]

    return p


@block
def mul_shift(x, amount, out):
    """``out = x << amount`` with *x* already widened to *out*'s width."""

    @always_comb
    def p():
        out.next = x << amount

    return p


@block
def mul_pp(a, b, i, amount, out):
    """Soft-array partial product: ``out = (a << amount) if b[i] else 0``."""

    @always_comb
    def p():
        if b[i]:
            out.next = a << amount
        else:
            out.next = 0

    return p


@block
def sum_tree(terms, out, width):
    """Balanced adder tree reducing the non-empty *terms* into *out*.

    Every partial sum wraps in ``width`` bits (``mod 2**width``), which is what
    a two's-complement product needs.
    """
    procs = []
    level = list(terms)
    while len(level) > 1:
        nxt = []
        i = 0
        while i < len(level):
            if i + 1 == len(level):
                nxt.append(level[i])
            else:
                node = out if len(level) == 2 else Signal(intbv(0)[width:])
                procs.append(mul_add(level[i], level[i + 1], node))
                nxt.append(node)
            i += 2
        level = nxt
    if level[0] is not out:
        single = level[0]

        @always_comb
        def copy_first():
            out.next = single

        procs.append(copy_first)
    return procs


class Multiplier(ComponentBase):
    """Combinational multiplier (``MD-FR-001..007``).

    Args:
        width: operand width (both ``a`` and ``b``); the product ``y`` is
            ``2*width`` bits.
        signed: two's-complement operand/product interpretation (default).
        impl: ``"dsp"`` (portable ``*``, tool-infers a hard multiplier) or
            ``"luts"`` (soft partial-product array, no ``*``).
        dsptype: optional target hard-multiplier shape for ``impl="dsp"``
            (``"9x9"`` / ``"18x18"`` / ``"25x18"`` / ``"27x18"``); ``None`` lets
            the tool choose.  Ignored for ``impl="luts"``.
    """

    def __init__(
        self,
        width: int = 18,
        signed: bool = True,
        impl: str = "dsp",
        dsptype: str | None = None,
    ) -> None:
        p_width = int(check_positive(width, "width"))
        p_impl = check_choice(impl, AVAIL_MUL_IMPL, "impl")
        p_dsptype = (
            None
            if dsptype is None
            else check_choice(dsptype, AVAIL_DSP_TYPES, "dsptype")
        )
        self._params = {
            "width": p_width,
            "signed": check_bool(signed, "signed"),
            "impl": p_impl,
            "dsptype": p_dsptype,
        }

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        width = self._params["width"]
        return SignalView(
            a=Signal(intbv(0)[width:]),
            b=Signal(intbv(0)[width:]),
            y=Signal(intbv(0)[2 * width :]),
        )

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the multiplier onto *ports* and return its instances."""
        width = self._params["width"]
        signed = self._params["signed"]
        impl = self._params["impl"]
        dsptype = self._params["dsptype"]
        fw = 2 * width
        full = (1 << fw) - 1

        a = ports.a
        b = ports.b
        prod_u = Signal(intbv(0)[fw:])
        proclist = []

        if impl == "luts":
            a_wide = Signal(intbv(0)[fw:])

            @always_comb
            def widen_a():
                a_wide.next = a

            proclist.append(widen_a)
            terms = []
            for i in range(width):
                term = Signal(intbv(0)[fw:])
                proclist.append(mul_pp(a_wide, b, i, i, term))
                terms.append(term)
            proclist.append(sum_tree(terms, prod_u, fw))
        else:
            chunk = None if dsptype is None else _DSP_CHUNK[dsptype]
            if chunk is None or width <= chunk:
                proclist.append(mul_mul(a, b, prod_u))
            else:
                a_chunks = []
                for lo, size in _chunk_specs(width, chunk):
                    sig = Signal(intbv(0)[size:])
                    proclist.append(mul_slice(a, lo + size, lo, sig))
                    a_chunks.append((lo, sig))
                b_chunks = []
                for lo, size in _chunk_specs(width, chunk):
                    sig = Signal(intbv(0)[size:])
                    proclist.append(mul_slice(b, lo + size, lo, sig))
                    b_chunks.append((lo, sig))
                terms = []
                for lo_a, ca in a_chunks:
                    for lo_b, cb in b_chunks:
                        partial = Signal(intbv(0)[fw:])
                        term = Signal(intbv(0)[fw:])
                        proclist.append(mul_mul(ca, cb, partial))
                        proclist.append(mul_shift(partial, lo_a + lo_b, term))
                        terms.append(term)
                proclist.append(sum_tree(terms, prod_u, fw))

        if signed:
            shifted_a = Signal(intbv(0)[fw:])
            shifted_b = Signal(intbv(0)[fw:])

            @always_comb
            def sign_extend():
                shifted_a.next = concat(a, intbv(0)[width:])
                shifted_b.next = concat(b, intbv(0)[width:])

            corr_hi = Signal(intbv(0)[fw:])

            @always_comb
            def sign_corr_a():
                if a[width - 1]:
                    corr_hi.next = (prod_u - shifted_b) & full
                else:
                    corr_hi.next = prod_u

            @always_comb
            def sign_corr_b():
                if b[width - 1]:
                    ports.y.next = (corr_hi - shifted_a) & full
                else:
                    ports.y.next = corr_hi

            proclist += [sign_extend, sign_corr_a, sign_corr_b]
        else:

            @always_comb
            def unsigned_out():
                ports.y.next = prod_u

            proclist.append(unsigned_out)

        return proclist


@block
def seq_addend(radix, areg, breg, addend):
    """Radix-k partial addend: ``{0, A, 2A, 3A}`` selected by ``breg`` bits."""

    if radix == 2:

        @always_comb
        def p():
            if breg[0]:
                addend.next = areg
            else:
                addend.next = 0

    else:

        @always_comb
        def p():
            if breg[1]:
                if breg[0]:
                    addend.next = areg + (areg << 1)  # 3A
                else:
                    addend.next = areg << 1  # 2A
            else:
                if breg[0]:
                    addend.next = areg  # A
                else:
                    addend.next = 0

    return p


class SequentialMultiplier(ComponentBase):
    """Shift-and-add sequential multiplier (``MD-FR-020..025``).

    Args:
        width: operand width (both ``a`` and ``b``); ``y`` is ``2*width`` bits.
        signed: two's-complement interpretation.
        radix: bits of the multiplier consumed per cycle (``2`` or ``4``).
        en: add a clock enable that stalls the iteration.
        reset_value: value driven on ``y`` after reset.
        reset_signal: reuse a specific ``ResetSignal``, or ``None`` to create one.
    """

    def __init__(
        self,
        width: int = 18,
        signed: bool = True,
        radix: int = 2,
        en: bool = False,
        reset_value: int = 0,
        reset_signal: ResetSignal | None = None,
    ) -> None:
        p_width = int(check_positive(width, "width"))
        p_radix = check_choice(radix, AVAIL_RADIX, "radix")
        fw = 2 * p_width
        self._params = {
            "width": p_width,
            "signed": check_bool(signed, "signed"),
            "radix": p_radix,
            "en": check_bool(en, "en"),
            "reset_value": check_non_negative(reset_value, "reset_value")
            & ((1 << fw) - 1),
            "reset_signal": make_reset(reset_signal),
        }

    @property
    def iterations(self) -> int:
        """Number of shift-and-add iterations (``ceil(width / log2(radix))``)."""
        width = self._params["width"]
        shift = _RADIX_SHIFT[self._params["radix"]]
        return (width + shift - 1) // shift

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        width = self._params["width"]
        sig = {
            "clk": Signal(bool(0)),
            "reset": self._params["reset_signal"],
            "start": Signal(bool(0)),
            "a": Signal(intbv(0)[width:]),
            "b": Signal(intbv(0)[width:]),
            "y": Signal(intbv(0)[2 * width :]),
            "busy": Signal(bool(0)),
            "done": Signal(bool(0)),
        }
        if self._params["en"]:
            sig["en"] = Signal(bool(0))
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the multiplier onto *ports* and return its instances."""
        width = self._params["width"]
        signed = self._params["signed"]
        radix = self._params["radix"]
        has_en = self._params["en"]
        reset_value = self._params["reset_value"]
        shift = _RADIX_SHIFT[radix]
        niter = self.iterations
        fw = 2 * width
        full = (1 << fw) - 1
        active = int(self._params["reset_signal"].active)

        acc = Signal(intbv(0)[fw:])
        areg = Signal(intbv(0)[fw:])
        breg = Signal(intbv(0)[width:])
        # Guard bits: radix-4 forms 3*A and the running sum can exceed 2*width;
        # only the low 2*width bits are architecturally relevant (mod 2**(2*width)).
        addend = Signal(intbv(0)[fw + 2 :])
        sum_next = Signal(intbv(0)[fw + 2 :])
        prod = Signal(intbv(0)[fw:])
        count = Signal(intbv(0, min=0, max=max(2, niter)))

        proclist = [seq_addend(radix, areg, breg, addend)]

        @always_comb
        def sum_proc():
            sum_next.next = acc + addend

        proclist.append(sum_proc)

        if signed:
            # Original operands are captured only for the two's-complement
            # correction; unsigned multipliers omit them entirely.
            a_lat = Signal(intbv(0)[width:])
            b_lat = Signal(intbv(0)[width:])
            shifted_a = Signal(intbv(0)[fw:])
            shifted_b = Signal(intbv(0)[fw:])
            corr_hi = Signal(intbv(0)[fw:])

            @always_comb
            def sign_extend():
                shifted_a.next = concat(a_lat, intbv(0)[width:])
                shifted_b.next = concat(b_lat, intbv(0)[width:])

            @always_comb
            def sign_corr_a():
                if a_lat[width - 1]:
                    corr_hi.next = (sum_next - shifted_b) & full
                else:
                    corr_hi.next = sum_next

            @always_comb
            def sign_corr_b():
                if b_lat[width - 1]:
                    prod.next = (corr_hi - shifted_a) & full
                else:
                    prod.next = corr_hi

            @always(ports.clk.posedge)
            def sign_capture():
                if ports.reset == active:
                    a_lat.next = 0
                    b_lat.next = 0
                else:
                    if not ports.busy and ports.start:
                        a_lat.next = ports.a
                        b_lat.next = ports.b

            proclist += [sign_extend, sign_corr_a, sign_corr_b, sign_capture]
        else:

            @always_comb
            def unsigned_prod():
                prod.next = sum_next & full

            proclist.append(unsigned_prod)

        if has_en:

            @always(ports.clk.posedge)
            def fsm():
                if ports.reset == active:
                    ports.busy.next = 0
                    ports.done.next = 0
                    ports.y.next = reset_value
                    count.next = 0
                    acc.next = 0
                    areg.next = 0
                    breg.next = 0
                else:
                    ports.done.next = 0
                    if not ports.busy:
                        if ports.start:
                            areg.next = ports.a
                            breg.next = ports.b
                            acc.next = 0
                            count.next = 0
                            ports.busy.next = 1
                    elif ports.en:
                        acc.next = sum_next & full
                        areg.next = (areg << shift) & full
                        breg.next = breg >> shift
                        if count == niter - 1:
                            ports.y.next = prod
                            ports.done.next = 1
                            ports.busy.next = 0
                            count.next = 0
                        else:
                            count.next = count + 1

        else:

            @always(ports.clk.posedge)
            def fsm():
                if ports.reset == active:
                    ports.busy.next = 0
                    ports.done.next = 0
                    ports.y.next = reset_value
                    count.next = 0
                    acc.next = 0
                    areg.next = 0
                    breg.next = 0
                else:
                    ports.done.next = 0
                    if not ports.busy:
                        if ports.start:
                            areg.next = ports.a
                            breg.next = ports.b
                            acc.next = 0
                            count.next = 0
                            ports.busy.next = 1
                    else:
                        acc.next = sum_next & full
                        areg.next = (areg << shift) & full
                        breg.next = breg >> shift
                        if count == niter - 1:
                            ports.y.next = prod
                            ports.done.next = 1
                            ports.busy.next = 0
                            count.next = 0
                        else:
                            count.next = count + 1

        proclist.append(fsm)
        return proclist
