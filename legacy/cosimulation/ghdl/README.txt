Co-simulation for GHDL

Co-simulation support is done through the VHPI interface available in GHDL, 
as described in the User Guide:

http://ghdl.free.fr/site/uploads/Main/ghdl_user_guide/Interfacing-to-other-languages.html

Use entity "myhdl_ghdl_core" in <myhdl_ghdl_core.vhdl> to write a testbench 
to connect with MyHDL. The testbench must define the following generics:

* C_FROM_WIDTH : Total number of bits for signals driven by MyHDL
* C_TO_WIDTH : Total number of bits for signals read MyHDL
* C_TIMERES : Duration of one timestep in MyHDL. This value allows to synchronize
              time between GHDL and MyHDL in the correct time units.
* C_FROM_SIGINFO : List of space separated values with the signal descriptions 
                   driven by MyHDL. Must follow format
                   <signal_name> <bit_width>
                   with "signal_name" being the same name used in MyHDL
* C_TO_SIGINFO   : List of space separated values with the signal descriptions 
                   read by MyHDL. Same format as before.
                   
Testbench must use the following signals:

* To_sigvector : All signals read by MyHDL concatenated in a single signal following
                 the same order in C_TO_SIGINFO
* From_sigvector : All signals driven by MyHDL concatenated in a single signal 
                   following the same order in C_FROM_SIGINFO
                   
Keep track of the signals descriptions when mapping signals from myhdl_ghdl_core
to your testbench. Order and bit-order (msb downto lsb in bit_vectors) are 
important.

Cosimulation for GHDL is based on icarus cosimulation code, relying on 
Unix-style pipes IPC. Sockets IPC (UNIX, IPv4 and IPv6) are also available.

Test is available on the "test" subdirectory, just run "python test_all.py".

Thanks to Yann Guidon for ghdl_env, downloaded from http://ygdes.com/GHDL/ghdl_env/

Issues:

* Signal descriptions must be stored in string generics, there's no introspection 
available with this method.

* Signal propagation could be delayed C_TIMERES at most, because the entity 
"myhdl_ghdl_core" manage time delays until next MyHDL event, unable to explicitly
wait for a delta time.

* inc_test features using environment variables to pass values to VHDL. However, only 
variables that can change in runtime 

* Type is restricted to std_logic and std_logic_vector. Integers should be converted
to 32-bit std_logic_vector.

Last update: Sun, 31 Mar 2013 14:51:15 +0200