# change here to point to your local source dir
MYHDL_BASEDIR=/usr/local/src/myhdl

GENERAL_TEST=myhdl/test/conversion/general
TOVHDL_TEST=myhdl/test/conversion/toVHDL
LOCALDIR=$(CURDIR)
CONVPATH=$(realpath $(LOCALDIR)/..)

PYTHONPATH = $(MYHDL_BASEDIR):$(CONVPATH)

all: GHDL 

vcom:
	cp vcom_kh.py monkey_kh.py $(MYHDL_BASEDIR)/$(GENERAL_TEST)
	cp vcom_kh.py monkey_kh.py $(MYHDL_BASEDIR)/$(TOVHDL_TEST)
	vlib work_vcom && vmap work_vcom work_vcom
	cd $(MYHDL_BASEDIR)/$(GENERAL_TEST) && vlib work_vcom && vmap work_vcom work_vcom
	cd $(MYHDL_BASEDIR)/$(TOVHDL_TEST) && vlib work_vcom && vmap work_vcom work_vcom
	-py.test monkey_kh.py vcom_kh.py test_*.py
	-cd $(MYHDL_BASEDIR)/$(GENERAL_TEST) && py.test monkey_kh.py vcom_kh.py test_*.py
	-cd $(MYHDL_BASEDIR)/$(TOVHDL_TEST) && py.test monkey_kh.py vcom_kh.py test_*.py

GHDL:
	cp GHDL_kh.py monkey_kh.py $(MYHDL_BASEDIR)/$(GENERAL_TEST)
	cp GHDL_kh.py monkey_kh.py $(MYHDL_BASEDIR)/$(TOVHDL_TEST)
	-py.test monkey_kh.py GHDL_kh.py test_*.py
	-cd $(MYHDL_BASEDIR)/$(GENERAL_TEST) && py.test monkey_kh.py GHDL_kh.py test_*.py
	-cd $(MYHDL_BASEDIR)/$(TOVHDL_TEST) && py.test monkey_kh.py GHDL_kh.py test_*.py

clean:
	-rm -r *.o *.out *.v *.vhd *.pyc *~ *.vcd* *.log *_ghdl modelsim.ini vsim.wlf transcript work*
	-cd $(MYHDL_BASEDIR)/$(GENERAL_TEST) && rm -r *.o *.out *.v *.vhd *.pyc *~ *.vcd* *.log *_ghdl modelsim.ini vsim.wlf transcript work* GHDL_kh.py monkey_kh.py
	-cd $(MYHDL_BASEDIR)/$(TOVHDL_TEST) && rm -r *.o *.out *.v *.vhd *.pyc *~ *.vcd* *.log *_ghdl modelsim.ini vsim.wlf transcript work* GHDL_kh.py monkey_kh.py
