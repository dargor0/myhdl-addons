Co-simulation for GHDL

Co-simulation support is done through the VHPI interface available in GHDL, 
as described in the User Guide:

http://ghdl.free.fr/site/uploads/Main/ghdl_user_guide/Interfacing-to-other-languages.html

Use entity "myhdl_ghdl_core" in myhdl_ghdl_core.vhdl to write a testbench 
to connect with MyHDL. The testbench must define the following generics:

* C_FROM_WIDTH : Total number of bits for signals driven by MyHDL
* C_TO_WIDTH : Total number of bits for signals read MyHDL
* C_TIMERES : Duration of one timestep in MyHDL. This value allows to synchronize
              time between GHDL and MyHDL in the correct time units.
* C_FROM_SIGINFO : List of space separated values with the signal descriptions 
                   driven by MyHDL. Must follow format
                   <signal_name> <bit_width>
                   signal_name is the same name used in MyHDL
* C_TO_SIGINFO   : List of space separated values with the signal descriptions 
                   read by MyHDL.
                   
Testbench must use the following signals:

* To_sigvector : All signals read by MyHDL concatenated in a single signal following
                 the same order in C_TO_SIGINFO
* From_sigvector : All signals driven by MyHDL concatenated in a single signal 
                   following the same order in C_FROM_SIGINFO
                   
Keep track of the signals descriptions when mapping 

Cosimulation for GHDL is based on icarus cosimulation code, relying on 
Unix-style pipes IPC. Initial support for sockets IPC is available.

Test is available on the "test" subdirectory, just run "python test_all.py".
