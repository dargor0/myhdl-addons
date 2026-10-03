"""Address-window decoder (``IC-FR-089..095``).

Combinational, bus-agnostic decoder: given an address and a list of
non-overlapping ``(base, size)`` windows, assert exactly the matching
``selects[i]``.  It is the reusable primitive behind a bus address decoder
(``reqs/00`` ``CB-FR-060..062``).

Convertibility shapes the implementation: one small ``@always_comb`` process
compares the address against each window's elaboration-time bounds, and an
optional output register stage (``IC-FR-128``) reuses the library's uniform
``clk``/``reset``/``reset_value`` model.
"""

from myhdl import ResetSignal, Signal, always, always_comb, block, intbv

from ..common.config import (
    ComponentBase,
    check_bool,
    check_non_negative,
    check_positive,
    check_registered,
    mask,
)
from ..common.errors import HdlConfigError
from ..common.views import SignalView

__all__ = ["AddressDecoder"]


def _check_windows(windows, adr_width: int) -> tuple[tuple[int, int], ...]:
    """Validate and canonicalise the ``(base, size)`` window list."""
    if windows is None:
        raise HdlConfigError("windows must be provided")
    try:
        entries = tuple(windows)
    except TypeError:
        raise HdlConfigError(
            f"windows must be an iterable of (base, size), got {windows!r}"
        )
    if not entries:
        raise HdlConfigError("windows must not be empty")
    limit = 1 << adr_width
    result: list[tuple[int, int]] = []
    for entry in entries:
        if not isinstance(entry, (tuple, list)) or len(entry) != 2:
            raise HdlConfigError(f"window must be a (base, size) pair, got {entry!r}")
        base = check_non_negative(entry[0], "window base")
        size = check_positive(entry[1], "window size")
        if base + size > limit:
            raise HdlConfigError(
                f"window [{base:#x}, {base + size:#x}) exceeds the "
                f"{adr_width}-bit address space"
            )
        result.append((base, size))
    for i, (base_i, size_i) in enumerate(result):
        for base_j, size_j in result[i + 1 :]:
            if base_i < base_j + size_j and base_j < base_i + size_i:
                raise HdlConfigError(
                    f"windows [{base_i:#x}, {base_i + size_i:#x}) and "
                    f"[{base_j:#x}, {base_j + size_j:#x}) overlap"
                )
    return tuple(result)


@block
def ad_match(adr, base, end, en, dst, has_en):
    """One window match: assert ``dst`` while ``base <= adr < end``."""

    if has_en:

        @always_comb
        def p():
            if en:
                if (int(adr) >= base) and (int(adr) < end):
                    dst.next = 1
                else:
                    dst.next = 0
            else:
                dst.next = 0

    else:

        @always_comb
        def p():
            if (int(adr) >= base) and (int(adr) < end):
                dst.next = 1
            else:
                dst.next = 0

    return p


@block
def ad_valid(selects, valid, n):
    """``valid`` is asserted while any select is asserted."""

    # NOTE: always_comb does not see signals hidden in a tuple; use an explicit
    # sensitivity list (as OneHotMux does).
    @always(*selects)
    def p():
        any_sel = 0
        for i in range(n):
            if selects[i]:
                any_sel = 1
        if any_sel:
            valid.next = 1
        else:
            valid.next = 0

    return p


@block
def ad_bool_reg(d, q, clk, reset, reset_val):
    """Registered select/valid stage (resets to the constant ``reset_val``)."""

    @always(clk.posedge)
    def p():
        if not reset:
            q.next = d
        else:
            q.next = reset_val

    return p


class AddressDecoder(ComponentBase):
    """Bus-agnostic address-window decoder (``IC-FR-089..095``).

    Args:
        adr_width: address width.
        windows: non-empty list of non-overlapping ``(base, size)`` pairs;
            window ``i`` drives ``selects[i]``.
        en: add an ``en`` input (all-zero selects when low).
        valid: expose a ``valid`` output (any window matched and enabled).
        registered: output register latency (``0``/``1``).
        reset_value: registered reset bitmap for ``selects`` (default 0).
        reset_signal: reuse a specific ``ResetSignal``, or ``None`` to create one.
    """

    def __init__(
        self,
        adr_width: int = 32,
        windows=None,
        en: bool = False,
        valid: bool = False,
        registered: int = 0,
        reset_value: int = 0,
        reset_signal: ResetSignal | None = None,
    ) -> None:
        p_adr_width = int(check_positive(adr_width, "adr_width"))
        p_windows = _check_windows(windows, p_adr_width)
        self._params = {
            "adr_width": p_adr_width,
            "windows": p_windows,
            "en": check_bool(en, "en"),
            "valid": check_bool(valid, "valid"),
            "registered": check_registered(registered),
            "reset_value": check_non_negative(reset_value, "reset_value")
            & mask(len(p_windows)),
            "reset_signal": reset_signal
            if isinstance(reset_signal, ResetSignal)
            else None,
        }

    @property
    def num_windows(self) -> int:
        """Number of address windows (the width of ``selects``)."""
        return len(self._params["windows"])

    def ports(self) -> SignalView:
        """Allocate and return the component interface.

        Each window gets its own named ``sel{i}`` output (one
        ``Signal(bool)`` per window); exposing them as a tuple confuses MyHDL's
        hierarchy/port handling, so individual ports are used as elsewhere in
        the library (``we0``/``rdata0``/...).
        """
        n = self.num_windows
        sig = {"adr": Signal(intbv(0)[self._params["adr_width"] :])}
        for i in range(n):
            sig[f"sel{i}"] = Signal(bool(0))
        if self._params["en"]:
            sig["en"] = Signal(bool(0))
        if self._params["valid"]:
            sig["valid"] = Signal(bool(0))
        if self._params["registered"]:
            sig["clk"] = Signal(bool(0))
            if self._params["reset_signal"] is None:
                self._params["reset_signal"] = ResetSignal(0, active=0, isasync=False)
            sig["reset"] = self._params["reset_signal"]
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the decoder onto *ports* and return its instances."""
        params = self._params
        windows = params["windows"]
        has_en = params["en"]
        has_valid = params["valid"]
        registered = params["registered"]
        reset_value = params["reset_value"]
        n = len(windows)

        proclist = []
        sels = tuple(ports[f"sel{i}"] for i in range(n))
        comb = tuple(Signal(bool(0)) for _ in range(n)) if registered else sels
        en = ports.en if has_en else None

        for i, (base, size) in enumerate(windows):
            proclist.append(ad_match(ports.adr, base, base + size, en, comb[i], has_en))

        valid_comb = None
        if has_valid:
            valid_comb = ports.valid if not registered else Signal(bool(0))
            proclist.append(ad_valid(comb, valid_comb, n))

        if registered:
            for i in range(n):
                proclist.append(
                    ad_bool_reg(
                        comb[i],
                        sels[i],
                        ports.clk,
                        ports.reset,
                        (reset_value >> i) & 1,
                    )
                )
            if has_valid:
                proclist.append(
                    ad_bool_reg(valid_comb, ports.valid, ports.clk, ports.reset, 0)
                )

        return proclist
