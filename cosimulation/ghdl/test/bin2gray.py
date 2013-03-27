import os

from myhdl import Cosimulation

vhdl_srcroute = "../../test/vhdl"

cmd = "make -C %s dut_bin2gray"
      
def bin2gray(B, G, width):
    os.environ["C_WIDTH"] = str(width)
    os.system(cmd % vhdl_srcroute)
    return Cosimulation("%s/dut_bin2gray" % vhdl_srcroute, B=B, G=G)
               

    
