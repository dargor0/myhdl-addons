"""AXI status extends the common BusStatus (AX-FR-010, CB-FR-082)."""

from myhdl_addons.axi import AxiStatus, resp_to_status, status_to_resp
from myhdl_addons.axi.status import AXI_TO_BUS
from myhdl_addons.bus_common import BusStatus, extend_bus_status


def test_axi_status_extends_bus_status():
    for member in BusStatus:
        assert AxiStatus[member.name].value == member.value
    assert AxiStatus.OKAY.value == "okay"
    assert AxiStatus.SLVERR.value == "slverr"
    assert AxiStatus.DECERR.value == "decerr"


def test_bus_mapping():
    assert AXI_TO_BUS[AxiStatus.OKAY] is BusStatus.OK
    assert AXI_TO_BUS[AxiStatus.SLVERR] is BusStatus.ERROR
    assert AXI_TO_BUS[AxiStatus.DECERR] is BusStatus.ERROR


def test_resp_roundtrip():
    assert resp_to_status(0) is AxiStatus.OKAY
    assert resp_to_status(1) is AxiStatus.EXOKAY
    assert resp_to_status(2) is AxiStatus.SLVERR
    assert resp_to_status(3) is AxiStatus.DECERR
    assert resp_to_status(0b1111) is AxiStatus.DECERR
    assert status_to_resp(AxiStatus.OKAY) == 0
    assert status_to_resp(AxiStatus.EXOKAY) == 1
    assert status_to_resp(AxiStatus.SLVERR) == 2
    assert status_to_resp(AxiStatus.DECERR) == 3
    assert status_to_resp(AxiStatus.OK) == 3  # base-only member -> DECERR


def test_extend_bus_status_helper():
    extra = extend_bus_status("Demo", {"FOO": "foo"})
    assert extra.FOO.value == "foo"
    assert extra.OK.value == "ok"
