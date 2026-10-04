"""Shared configuration model (``IC-FR-120..129``)."""

import pytest

from myhdl_addons.common.config import (
    ComponentBase,
    ceil_log2,
    check_bool,
    check_choice,
    check_int,
    check_non_negative,
    check_positive,
    check_power_of_two,
    check_registered,
    mask,
    normalize_subset,
)
from myhdl_addons.components import HdlConfigError


def test_integer_helpers():
    assert check_int(3, "x") == 3
    assert check_positive(3, "x") == 3
    assert check_non_negative(0, "x") == 0
    assert check_power_of_two(8, "x") == 8
    assert check_registered(0, "r") == 0
    assert check_registered(1, "r") == 1
    assert check_bool(True, "b") is True
    assert check_choice("wrap", ("wrap", "saturate"), "m") == "wrap"
    for bad in (True, 3.0, "3"):
        with pytest.raises(HdlConfigError):
            check_int(bad, "x")
    with pytest.raises(HdlConfigError):
        check_positive(0, "x")
    with pytest.raises(HdlConfigError):
        check_non_negative(-1, "x")
    with pytest.raises(HdlConfigError):
        check_power_of_two(3, "x")
    with pytest.raises(HdlConfigError):
        check_registered(2, "r")
    with pytest.raises(HdlConfigError):
        check_bool(1, "b")
    with pytest.raises(HdlConfigError):
        check_choice("nope", ("a",), "m")


def test_bits_helpers():
    assert ceil_log2(1) == 0
    assert ceil_log2(2) == 1
    assert ceil_log2(3) == 2
    assert ceil_log2(8) == 3
    assert mask(4) == 0xF
    with pytest.raises(HdlConfigError):
        ceil_log2(0)
    with pytest.raises(HdlConfigError):
        mask(0)


def test_normalize_subset():
    allowed = (1, 2, 3)
    names = {1: "A", 2: "B", 3: "C"}
    assert normalize_subset(None, allowed, "s", default=(1, 2)) == (1, 2)
    assert normalize_subset(2, allowed, "s") == (2,)
    assert normalize_subset([3, 1], allowed, "s") == (1, 3)
    assert normalize_subset(["B", "a"], allowed, "s", names=names) == (1, 2)
    with pytest.raises(HdlConfigError):
        normalize_subset(None, allowed, "s")
    with pytest.raises(HdlConfigError):
        normalize_subset([], allowed, "s")
    with pytest.raises(HdlConfigError):
        normalize_subset([9], allowed, "s")
    with pytest.raises(HdlConfigError):
        normalize_subset([1, 1], allowed, "s")


class _Demo(ComponentBase):
    def __init__(self, width=8):
        self._params = {"width": width}


def test_component_base_protocol():
    demo = _Demo()
    assert demo.as_dict() == {"width": 8}
    assert "width=8" in repr(demo)
