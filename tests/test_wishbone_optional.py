"""Optional-signal tests: the ``ERR``/``RTY``/``LOCK`` paths."""

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
    CSRMap,
    PointToPoint,
    SharedBus,
    Wishbone,
    WishboneBFM,
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
def _err_ack_tb():
    """``ERR`` enabled, the slave ACKs: master err-FSM ack branch + slave err branch."""
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
        read_data.next = 0x77

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
        assert int(dat_r) == 0x77
        raise StopSimulation

    return clkgen, glue, core, slave, store, stim


def test_master_slave_err_ack():
    _err_ack_tb().run_sim()


@block
def _err_rty_tb():
    """``ERR``+``RTY`` enabled: exercise the combined FSM's rty/err/ack branches."""
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    bus = Wishbone(
        clk,
        rst,
        data_width=32,
        adr_width=16,
        gran=8,
        err=True,
        rty=True,
        interconnect=PointToPoint(),
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x100, name="per")
    (req, adr, we, dat_w, sel, busy, done, dat_r, err) = _cmd_ports()
    core = wishbone_master(m, req, adr, we, dat_w, sel, busy, done, dat_r, err)

    stall = Signal(bool(1))
    fail = Signal(bool(0))

    @always_comb
    def resp_slave():
        active = s.cyc_i and s.stb_i
        s.rty_o.next = active and stall
        s.err_o.next = active and fail and (not stall)
        s.ack_o.next = active and (not stall) and (not fail)
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

        # transaction 1: retry for a few cycles, then ack
        req.next = 1
        adr.next = 0x00
        we.next = 0
        sel.next = 0xF
        yield clk.posedge
        req.next = 0
        yield clk.posedge
        yield clk.posedge
        stall.next = 0
        guard = 0
        while not done:
            yield clk.posedge
            guard += 1
            assert guard < 50
        assert int(err) == 0
        assert int(dat_r) == 0x5A

        # transaction 2: error
        fail.next = 1
        req.next = 1
        adr.next = 0x04
        we.next = 0
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

    return clkgen, glue, core, resp_slave, stim


def test_master_slave_err_rty():
    _err_rty_tb().run_sim()


@block
def _shared_opt_tb():
    """Shared bus with ERR/RTY/LOCK enabled: exercise every optional path."""
    clk = Signal(bool(0))
    rst = Signal(bool(0))

    bus = Wishbone(
        clk,
        rst,
        data_width=32,
        adr_width=16,
        gran=8,
        err=True,
        rty=True,
        lock=True,
        interconnect=SharedBus(),
    )
    m0 = bus.add_master("m0")
    m1 = bus.add_master("m1")
    s0 = bus.add_slave(base=0x0000, size=0x100, name="s0")
    s1 = bus.add_slave(base=0x1000, size=0x100, name="s1")

    csr0 = CSRMap(width=32)
    csr0.add_write(0x00, "REG", init=0)
    csr0.add_ro(0x04, "ID", init=0xAAAA)
    peri0 = csr0.build(s0)

    csr1 = CSRMap(width=32)
    csr1.add_write(0x00, "REG", init=0)
    csr1.add_ro(0x04, "ID", init=0xBBBB)
    peri1 = csr1.build(s1)

    bfm0 = WishboneBFM(m0, timeout=200)
    bfm1 = WishboneBFM(m1, timeout=200)
    glue = bus.build()

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def do_reset():
        rst.next = 1
        yield clk.posedge
        yield clk.posedge
        rst.next = 0

    @instance
    def driver0():
        while rst:
            yield clk.posedge
        yield bfm0.read(0x0004)
        assert bfm0.last_data == 0xAAAA
        yield bfm0.write(0x0000, 0x1234)
        yield bfm0.read(0x0000)
        assert bfm0.last_data == 0x1234

    @instance
    def driver1():
        while rst:
            yield clk.posedge
        yield bfm1.read(0x1004)
        assert bfm1.last_data == 0xBBBB

    @instance
    def stopper():
        yield delay(20000)
        raise StopSimulation

    return clkgen, glue, peri0, peri1, do_reset, driver0, driver1, stopper


def test_shared_bus_all_optional():
    _shared_opt_tb().run_sim()
