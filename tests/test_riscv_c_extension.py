"""C as a front-end ISA plug-in (``RC-FR-041/045/048``, WP-05).

Verifies that C is registered as an :class:`Extension` front-end entry, that
:class:`CoreConfig` enables it by default and can disable it, that a disabled C
contributes **zero logic**, and that the plug-in elaborates the RVC
decompressor onto the shared front-end context.

The decompressor's behaviour and both-HDL conversion are covered directly in
``test_riscv_rvc.py`` / ``test_riscv_rvc_conversion.py``; building it through
the registry is checked here for shape and conversion.
"""

import pytest
from myhdl import Signal, intbv

from myhdl_addons.common.views import SignalView
from myhdl_addons.riscv import (
    CExtension,
    CoreConfig,
    default_registry,
    is_compressed,
)

_C_BIT = 1 << 2


def _context():
    """A minimal front-end context (the signals C binds to)."""
    return SignalView(
        instr_i=Signal(intbv(0)[16:]),
        instr_o=Signal(intbv(0)[32:]),
        illegal=Signal(bool(0)),
    )


def _region():
    return {
        "base": "0x0",
        "size": "0x10000",
        "perms": "ID",
        "access": "RW",
        "target": "internal",
    }


def _mapping(**over):
    data = {"core": {"reset_vector": "0x0", "tohost": "0x1000", "fromhost": "0x1004"}}
    data["region.ram"] = _region()
    data.update(over)
    return data


def test_is_compressed_marks_sixteen_bit_encodings():
    assert is_compressed(0x0000) is True  # quadrant 0
    assert is_compressed(0x0001) is True  # quadrant 1
    assert is_compressed(0x0002) is True  # quadrant 2
    assert is_compressed(0x0003) is False  # quadrant 3 (32-bit)
    assert is_compressed(0x0013) is False  # addi
    assert is_compressed(0x00000033) is False  # add


def test_c_extension_is_a_front_end_plug_in():
    ext = CExtension()
    assert ext.name == "c"
    assert ext.priority == 0
    assert ext.claims() == ()  # C adds no 32-bit decode encodings (Q7)
    assert ext.csrs() == ()
    assert ext.decode(0x0001) == {}
    assert ext.components(_context()) == []
    blocks = ext.front_end(_context())
    assert len(blocks) == 1
    assert blocks[0].func.__name__ == "hdl"  # the RvcDecompressor block


def test_default_registry_registers_c():
    assert default_registry().names() == ("c",)


def test_enable_disable_and_zero_overhead():
    reg = default_registry()
    reg.select(["c"])
    assert reg.is_enabled("c") is True
    assert len(reg.build(_context())) == 1  # decompressor elaborated

    reg.select([])
    assert reg.is_enabled("c") is False
    assert reg.build(_context()) == []  # disabled C contributes zero logic


def test_config_drives_selection_and_misa():
    on = CoreConfig.from_mapping(_mapping())
    assert on.extensions == ("c",)
    assert on.misa & _C_BIT

    off = CoreConfig.from_mapping(_mapping(**{"extension.c": {"enabled": "false"}}))
    assert off.extensions == ()
    assert not off.misa & _C_BIT

    reg = default_registry()
    reg.select(on.extensions)
    assert reg.is_enabled("c") is True
    reg.select(off.extensions)
    assert reg.is_enabled("c") is False
    assert reg.build(_context()) == []


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_c_extension_front_end_converts(hdl, convert_dut):
    reg = default_registry()
    reg.select(["c"])
    convert_dut(reg.build(_context())[0], hdl, f"c_front_end_{hdl.lower()}")
