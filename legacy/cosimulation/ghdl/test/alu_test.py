# -*- coding: utf-8 -*-

from myhdl import *

import os
import random

def run_simulation(a_width = 16, b_width = 16, c_width = 2, samples = 20):

    op_width = 2
    res_width = max(a_width, b_width) + 1 + ((2**c_width)-1)

    clk = Signal(False)
    rst = Signal(False)
    a = Signal(intbv(0, min=-2**(a_width-1), max=2**(a_width-1)))
    b = Signal(intbv(0, min=-2**(b_width-1), max=2**(b_width-1)))
    c = Signal(intbv(0)[c_width:])
    op = Signal(intbv(0)[op_width:])
    x = Signal(intbv(0, min=-2**(res_width-1), max=2**(res_width-1)))
    y = Signal(intbv(0, min=-2**(res_width-1), max=2**(res_width-1)))
    
    xops = [
        (lambda al, bl, cl: (0,0)), 
        (lambda al, bl, cl: ((al+bl)<<cl,(al-bl)<<cl)),
        (lambda al, bl, cl: ((al & bl)<<cl,(al | bl)<<cl)),
        (lambda al, bl, cl: (-1,-1))]

    print "ALU_TEST: a(%d bits) b(%d bits) c(%d bits) %d operations x,y(%d bits)" % (a_width, b_width, c_width, 2**op_width, res_width)
    update_template(a_width, b_width, c_width, res_width, op_width)
    os.system("ghdl -a -g  ../../ghdl/myhdl_ghdl_extern.vhdl ../../ghdl/myhdl_ghdl_core.vhdl alu_test.vhdl")
    os.system("ghdl -e -g  -Wl,../../ghdl/myhdl_ghdl_vhpi.o alu_test")
      
    @instance
    def clkdriver():
        while True:
            clk.next = 0
            yield delay(5)
            clk.next = 1
            yield delay(5)
            
    @instance
    def rstdriver():
        rst.next = 1
        yield delay(20)
        rst.next = 0
        
    @instance
    def stim():
        yield rst.negedge
        yield clk.negedge
        for i in range(samples):
            ar = random.randrange(a._min, a._max)
            br = random.randrange(b._min, b._max)
            cr = random.randrange(c._min, c._max)
            a.next = ar
            b.next = br
            c.next = cr
            for i in range(4):
                op.next = i
                yield clk.negedge
                if int(op) == 2:
                    xtest, ytest = xops[i](int(intbv(ar, min=a._min, max=a._max)[a._nrbits:]), int(intbv(br, min=b._min, max=b._max)[b._nrbits:]), cr)
                else:
                    xtest, ytest = xops[i](ar, br, cr)
                if (xtest != x) and (ytest != y):
                    print "ERROR: (time %d) for a=%d, b=%d, c=%d, op=%d, x: %d != %d , y: %d != %d" % (now(), a, b, c, op, x, xtest, y, ytest)
        print "End stimulus at time %d" % now()
        raise StopSimulation
    
    cosim = Cosimulation("ghdl -r alu_test --vcd=alu_test.vcd", clk=clk, rst=rst, a_term=a, b_term=b, c_term=c, operation=op, x_term=x, y_term=y)

    sim = Simulation(clkdriver, rstdriver, stim, cosim)
    sim.run()
    
def update_template(a_width, b_width, c_width, res_width, op_width):
    template = open("alu_test_template.vhdl")
    dest = open("alu_test.vhdl", "w")
    
    for l in template.readlines():
        r = l.replace("MYHDL_TEMPLATE_A_WIDTH", str(a_width))
        r = r.replace("MYHDL_TEMPLATE_B_WIDTH", str(b_width))
        r = r.replace("MYHDL_TEMPLATE_C_WIDTH", str(c_width))
        r = r.replace("MYHDL_TEMPLATE_RES_WIDTH", str(res_width))
        r = r.replace("MYHDL_TEMPLATE_OP_WIDTH", str(op_width))
        dest.write(r)
    template.close()
    dest.close()

if __name__ == "__main__":
    run_simulation(8,8,4,10)
    