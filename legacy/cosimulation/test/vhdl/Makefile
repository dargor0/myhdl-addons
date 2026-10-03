# makefile for GHDL

GHDL=ghdl

# custom options
MYHDLVHPI=myhdl_ghdl_vhpi
MYHDLCORE=myhdl_ghdl_core
MYHDLEXTR=myhdl_ghdl_extern
GHDL_ENV=ghdl_env

GHDLFLAGS=-g 
GHDL_LINK=-Wl,../../ghdl/$(MYHDLVHPI).o -Wl,../../ghdl/$(GHDL_ENV)_c.o 
targets=dut_bin2gray dut_dff dut_dff_clkout dut_inc

# predefined rules
.PHONY : all clean run

all: $(MYHDLVHPI).o $(MYHDLCORE).o $(MYHDLEXTR).o $(GHDL_ENV).o $(targets)

clean:
	$(GHDL) --clean
	-rm work-obj93.cf
	-rm -f *.o

$(MYHDLVHPI).o :
	make -C ../../ghdl/ $@
	
$(MYHDLCORE).o :
	make -C ../../ghdl/ $@

$(MYHDLEXTR).o :
	make -C ../../ghdl/ $@

$(GHDL_ENV).o :
	make -C ../../ghdl/ $@
	
dut_%.o: dut_%.vhdl %.o
	$(GHDL) -a $(GHDLFLAGS) ../../ghdl/$(MYHDLEXTR).vhdl ../../ghdl/$(MYHDLCORE).vhdl ../../ghdl/$(GHDL_ENV).vhdl $<

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

