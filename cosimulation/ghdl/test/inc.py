import os

from myhdl import Cosimulation

vhdl_srcroute = "../../test/vhdl"

cmd = "make -C %s dut_inc"
      
def inc(count, enable, clock, reset, n):
    os.environ["INC_N"] = str(n)
    os.system(cmd % vhdl_srcroute)
    return Cosimulation("%s/dut_inc" % vhdl_srcroute, **locals())