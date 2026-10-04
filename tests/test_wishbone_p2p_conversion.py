"""Conversion smoke test for master + slave + point-to-point (Verilog + VHDL)."""

import pytest
from myhdl import Signal, always_comb, block, intbv

from myhdl_addons.wishbone import (
    PointToPoint,
    Wishbone,
    wishbone_master,
    wishbone_slave,
)


@block
def _p2p_top(
    clk,
    rst,
    req,
    adr,
    we,
    dat_w,
    sel,
    busy,
    done,
    dat_r,
    err,
    wr,
    rd,
    wr_data,
    wr_sel,
):
    bus = Wishbone(
        clk, rst, data_width=32, adr_width=16, gran=8, interconnect=PointToPoint()
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x100, name="per")

    core = wishbone_master(m, req, adr, we, dat_w, sel, busy, done, dat_r, err)
    read_data = Signal(intbv(0)[32:])
    slave = wishbone_slave(s, read_data, wr, rd, wr_data, wr_sel)

    @always_comb
    def tie_read_data():
        read_data.next = s.adr_i

    glue = bus.build()
    return core, slave, tie_read_data, glue


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_p2p_converts(hdl, convert_dut):
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    req = Signal(bool(0))
    adr = Signal(intbv(0)[16:])
    we = Signal(bool(0))
    dat_w = Signal(intbv(0)[32:])
    sel = Signal(intbv(0)[4:])
    busy = Signal(bool(0))
    done = Signal(bool(0))
    dat_r = Signal(intbv(0)[32:])
    err = Signal(bool(0))
    wr = Signal(bool(0))
    rd = Signal(bool(0))
    wr_data = Signal(intbv(0)[32:])
    wr_sel = Signal(intbv(0)[4:])
    dut = _p2p_top(
        clk,
        rst,
        req,
        adr,
        we,
        dat_w,
        sel,
        busy,
        done,
        dat_r,
        err,
        wr,
        rd,
        wr_data,
        wr_sel,
    )
    convert_dut(dut, hdl, f"wb_p2p_{hdl.lower()}")
