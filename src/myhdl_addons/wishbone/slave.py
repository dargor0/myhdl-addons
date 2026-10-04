"""Classic Wishbone slave helper.

Implements ``WB-FR-030`` (classic slave, ``ACK`` per spec, granularity-aware
read/write) and ``WB-FR-032`` (zero-wait-state by default).  The helper
handles the bus handshake and exposes strobes/data to the peripheral logic:

    inputs : read_data  (value returned on a read)
    outputs: wr         (write strobe)
             rd         (read strobe)
             wr_data    (= dat_i during a write)
             wr_sel     (= sel during a write)

The peripheral drives ``read_data`` and consumes ``wr``/``rd``.  For simple
memory-mapped registers prefer :mod:`myhdl_addons.wishbone.regfile`.
"""

from myhdl import SignalType, always_comb, block

from .interface import SlaveView

__all__ = ["wishbone_slave"]


@block
def wishbone_slave(
    wb: SlaveView,
    read_data: SignalType,
    wr: SignalType,
    rd: SignalType,
    wr_data: SignalType,
    wr_sel: SignalType,
):
    """A zero-wait-state classic Wishbone slave.

    Args:
        wb: a :class:`~myhdl_addons.wishbone.interface.SlaveView`.
        read_data: signal driven by the peripheral for read cycles.
        wr, rd: write/read strobe outputs (comb, active during the cycle).
        wr_data, wr_sel: captured write data and byte-select outputs.
    """
    err_o = wb.err_o

    if err_o is not None:

        @always_comb
        def handshake():
            active = wb.cyc_i and wb.stb_i
            wb.ack_o.next = active
            wr.next = active and wb.we_i
            rd.next = active and (not wb.we_i)
            wr_data.next = wb.dat_i
            wr_sel.next = wb.sel_i
            wb.dat_o.next = read_data
            err_o.next = 0

    else:

        @always_comb
        def handshake():
            active = wb.cyc_i and wb.stb_i
            wb.ack_o.next = active
            wr.next = active and wb.we_i
            rd.next = active and (not wb.we_i)
            wr_data.next = wb.dat_i
            wr_sel.next = wb.sel_i
            wb.dat_o.next = read_data

    return handshake
