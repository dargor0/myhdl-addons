"""Common adapter base and loopback self-check (CB-FR-120..122)."""

import pytest
from myhdl import StopSimulation, block, delay, instance

from myhdl_addons.bus_common.adapter import AdapterBase
from myhdl_addons.bus_common.errors import BusProtocolError


class _MemBFM:
    def __init__(self):
        self.mem = {}
        self.last_data = None

    def write(self, addr, data, sel=None):
        self.mem[addr] = data
        yield delay(1)

    def read(self, addr, sel=None):
        self.last_data = self.mem.get(addr)
        yield delay(1)


class _BadBFM(_MemBFM):
    def read(self, addr, sel=None):
        self.last_data = 0xDEAD
        yield delay(1)


class _Concrete(AdapterBase):
    def build(self):
        return []

    def convert_request(self, addr, we, data, sel=None):
        return (addr, we, data)

    def convert_response(self, response):
        return response


@block
def _adapter_tb(adapter, bfm, pairs, readback=True):
    @instance
    def stim():
        yield adapter.self_check(bfm, pairs, readback=readback)
        raise StopSimulation

    return stim


def test_adapter_base_not_implemented():
    adapter = AdapterBase()
    with pytest.raises(NotImplementedError):
        adapter.build()
    with pytest.raises(NotImplementedError):
        adapter.convert_request(0, False, 0)
    with pytest.raises(NotImplementedError):
        adapter.convert_response(None)


def test_adapter_directions():
    adapter = AdapterBase(upstream=1, downstream=2, name="ax", to_upstream=False)
    assert adapter.upstream == 1
    assert adapter.downstream == 2
    assert adapter.name == "ax"
    assert not adapter.bidirectional
    assert AdapterBase().bidirectional


def test_concrete_adapter_hooks():
    adapter = _Concrete(name="c")
    assert adapter.build() == []
    assert adapter.convert_request(0x4, True, 0xAB) == (0x4, True, 0xAB)
    assert adapter.convert_response(5) == 5


def test_self_check_ok():
    _adapter_tb(
        AdapterBase(name="loop"), _MemBFM(), [(0x0, 0xAA), (0x4, 0x55)]
    ).run_sim()


def test_self_check_without_readback():
    _adapter_tb(
        AdapterBase(name="loop"), _MemBFM(), [(0x0, 0xAA)], readback=False
    ).run_sim()


def test_self_check_mismatch_raises():
    with pytest.raises(BusProtocolError):
        _adapter_tb(AdapterBase(name="loop"), _BadBFM(), [(0x0, 0xAA)]).run_sim()
