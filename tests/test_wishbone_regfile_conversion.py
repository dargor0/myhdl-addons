"""Conversion smoke test for the Wishbone CSR peripheral (Verilog + VHDL)."""

import pytest
from myhdl import Signal, always_comb, block, intbv

from myhdl_addons.wishbone import CSRMap, PointToPoint, Wishbone, wishbone_master


@block
def _csr_top(clk, rst, req, adr, we, dat_w, sel, busy, done, dat_r, err, rw_out):
    bus = Wishbone(
        clk, rst, data_width=32, adr_width=16, gran=8, interconnect=PointToPoint()
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x100, name="csr")

    core = wishbone_master(m, req, adr, we, dat_w, sel, busy, done, dat_r, err)

    csr = CSRMap(width=32)
    csr.add_write(0x00, "CTRL", init=1)
    csr.add_ro(0x04, "ID", init=0xCAFE)
    csr.add_read(0x08, "STATUS")
    peri = csr.build(s)

    glue = bus.build()
    status = csr.signals["STATUS"]
    wr_ctrl, rd_ctrl = csr.wr["CTRL"], csr.rd["CTRL"]
    wr_id, rd_id = csr.wr["ID"], csr.rd["ID"]
    wr_status, rd_status = csr.wr["STATUS"], csr.rd["STATUS"]

    @always_comb
    def drive_status():
        status.next = dat_w

    @always_comb
    def collect_strobes():
        rw_out.next = (
            wr_ctrl or rd_ctrl or wr_id or rd_id or wr_status or rd_status
        )

    return core, peri, glue, drive_status, collect_strobes


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_wishbone_csr_converts(hdl, convert_dut):
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
    rw_out = Signal(bool(0))
    dut = _csr_top(clk, rst, req, adr, we, dat_w, sel, busy, done, dat_r, err, rw_out)
    convert_dut(dut, hdl, f"wb_csr_{hdl.lower()}")
