import os

from myhdl import Cosimulation

vhdl_srcroute = "../../test/vhdl"

cmd = "make -s -C %s dut_dff_clkout"
      
def dff_clkout(clkout, q, d, clk, reset):
    os.system(cmd % vhdl_srcroute)
    return Cosimulation("%s/dut_dff_clkout"  % vhdl_srcroute, **locals())