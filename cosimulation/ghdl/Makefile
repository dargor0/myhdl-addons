# makefile for GHDL

# ghdl_env downloaded from http://ygdes.com/GHDL/ghdl_env/

CC=gcc
GHDL=ghdl
CFLAGS=-Wall -g -I.

# custom options
MYHDLVPI=myhdl_ghdl_vhpi

# some predefined options
GHDLFLAGS=
GHDL_LINK=-Wl,myhdl_ghdl_vhpi.o -Wl,ghdl_env_c.o

# predefined rules
.PHONY : all clean

all: myhdl_ghdl_core.o ghdl_env_c.o ghdl_env.o

# myhdl_ghdl_vhpi.so: myhdl_ghdl_vhpi.o
# 	$(CC) --shared -Wl,-soname,$(MYHDLVPI).so -o $@ $^

myhdl_ghdl_vhpi.o: myhdl_ghdl_vhpi.c
	$(CC) -c -fPIC $(CFLAGS) $^
	
ghdl_env_c.o: ghdl_env.c
	$(CC) -c -fPIC $(CFLAGS) -o $@ $<

myhdl_ghdl_core.o : myhdl_ghdl_core.vhdl
	$(GHDL) -a $(GHDLFLAGS) $^
	
ghdl_env.o : ghdl_env.vhdl
	$(GHDL) -a $(GHDLFLAGS) $^

clean:
	$(GHDL) --clean
	-rm work-obj93.cf
	-rm -f *.o
