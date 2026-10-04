"""Conversion smoke test for the common register/CSR engine (Verilog + VHDL)."""

import pytest
from myhdl import Signal, always_comb, block, intbv

from myhdl_addons.bus_common.regfile import CSRMap


@block
def _csr_top(clk, rst, req, we, addr, wdata, wstrb, rdata, ack, rw_out):
    engine = CSRMap(width=32, gran=8)
    engine.add_write(0x00, "ctrl", init=1)
    engine.add_ro(0x04, "id", init=0xCAFE)
    engine.add_read(0x08, "status")
    engine.add_write(0x0C, "w1c", init=0xFF, w1c=True)

    inst = engine.build(clk, rst, req, we, addr, wdata, rdata, ack, wstrb=wstrb)
    status = engine.signals["status"]
    rd_ctrl, wr_ctrl = engine.rd["ctrl"], engine.wr["ctrl"]
    rd_id, wr_id = engine.rd["id"], engine.wr["id"]
    rd_status, wr_status = engine.rd["status"], engine.wr["status"]
    rd_w1c, wr_w1c = engine.rd["w1c"], engine.wr["w1c"]

    @always_comb
    def drive_status():
        status.next = wdata

    @always_comb
    def collect_strobes():
        rw_out.next = (
            rd_ctrl
            or wr_ctrl
            or rd_id
            or wr_id
            or rd_status
            or wr_status
            or rd_w1c
            or wr_w1c
        )

    return inst, drive_status, collect_strobes


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_register_engine_converts(hdl, convert_dut):
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    req = Signal(bool(0))
    we = Signal(bool(0))
    addr = Signal(intbv(0)[8:])
    wdata = Signal(intbv(0)[32:])
    wstrb = Signal(intbv(0)[4:])
    rdata = Signal(intbv(0)[32:])
    ack = Signal(bool(0))
    rw_out = Signal(bool(0))
    dut = _csr_top(clk, rst, req, we, addr, wdata, wstrb, rdata, ack, rw_out)
    convert_dut(dut, hdl, f"bus_csr_{hdl.lower()}")
