# change here to point to your local source dir
MYHDL_BASEDIR=/usr/local/src/myhdl

GENERAL_TEST=myhdl/test/conversion/general
TOVHDL_TEST=myhdl/test/conversion/toVHDL
LOCALDIR=$(CURDIR)
CONVPATH=$(realpath $(LOCALDIR)/..)

PYTHONPATH = $(MYHDL_BASEDIR):$(CONVPATH)

all: GHDL 

#vcom:
#	py.test vcom.py test_*.py

GHDL:
	cp GHDL_kh.py monkey_kh.py $(MYHDL_BASEDIR)/$(GENERAL_TEST)
	cp GHDL_kh.py monkey_kh.py $(MYHDL_BASEDIR)/$(TOVHDL_TEST)
	py.test monkey_kh.py GHDL_kh.py test_structural.py
	cd $(MYHDL_BASEDIR)/$(GENERAL_TEST) && py.test monkey_kh.py GHDL_kh.py test_*.py
	cd $(MYHDL_BASEDIR)/$(TOVHDL_TEST) && py.test monkey_kh.py GHDL_kh.py test_*.py

clean:
	-rm *.o *.out *.v *.vhd *.pyc *~ *.vcd* *.log *_ghdl
	-cd $(MYHDL_BASEDIR)/$(GENERAL_TEST) && rm *.o *.out *.v *.vhd *.pyc *~ *.vcd* *.log *_ghdl GHDL_kh.py monkey_kh.py
	-cd $(MYHDL_BASEDIR)/$(TOVHDL_TEST) && rm *.o *.out *.v *.vhd *.pyc *~ *.vcd* *.log *_ghdl GHDL_kh.py monkey_kh.py
