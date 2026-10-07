"""RISC-V ISA plug-in mechanism (``RC-FR-030..039``)."""

import pytest
from myhdl import Signal, intbv

from myhdl_addons.common import HdlTypeError
from myhdl_addons.common.views import SignalView
from myhdl_addons.riscv import (
    Extension,
    ExtensionRegistry,
    RiscvConfigError,
)


class _Recorder(Extension):
    """Test extension that records which hooks are elaborated."""

    def __init__(self, name, priority=0, claims=(), log=None):
        self.name = name
        self.priority = priority
        self._claims = tuple(claims)
        self.log = log if log is not None else []

    def claims(self):
        return self._claims

    def front_end(self, context):
        self.log.append((self.name, "front_end"))
        return [f"{self.name}-front"]

    def components(self, context):
        self.log.append((self.name, "components"))
        return [f"{self.name}-component"]

    def reset(self, context):
        self.log.append((self.name, "reset"))
        return [f"{self.name}-reset"]


def test_extension_defaults():
    ext = Extension()
    assert ext.name == ""
    assert ext.priority == 0
    assert ext.claims() == ()
    assert ext.matches(0x00000000) is False
    assert ext.decode(0x33) == {}
    assert ext.csrs() == ()
    assert ext.front_end(SignalView()) == []
    assert list(ext.decode_stage(SignalView()).subs) == []
    assert ext.components(SignalView()) == []
    assert ext.reset(SignalView()) == []


def test_matches_uses_claims():
    ext = _Recorder("m", claims=[(0xFE00007F, 0x02000033)])
    assert ext.matches(0x02000033) is True
    assert ext.matches(0x02000033 | (1 << 10)) is True
    assert ext.matches(0x33) is False
    assert ext.matches(0x00000013) is False


def test_extension_context_is_a_signal_view():
    ctx = SignalView(clk=Signal(bool(0)), data=Signal(intbv(0)[8:]))
    assert isinstance(ctx, SignalView)  # the context is just a SignalView
    assert ctx.clk is ctx["clk"]
    assert ctx.names == ["clk", "data"]
    with pytest.raises(HdlTypeError):
        SignalView(x=5)


def test_registry_register_names_and_duplicates():
    reg = ExtensionRegistry([_Recorder("c"), _Recorder("m")])
    assert reg.names() == ("c", "m")
    with pytest.raises(RiscvConfigError):
        reg.register(_Recorder("c"))
    with pytest.raises(RiscvConfigError):
        ExtensionRegistry([_Recorder("")])


def test_select_orders_by_priority_then_name():
    low = _Recorder("a", priority=0)
    high = _Recorder("b", priority=5)
    tie = _Recorder("c", priority=5)
    reg = ExtensionRegistry([low, high, tie])
    assert [e.name for e in reg.select(["a", "c", "b"])] == ["b", "c", "a"]
    assert [e.name for e in reg.selected] == ["b", "c", "a"]


def test_select_unknown_and_duplicate_enabled():
    reg = ExtensionRegistry([_Recorder("c")])
    with pytest.raises(RiscvConfigError):
        reg.select(["m"])  # not registered
    with pytest.raises(RiscvConfigError):
        reg.select(["c", "c"])  # duplicate


def test_conflicts_are_detected_by_claims():
    a = _Recorder("a", claims=[(0x7F, 0x33)])
    b = _Recorder("b", claims=[(0x7F, 0x33)])  # identical encoding
    c = _Recorder("c", claims=[(0x7F, 0x13)])
    reg = ExtensionRegistry([a, b, c])
    reg.select(["a", "c"])  # disjoint -> fine
    with pytest.raises(RiscvConfigError):
        reg.select(["a", "b"])
    # partly-overlapping masks (funct7 subset of opcode-only claim)
    wide = _Recorder("wide", claims=[(0x7F, 0x33)])
    narrow = _Recorder("narrow", claims=[(0xFE00007F, 0x02000033)])
    reg2 = ExtensionRegistry([wide, narrow])
    with pytest.raises(RiscvConfigError):
        reg2.select(["wide", "narrow"])


def test_build_only_enables_selected_extensions():
    log = []
    a = _Recorder("a", log=log)
    b = _Recorder("b", log=log)
    reg = ExtensionRegistry([a, b])
    reg.select(["a"])
    blocks = reg.build(SignalView())
    assert blocks == ["a-front", "a-component", "a-reset"]
    assert [entry[0] for entry in log] == ["a", "a", "a"]


def test_build_with_no_selection_is_empty():
    reg = ExtensionRegistry([_Recorder("a")])
    assert reg.build(SignalView()) == []
