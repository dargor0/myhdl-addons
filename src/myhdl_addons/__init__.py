"""myhdl-addons: MyHDL building blocks for modular hardware systems.

Sub-packages:

* :mod:`myhdl_addons.common` — shared foundation (unified exception
  hierarchy, generic config helpers, :class:`SignalView`);
* :mod:`myhdl_addons.bus_common` — protocol-agnostic bus layer;
* :mod:`myhdl_addons.wishbone` / :mod:`myhdl_addons.axi` — bus libraries;
* :mod:`myhdl_addons.components` — independent, configurable components;
* :mod:`myhdl_addons.riscv` — the RV32IC core library.

This package targets MyHDL 0.11.x and Python 3.10+.
"""

__version__ = "0.2.0"
