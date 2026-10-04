"""AXI transaction-level reference model and differential checks (AX-FR-092)."""

import random

from myhdl import Signal, StopSimulation, always, block, delay, instance

from myhdl_addons.axi import (
    Axi,
    AxiBFM,
    AxiMemModel,
    AxiPointToPoint,
    AxiStatus,
    axi_full_slave,
)


def test_model_write_read_roundtrip():
    model = AxiMemModel(data_width=32, base=0, size=0x100)
    assert model.write(0x00, [0x11, 0x22]) is AxiStatus.OKAY
    assert model.read(0x00, 2) is AxiStatus.OKAY
    assert model.last_data == [0x11, 0x22]


def test_model_unmapped_returns_decerr():
    model = AxiMemModel(data_width=32, base=0, size=0x100)
    assert model.read(0x8000) is AxiStatus.DECERR
    assert model.last_data is None
    assert model.write(0x8000, [0x1]) is AxiStatus.DECERR


def test_model_partial_write_strb():
    model = AxiMemModel(data_width=32, base=0, size=0x100)
    model.write(0x00, [0xFFFF_FFFF])
    model.write(0x00, [0x0000_ABCD], strb=0b0011)
    model.read(0x00)
    assert model.last_data == [0xFFFF_ABCD]


def test_model_reset_and_word():
    model = AxiMemModel(data_width=32, base=0, size=0x100, fill=0xAB)
    assert model.word(0x04) == 0xAB
    model.reset()
    assert model.word(0x04) == 0
    assert model.last_data is None


@block
def _diff_tb(seed, count):
    aclk = Signal(bool(0))
    aresetn = Signal(bool(0))

    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        variant="full",
        interconnect=AxiPointToPoint(),
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x0100, name="mem")

    mem = axi_full_slave(s)
    bfm = AxiBFM(m, timeout=400)
    glue = bus.build()

    model = AxiMemModel(data_width=32, base=0, size=0x100)
    rng = random.Random(seed)
    words = model.words
    nbytes = model.nbytes

    @always(delay(5))
    def clkgen():
        aclk.next = not aclk

    @instance
    def stim():
        aresetn.next = 0
        yield aclk.posedge
        yield aclk.posedge
        aresetn.next = 1

        for _ in range(count):
            length = rng.randint(1, 4)
            start = rng.randrange(0, words - length + 1)
            addr = start * nbytes
            if rng.random() < 0.5:
                data = [rng.getrandbits(32) for _ in range(length)]
                yield bfm.write(addr, data)
                assert bfm.last_resp is model.write(addr, data)
                yield bfm.read(addr, length)
                model.read(addr, length)
                assert bfm.last_data == model.last_data, (addr, bfm.last_data)
                assert bfm.last_resp is model.last_resp
            else:
                yield bfm.read(addr, length)
                model.read(addr, length)
                assert bfm.last_data == model.last_data, (addr, bfm.last_data)
                assert bfm.last_resp is model.last_resp

        raise StopSimulation

    return clkgen, glue, mem, stim


def test_refmodel_matches_full_slave_randomized():
    _diff_tb(seed=1234, count=25).run_sim()
