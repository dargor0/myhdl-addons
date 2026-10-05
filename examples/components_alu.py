"""Reusable-component demo: use an ``Alu`` and convert it to Verilog + VHDL.

Shows the standard component flow (``ports()`` → ``hdl(ports)``) and the
mandatory HDL conversion.

Run with::

    python examples/components_alu.py
"""

from pathlib import Path

from myhdl import StopSimulation, block, delay, instance

from myhdl_addons.components import Alu

_VECTORS = (
    ("ADD", 0x0F, 0x01),
    ("SUB", 0x01, 0x02),
    ("AND", 0xF0, 0x0F),
    ("SLT", 0x80, 0x01),
)


@block
def alu_demo(verbose=False):
    alu = Alu(width=8, flags=["zero", "lt", "carry"])
    ports = alu.ports()
    dut = alu.hdl(ports)
    opmap = alu.get_op_intmap()

    @instance
    def stim():
        for name, a, b in _VECTORS:
            ports.a.next = a
            ports.b.next = b
            ports.op.next = opmap[name]
            yield delay(1)
            if verbose:
                print(
                    f"{name:>3}: {a:#04x}, {b:#04x} -> {int(ports.y):#04x} "
                    f"(zero={int(ports.zero)}, lt={int(ports.lt)}, "
                    f"carry={int(ports.carry)})"
                )
        raise StopSimulation

    return dut, stim


def convert_demo(path):
    """Convert the demo ALU to Verilog and VHDL under *path*; return the dir."""
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    alu = Alu(width=8)
    alu.hdl(alu.ports()).convert(hdl="Verilog", path=str(out), name="alu")
    alu.hdl(alu.ports()).convert(hdl="VHDL", path=str(out), name="alu")
    return out


if __name__ == "__main__":
    alu_demo(verbose=True).run_sim()
    written = convert_demo("build")
    print(f"converted to {written}/alu.v and {written}/alu.vhd")
