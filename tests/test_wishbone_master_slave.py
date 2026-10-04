"""Classic master core + slave helper tests (WB-FR-020/023/030/032)."""

from myhdl import (
    Signal,
    StopSimulation,
    always,
    always_comb,
    block,
    delay,
    instance,
    intbv,
)

from myhdl_addons.wishbone import (
    PointToPoint,
    Wishbone,
    wishbone_master,
    wishbone_slave,
)


def _cmd_ports():
    req = Signal(bool(0))
    adr = Signal(intbv(0)[16:])
    we = Signal(bool(0))
    dat_w = Signal(intbv(0)[32:])
    sel = Signal(intbv(0)[4:])
    busy = Signal(bool(0))
    done = Signal(bool(0))
    dat_r = Signal(intbv(0)[32:])
    err = Signal(bool(0))
    return req, adr, we, dat_w, sel, busy, done, dat_r, err


@block
def _normal_tb():
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    bus = Wishbone(
        clk, rst, data_width=32, adr_width=16, gran=8, interconnect=PointToPoint()
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x100, name="per")
    (req, adr, we, dat_w, sel, busy, done, dat_r, err) = _cmd_ports()
    core = wishbone_master(m, req, adr, we, dat_w, sel, busy, done, dat_r, err)

    read_data = Signal(intbv(0)[32:])
    wr = Signal(bool(0))
    rd = Signal(bool(0))
    wr_data = Signal(intbv(0)[32:])
    wr_sel = Signal(intbv(0)[4:])
    slave = wishbone_slave(s, read_data, wr, rd, wr_data, wr_sel)

    stored = Signal(intbv(0)[32:])

    @always(clk.posedge)
    def store():
        if wr:
            stored.next = wr_data

    glue = bus.build()

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        rst.next = 1
        yield clk.posedge
        yield clk.posedge
        rst.next = 0

        read_data.next = 0xAB

        # write 0x55
        req.next = 1
        adr.next = 0x10
        we.next = 1
        dat_w.next = 0x55
        sel.next = 0xF
        yield clk.posedge
        req.next = 0
        guard = 0
        while not done:
            yield clk.posedge
            guard += 1
            assert guard < 50
        assert int(err) == 0
        assert int(stored) == 0x55
        assert int(rd) == 0

        # read back
        req.next = 1
        adr.next = 0x20
        we.next = 0
        sel.next = 0xF
        yield clk.posedge
        req.next = 0
        guard = 0
        while not done:
            yield clk.posedge
            guard += 1
            assert guard < 50
        assert int(dat_r) == 0xAB
        raise StopSimulation

    return clkgen, glue, core, slave, store, stim


def test_master_slave_normal():
    _normal_tb().run_sim()


@block
def _error_tb():
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    bus = Wishbone(
        clk,
        rst,
        data_width=32,
        adr_width=16,
        gran=8,
        err=True,
        interconnect=PointToPoint(),
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x100, name="per")
    (req, adr, we, dat_w, sel, busy, done, dat_r, err) = _cmd_ports()
    core = wishbone_master(m, req, adr, we, dat_w, sel, busy, done, dat_r, err)

    @always_comb
    def err_slave():
        active = s.cyc_i and s.stb_i
        s.ack_o.next = 0
        s.err_o.next = active
        s.dat_o.next = 0

    glue = bus.build()

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        rst.next = 1
        yield clk.posedge
        yield clk.posedge
        rst.next = 0

        req.next = 1
        adr.next = 0x00
        we.next = 1
        dat_w.next = 0xFF
        sel.next = 0xF
        yield clk.posedge
        req.next = 0
        guard = 0
        while not done:
            yield clk.posedge
            guard += 1
            assert guard < 50
        assert int(err) == 1
        raise StopSimulation

    return clkgen, glue, core, err_slave, stim


def test_master_slave_error():
    _error_tb().run_sim()


@block
def _retry_tb():
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    bus = Wishbone(
        clk,
        rst,
        data_width=32,
        adr_width=16,
        gran=8,
        rty=True,
        interconnect=PointToPoint(),
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x100, name="per")
    (req, adr, we, dat_w, sel, busy, done, dat_r, err) = _cmd_ports()
    core = wishbone_master(m, req, adr, we, dat_w, sel, busy, done, dat_r, err)

    stall = Signal(bool(1))

    @always_comb
    def rty_slave():
        active = s.cyc_i and s.stb_i
        s.ack_o.next = active and (not stall)
        s.rty_o.next = active and stall
        s.dat_o.next = 0x5A

    glue = bus.build()

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        rst.next = 1
        yield clk.posedge
        yield clk.posedge
        rst.next = 0

        req.next = 1
        adr.next = 0x00
        we.next = 0
        sel.next = 0xF
        yield clk.posedge
        req.next = 0
        # hold the retry for a couple of cycles, then let it complete
        yield clk.posedge
        yield clk.posedge
        stall.next = 0
        guard = 0
        while not done:
            yield clk.posedge
            guard += 1
            assert guard < 50
        assert int(dat_r) == 0x5A
        raise StopSimulation

    return clkgen, glue, core, rty_slave, stim


def test_master_slave_retry():
    _retry_tb().run_sim()
