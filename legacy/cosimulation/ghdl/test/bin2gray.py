import os
import time

from myhdl import Cosimulation

vhdl_srcroute = "../../test/vhdl"

def build_bin2gray_vhdl(width):
    template = open("%s/dut_bin2gray_template.vhdl" % vhdl_srcroute)
    dest = open("%s/dut_bin2gray.vhdl" % vhdl_srcroute, "w")
    width_str = str(width)
    
    for l in template.readlines():
        dest.write(l.replace("MYHDL_TEMPLATE_C_WIDTH", width_str))
    template.close()
    dest.close()
    os.system("rm %s/dut_bin2gray.o %s/dut_bin2gray" % tuple([vhdl_srcroute]*2))
      
def bin2gray(B, G, width):
    build_bin2gray_vhdl(width)
    os.system("make -s -C %s dut_bin2gray" % vhdl_srcroute)
    return Cosimulation("%s/dut_bin2gray" % vhdl_srcroute, B=B, G=G)

