"""Yosys synthesizability smoke test for the Wishbone shared-bus fabric (S1).

A closed 2-master / 2-slave system: two master cores, the shared-bus fabric and
two CSR slaves, with every external command/status signal a top-level port and
the per-register strobes consumed, so nothing is left undriven or unread.
"""

from myhdl import Signal, always_comb, block, intbv

from myhdl_addons.wishbone import CSRMap, SharedBus, Wishbone, wishbone_master


@block
def _shared_top(
    clk,
    rst,
    m0_req,
    m0_adr,
    m0_we,
    m0_dat_w,
    m0_sel,
    m0_busy,
    m0_done,
    m0_dat_r,
    m0_err,
    m1_req,
    m1_adr,
    m1_we,
    m1_dat_w,
    m1_sel,
    m1_busy,
    m1_done,
    m1_dat_r,
    m1_err,
    s0_strobes,
    s1_strobes,
):
    bus = Wishbone(
        clk, rst, data_width=32, adr_width=16, gran=8, interconnect=SharedBus()
    )
    p0 = bus.add_master("m0")
    p1 = bus.add_master("m1")
    sp0 = bus.add_slave(base=0x0000, size=0x0100, name="s0")
    sp1 = bus.add_slave(base=0x1000, size=0x0100, name="s1")

    master0 = wishbone_master(
        p0, m0_req, m0_adr, m0_we, m0_dat_w, m0_sel, m0_busy, m0_done, m0_dat_r, m0_err
    )
    master1 = wishbone_master(
        p1, m1_req, m1_adr, m1_we, m1_dat_w, m1_sel, m1_busy, m1_done, m1_dat_r, m1_err
    )

    csr0 = CSRMap(width=32)
    csr0.add_write(0x00, "REG", init=1)
    csr0.add_ro(0x04, "ID", init=0xAAAA)
    csr1 = CSRMap(width=32)
    csr1.add_write(0x00, "REG", init=2)
    csr1.add_ro(0x04, "ID", init=0xBBBB)
    peri0 = csr0.build(sp0)
    peri1 = csr1.build(sp1)
    glue = bus.build()

    wr0, rd0 = csr0.wr["REG"], csr0.rd["REG"]
    wr0b, rd0b = csr0.wr["ID"], csr0.rd["ID"]
    wr1, rd1 = csr1.wr["REG"], csr1.rd["REG"]
    wr1b, rd1b = csr1.wr["ID"], csr1.rd["ID"]

    @always_comb
    def collect0():
        s0_strobes.next = wr0 or rd0 or wr0b or rd0b

    @always_comb
    def collect1():
        s1_strobes.next = wr1 or rd1 or wr1b or rd1b

    return [master0, master1, peri0, peri1, glue, collect0, collect1]


def _master_signals():
    return (
        Signal(bool(0)),  # req
        Signal(intbv(0)[16:]),  # adr
        Signal(bool(0)),  # we
        Signal(intbv(0)[32:]),  # dat_w
        Signal(intbv(0)[4:]),  # sel
        Signal(bool(0)),  # busy
        Signal(bool(0)),  # done
        Signal(intbv(0)[32:]),  # dat_r
        Signal(bool(0)),  # err
    )


def test_wishbone_shared_bus_synthesizes(hdl_synth):
    dut = _shared_top(
        Signal(bool(0)),
        Signal(bool(0)),
        *_master_signals(),
        *_master_signals(),
        Signal(bool(0)),  # s0 strobes
        Signal(bool(0)),  # s1 strobes
    )
    result = hdl_synth(dut, "wb_shared_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
