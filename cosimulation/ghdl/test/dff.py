import os

from myhdl import Cosimulation

vhdl_srcroute = "../../test/vhdl"

cmd = "make -C %s dut_dff"
      
def dff(q, d, clk, reset):
    os.system(cmd % vhdl_srcroute)
    return Cosimulation("%s/dut_dff"  % vhdl_srcroute, **locals())