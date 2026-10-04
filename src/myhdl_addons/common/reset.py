"""Uniform reset-signal handling shared by the synthesizable blocks.

Every clocked block exposes its reset as a port named ``reset`` holding a
:class:`myhdl.ResetSignal`.  The **active level** is taken from the
``ResetSignal`` object (``active``), so a design can use either polarity, while
the reset is **always synchronous** and **active-low by default**
(``ResetSignal(0, active=0, isasync=False)``).  Asynchronous resets (or values
that are not ``ResetSignal`` objects) raise at construction.
"""

from myhdl import ResetSignal

from .errors import HdlConfigError, HdlTypeError

__all__ = ["make_reset"]


def make_reset(reset_signal: ResetSignal | None = None) -> ResetSignal:
    """Return a validated synchronous *reset_signal*, defaulting to active-low.

    Args:
        reset_signal: an optional externally supplied :class:`myhdl.ResetSignal`.

    Raises:
        HdlTypeError: if *reset_signal* is not a ``ResetSignal``.
        HdlConfigError: if *reset_signal* is asynchronous (``isasync`` true).
    """
    if reset_signal is None:
        return ResetSignal(0, active=0, isasync=False)
    if not isinstance(reset_signal, ResetSignal):
        raise HdlTypeError("reset_signal must be a myhdl.ResetSignal")
    if reset_signal.isasync:
        raise HdlConfigError("reset must be synchronous (isasync=False)")
    return reset_signal
