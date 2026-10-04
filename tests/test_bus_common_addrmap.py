"""Common address map and decoder (CB-FR-060..062)."""

import pytest
from myhdl import Signal, StopSimulation, block, delay, instance, intbv

from myhdl_addons.bus_common.addrmap import AddressMap, address_decoder
from myhdl_addons.bus_common.errors import BusConfigError


def test_address_map_regions():
    amap = AddressMap(16)
    amap.add(0x0000, 0x100, "ram")
    amap.add(0x1000, 0x100, "csr")
    assert amap.bases() == [0x0000, 0x1000]
    assert amap.sizes() == [0x100, 0x100]
    assert amap.names() == ["ram", "csr"]
    assert len(amap.regions) == 2
    assert len(amap) == 2
    assert next(iter(amap))[0] == 0x0000
    assert amap.find(0x0004) == 0
    assert amap.find(0x1050) == 1
    assert amap.find(0x2000) is None
    assert "AddressMap" in repr(amap)


def test_address_map_overlap_and_range():
    amap = AddressMap(16)
    amap.add(0x0000, 0x100, "a")
    with pytest.raises(BusConfigError):
        amap.add(0x0080, 0x100, "b")


def test_address_map_out_of_range():
    amap = AddressMap(8)
    with pytest.raises(BusConfigError):
        amap.add(0xF0, 0x20, "too_big")


def test_address_map_bad_width():
    with pytest.raises(BusConfigError):
        AddressMap(0)


def test_address_decoder_length_mismatch():
    adr = Signal(intbv(0)[16:])
    selects = [Signal(bool(0))]
    with pytest.raises(BusConfigError):
        address_decoder(adr, selects, [0x0000, 0x1000], [0x100, 0x100])


@block
def _decoder_tb():
    adr = Signal(intbv(0)[16:])
    selects = [Signal(bool(0)) for _ in range(3)]
    dec = address_decoder(adr, selects, [0x0000, 0x1000, 0x2000], [0x100, 0x100, 0x100])

    @instance
    def stim():
        for addr, expect in [
            (0x0000, [1, 0, 0]),
            (0x1050, [0, 1, 0]),
            (0x2000, [0, 0, 1]),
            (0x3000, [0, 0, 0]),
        ]:
            adr.next = addr
            yield delay(1)
            got = [int(s) for s in selects]
            assert got == expect, (hex(addr), got)
        raise StopSimulation

    return dec, stim


def test_address_decoder_sim():
    _decoder_tb().run_sim()
