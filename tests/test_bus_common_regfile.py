"""Generic register / CSR engine (CB-FR-070..075)."""

import pytest
from myhdl import Signal, StopSimulation, block, delay, instance, intbv

from myhdl_addons.bus_common.errors import BusConfigError
from myhdl_addons.bus_common.regfile import (
    CSRMap,
    RegisterEngine,
    RegisterSpec,
    bitfield,
    bitfield_set,
)


def test_bitfield_helpers():
    assert bitfield(0xABCD, 4, 4) == 0xC
    assert bitfield(0xABCD, 0, 8) == 0xCD
    assert bitfield_set(0x0000, 4, 4, 0xF) == 0x00F0
    assert bitfield_set(0xFFFF, 0, 4, 0x0) == 0xFFF0


def test_engine_configuration_errors():
    engine = RegisterEngine(width=32)
    with pytest.raises(BusConfigError):
        engine.add_write(0x01, "misaligned")
    engine.add_write(0x00, "a")
    with pytest.raises(BusConfigError):
        engine.add_write(0x00, "b")
    engine.add_write(0x04, "b")
    with pytest.raises(BusConfigError):
        engine.add_write(0x08, "b")
    with pytest.raises(BusConfigError):
        engine.add(0x08, "c", access="weird")
    with pytest.raises(BusConfigError):
        engine.add_write(0x08, "")
    with pytest.raises(BusConfigError):
        RegisterEngine(width=32, gran=12)
    with pytest.raises(BusConfigError):
        RegisterEngine(width=0)


def test_register_spec_and_accessors():
    engine = RegisterEngine(width=16, gran=8, name="rf")
    engine.add_write(0x00, "ctrl", init=1)
    engine.add_ro(0x02, "id", init=0xBEEF)
    engine.add_read(0x04, "status", source="ext")
    assert [r.name for r in engine.regs] == ["ctrl", "id", "status"]
    spec = engine.spec("id")
    assert isinstance(spec, RegisterSpec)
    assert spec.as_dict()["reset"] == 0xBEEF
    assert "id" in repr(spec)
    assert engine.spec("status").source == "ext"


def test_empty_engine_build_rejected():
    engine = RegisterEngine()
    with pytest.raises(BusConfigError):
        engine.build(
            Signal(bool(0)),
            Signal(bool(0)),
            Signal(bool(0)),
            Signal(bool(0)),
            Signal(intbv(0)[8:]),
            Signal(intbv(0)[32:]),
            Signal(intbv(0)[32:]),
            Signal(bool(0)),
        )


@block
def _csr_tb():
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    req = Signal(bool(0))
    we = Signal(bool(0))
    addr = Signal(intbv(0)[8:])
    wdata = Signal(intbv(0)[32:])
    wstrb = Signal(intbv(0)[4:])
    rdata = Signal(intbv(0)[32:])
    ack = Signal(bool(0))

    engine = CSRMap(width=32, gran=8)
    engine.add_write(0x00, "ctrl", init=1)
    engine.add_ro(0x04, "id", init=0xCAFE)
    engine.add_read(0x08, "status")
    engine.add_write(0x0C, "w1c", init=0xFF, w1c=True)
    instances = engine.build(clk, rst, req, we, addr, wdata, rdata, ack, wstrb=wstrb)

    @instance
    def stim():
        rst.next = 1
        clk.next = 1
        yield delay(1)
        clk.next = 0
        yield delay(1)
        assert int(engine.signals["ctrl"]) == 1
        assert int(engine.signals["id"]) == 0xCAFE
        rst.next = 0

        addr.next = 0x00
        wdata.next = 0x1234
        wstrb.next = 0xF
        req.next = 1
        we.next = 1
        yield delay(1)
        assert int(engine.wr["ctrl"]) == 1
        clk.next = 1
        yield delay(1)
        clk.next = 0
        yield delay(1)
        assert int(engine.signals["ctrl"]) == 0x1234

        wdata.next = 0xFFFFFFFF
        wstrb.next = 0x3
        clk.next = 1
        yield delay(1)
        clk.next = 0
        yield delay(1)
        assert int(engine.signals["ctrl"]) == 0x0000FFFF

        addr.next = 0x0C
        wdata.next = 0x0F
        wstrb.next = 0xF
        clk.next = 1
        yield delay(1)
        clk.next = 0
        yield delay(1)
        assert int(engine.signals["w1c"]) == 0xF0

        we.next = 0
        addr.next = 0x00
        yield delay(1)
        assert int(rdata) == 0x0000FFFF
        assert int(engine.rd["ctrl"]) == 1
        addr.next = 0x04
        yield delay(1)
        assert int(rdata) == 0xCAFE
        addr.next = 0x40
        yield delay(1)
        assert int(rdata) == 0
        assert int(ack) == 1
        req.next = 0
        yield delay(1)
        assert int(ack) == 0
        raise StopSimulation

    return instances, stim


def test_register_engine_sim():
    _csr_tb().run_sim()
