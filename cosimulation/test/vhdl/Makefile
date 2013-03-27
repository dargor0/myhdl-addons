# makefile for GHDL

GHDL=ghdl

# custom options
MYHDLVHPI=myhdl_ghdl_vhpi
MYHDLCORE=myhdl_ghdl_core
GHDLENV=ghdl_env

GHDLFLAGS=-g 
GHDL_LINK=-Wl,../../ghdl/$(MYHDLVHPI).o -Wl,../../ghdl/$(GHDLENV)_c.o
targets=dut_bin2gray dut_dff dut_dff_clkout dut_inc

# predefined rules
.PHONY : all clean run

all: $(MYHDLVHPI).o $(MYHDLCORE).o $(GHDLENV)_c.o $(targets)

clean:
	$(GHDL) --clean
	-rm work-obj93.cf
	-rm -f *.o

$(MYHDLVHPI).o :
	make -C ../../ghdl/ $@
	
$(MYHDLCORE).o :
	make -C ../../ghdl/ $@
	
$(GHDLENV)_c.o :
	make -C ../../ghdl/ $@
	
dut_%.o: dut_%.vhdl %.o
	$(GHDL) -a $(GHDLFLAGS) ../../ghdl/$(GHDLENV).vhdl ../../ghdl/$(MYHDLCORE).vhdl $<

dut_bin2gray.o : dut_bin2gray.vhdl bin2gray.o
dut_dff.o : dut_dff.vhdl dff.o
dut_dff_clkout.o : dut_dff_clkout.vhdl dff_clkout.o
dut_inc.o : dut_inc.vhdl inc.o

# basic rules
%.o : %.vhdl
	$(GHDL) -a $(GHDLFLAGS) $<

bin2gray.o : bin2gray.vhdl
dff.o : dff.vhdl
dff_clkout.o : dff_clkout.vhdl
inc.o : inc.vhdl

%: %.o
	$(GHDL) -e $(GHDLFLAGS) $(GHDL_LINK) $@

dut_bin2gray : dut_bin2gray.o
dut_dff : dut_dff.o
dut_dff_clkout : dut_dff_clkout.o
dut_inc : dut_inc.o

