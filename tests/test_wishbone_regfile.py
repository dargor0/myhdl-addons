"""Register-file / CSR layer tests (WB-FR-070/072/073/074)."""

import pytest
from myhdl import Signal, StopSimulation, always, always_comb, block, delay, instance

from myhdl_addons.wishbone import CSRMap, PointToPoint, Wishbone, WishboneBFM
from myhdl_addons.wishbone.checks import WishboneConfigError


def test_csr_map_errors():
    csr = CSRMap(width=32)
    csr.add_write(0x00, "A")
    with pytest.raises(WishboneConfigError):
        csr.add_write(0x00, "B")  # duplicate offset
    with pytest.raises(WishboneConfigError):
        csr.add_write(0x04, "A")  # duplicate name
    with pytest.raises(WishboneConfigError):
        csr.add_write(0x02, "C")  # misaligned offset


def test_csr_map_empty_build():
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    bus = Wishbone(clk, rst)
    s = bus.add_slave(base=0x0000, size=0x100)
    with pytest.raises(WishboneConfigError):
        CSRMap().build(s)


def test_csr_map_bad_width():
    with pytest.raises(WishboneConfigError):
        CSRMap(width=0)


@block
def _csr_tb():
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    bus = Wishbone(
        clk, rst, data_width=32, adr_width=16, gran=8, interconnect=PointToPoint()
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x100, name="csr")

    csr = CSRMap(width=32)
    csr.add_write(0x00, "CTRL", init=0x1111)
    csr.add_ro(0x04, "ID", init=0xC0DE)
    csr.add_read(0x08, "STATUS")
    peri = csr.build(s)

    bfm = WishboneBFM(m)
    glue = bus.build()

    @always_comb
    def drive_status():
        csr.signals["STATUS"].next = 0x77 | (s.cyc_i & 0)

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        rst.next = 1
        yield clk.posedge
        yield clk.posedge
        rst.next = 0

        yield bfm.read(0x00)
        assert bfm.last_data == 0x1111, hex(bfm.last_data)  # reset value

        yield bfm.write(0x00, 0xABCD)
        yield bfm.read(0x00)
        assert bfm.last_data == 0xABCD

        yield bfm.read(0x04)
        assert bfm.last_data == 0xC0DE

        yield bfm.write(0x04, 0xFFFF)  # read-only
        yield bfm.read(0x04)
        assert bfm.last_data == 0xC0DE

        yield bfm.read(0x08)
        assert bfm.last_data == 0x77

        # unused register bits read as zero
        yield bfm.read(0x0C)
        assert bfm.last_data == 0x00
        raise StopSimulation

    return clkgen, glue, peri, drive_status, stim


def test_csr_map_sim():
    _csr_tb().run_sim()
