"""AXI4-Lite CSR adapter (AX-FR-080)."""

import pytest

from myhdl_addons.axi import AxiLiteCSR
from myhdl_addons.bus_common import BusConfigError


def test_csr_map_errors():
    csr = AxiLiteCSR(width=32)
    csr.add_write(0x00, "A")
    with pytest.raises(BusConfigError):
        csr.add_write(0x00, "B")  # duplicate offset
    with pytest.raises(BusConfigError):
        csr.add_write(0x04, "A")  # duplicate name
    with pytest.raises(BusConfigError):
        csr.add_write(0x02, "C")  # misaligned offset


def test_csr_bad_width():
    with pytest.raises(BusConfigError):
        AxiLiteCSR(width=0)


def test_csr_empty_build():
    csr = AxiLiteCSR()
    assert csr.signals == {} and csr.wr == {} and csr.rd == {}
