"""Reusable-component demo: use multipliers and convert them to Verilog + VHDL.

Shows the standard component flow (``ports()`` -> ``hdl(ports)``) for the
combinational :class:`Multiplier` and the shift-and-add
:class:`SequentialMultiplier`, plus the mandatory HDL conversion.

Run with::

    python examples/components_multiplier.py
"""

from pathlib import Path

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import Multiplier, SequentialMultiplier

_VECTORS = (
    (0x0F, 0x03),
    (0xFF, 0xFF),  # -1 * -1 = 1 (two's complement)
    (0x80, 0x02),  # -128 * 2 = -256
)


@block
def multiplier_demo(verbose=False):
    """Simulate the full-precision combinational ``Multiplier``."""
    mul = Multiplier(width=8, signed=True)
    ports = mul.ports()
    dut = mul.hdl(ports)

    @instance
    def stim():
        for a, b in _VECTORS:
            ports.a.next = a
            ports.b.next = b
            yield delay(1)
            if verbose:
                print(f"{a:#04x} * {b:#04x} = {int(ports.y):#06x}")
        raise StopSimulation

    return dut, stim


@block
def seqmultiplier_demo(verbose=False):
    """Simulate the radix-4 ``SequentialMultiplier`` start/busy/done flow."""
    mul = SequentialMultiplier(width=8, signed=True, radix=4)
    ports = mul.ports()
    dut = mul.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0  # active-low: assert
        yield ports.clk.posedge
        ports.reset.next = 1  # release
        yield ports.clk.posedge

        for a, b in _VECTORS:
            ports.a.next = a
            ports.b.next = b
            ports.start.next = 1
            yield ports.clk.posedge
            ports.start.next = 0
            while not ports.done:
                yield ports.clk.posedge
            yield delay(1)
            if verbose:
                print(f"{a:#04x} * {b:#04x} = {int(ports.y):#06x} (sequential)")
        raise StopSimulation

    return clkgen, dut, stim


def convert_demo(path):
    """Convert both multipliers to Verilog and VHDL under *path*; return the dir."""
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    comb = Multiplier(width=8)
    comb.hdl(comb.ports()).convert(hdl="Verilog", path=str(out), name="multiplier")
    comb.hdl(comb.ports()).convert(hdl="VHDL", path=str(out), name="multiplier")
    seq = SequentialMultiplier(width=8)
    seq.hdl(seq.ports()).convert(hdl="Verilog", path=str(out), name="seqmultiplier")
    seq.hdl(seq.ports()).convert(hdl="VHDL", path=str(out), name="seqmultiplier")
    return out


if __name__ == "__main__":
    multiplier_demo(verbose=True).run_sim()
    seqmultiplier_demo(verbose=True).run_sim()
    written = convert_demo("build")
    print(f"converted to {written}/multiplier.v, {written}/multiplier.vhd, ...")
