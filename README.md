myhdl-addons
============

MyHDL related subprojects

* cosimulation : GHDL support for co-simulation using VHPI interface.
* conversion : VHDL convertor that keeps hierarchy
* bus : definitions and utilities for buses. Currently only Wishbone bus support is included.
* utils :
  - signal_monitor.py : object for VCD generation as "signal probe"
  - vhdl_lib.py : Base library for VHDL file management (parsing and code generation)
  - cosim_helper.py : Testbench generator for use in GHDL co-simulation
