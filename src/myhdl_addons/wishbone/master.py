"""Classic Wishbone master core.

Implements ``WB-FR-020`` (classic single read/write sequencing),
``WB-FR-022`` (simple convertible command interface) and ``WB-FR-023``
(``ERR``/``RTY`` handling).  ``WB-FR-025`` (convertibility) is a property
of the code style used throughout.

The command interface is intentionally simple:

    inputs : req, adr, we, dat_w, sel
    outputs: busy, done, dat_r, err

``req`` is sampled while ``busy`` is low; a new transaction starts on the
next clock edge.  ``done`` is a one-cycle pulse; ``dat_r``/``err`` are valid
with ``done``.

The optional ``ERR``/``RTY`` handling is selected at elaboration (based on
which optional signals the port exposes), so each FSM body stays within the
MyHDL convertible subset.
"""

from myhdl import SignalType, always, block

from .interface import MasterView

__all__ = ["wishbone_master"]


@block
def wishbone_master(
    wb: MasterView,
    req: SignalType,
    adr: SignalType,
    we: SignalType,
    dat_w: SignalType,
    sel: SignalType,
    busy: SignalType,
    done: SignalType,
    dat_r: SignalType,
    err: SignalType,
):
    """A classic Wishbone master.

    Args:
        wb: a :class:`~myhdl_addons.wishbone.interface.MasterView`.
        req, adr, we, dat_w, sel: command inputs.
        busy, done, dat_r, err: status/response outputs.
    """
    has_err = wb.err_i is not None
    has_rty = wb.rty_i is not None

    if has_rty and has_err:

        @always(wb.clk.posedge)
        def fsm():
            if wb.rst:
                wb.cyc_o.next = 0
                wb.stb_o.next = 0
                wb.we_o.next = 0
                busy.next = 0
                done.next = 0
                err.next = 0
            else:
                done.next = 0
                if not busy:
                    if req:
                        wb.adr_o.next = adr
                        wb.dat_o.next = dat_w
                        wb.we_o.next = we
                        wb.sel_o.next = sel
                        wb.cyc_o.next = 1
                        wb.stb_o.next = 1
                        busy.next = 1
                        err.next = 0
                else:
                    if wb.rty_i:
                        pass  # retry: keep the cycle active
                    elif wb.err_i:
                        wb.cyc_o.next = 0
                        wb.stb_o.next = 0
                        wb.we_o.next = 0
                        err.next = 1
                        done.next = 1
                        busy.next = 0
                    elif wb.ack_i:
                        wb.cyc_o.next = 0
                        wb.stb_o.next = 0
                        wb.we_o.next = 0
                        dat_r.next = wb.dat_i
                        done.next = 1
                        busy.next = 0

    elif has_rty:

        @always(wb.clk.posedge)
        def fsm():
            if wb.rst:
                wb.cyc_o.next = 0
                wb.stb_o.next = 0
                wb.we_o.next = 0
                busy.next = 0
                done.next = 0
                err.next = 0
            else:
                done.next = 0
                if not busy:
                    if req:
                        wb.adr_o.next = adr
                        wb.dat_o.next = dat_w
                        wb.we_o.next = we
                        wb.sel_o.next = sel
                        wb.cyc_o.next = 1
                        wb.stb_o.next = 1
                        busy.next = 1
                        err.next = 0
                else:
                    if wb.rty_i:
                        pass
                    elif wb.ack_i:
                        wb.cyc_o.next = 0
                        wb.stb_o.next = 0
                        wb.we_o.next = 0
                        dat_r.next = wb.dat_i
                        done.next = 1
                        busy.next = 0

    elif has_err:

        @always(wb.clk.posedge)
        def fsm():
            if wb.rst:
                wb.cyc_o.next = 0
                wb.stb_o.next = 0
                wb.we_o.next = 0
                busy.next = 0
                done.next = 0
                err.next = 0
            else:
                done.next = 0
                if not busy:
                    if req:
                        wb.adr_o.next = adr
                        wb.dat_o.next = dat_w
                        wb.we_o.next = we
                        wb.sel_o.next = sel
                        wb.cyc_o.next = 1
                        wb.stb_o.next = 1
                        busy.next = 1
                        err.next = 0
                else:
                    if wb.err_i:
                        wb.cyc_o.next = 0
                        wb.stb_o.next = 0
                        wb.we_o.next = 0
                        err.next = 1
                        done.next = 1
                        busy.next = 0
                    elif wb.ack_i:
                        wb.cyc_o.next = 0
                        wb.stb_o.next = 0
                        wb.we_o.next = 0
                        dat_r.next = wb.dat_i
                        done.next = 1
                        busy.next = 0

    else:

        @always(wb.clk.posedge)
        def fsm():
            if wb.rst:
                wb.cyc_o.next = 0
                wb.stb_o.next = 0
                wb.we_o.next = 0
                busy.next = 0
                done.next = 0
                err.next = 0
            else:
                done.next = 0
                if not busy:
                    if req:
                        wb.adr_o.next = adr
                        wb.dat_o.next = dat_w
                        wb.we_o.next = we
                        wb.sel_o.next = sel
                        wb.cyc_o.next = 1
                        wb.stb_o.next = 1
                        busy.next = 1
                        err.next = 0
                else:
                    if wb.ack_i:
                        wb.cyc_o.next = 0
                        wb.stb_o.next = 0
                        wb.we_o.next = 0
                        dat_r.next = wb.dat_i
                        done.next = 1
                        busy.next = 0

    return fsm
