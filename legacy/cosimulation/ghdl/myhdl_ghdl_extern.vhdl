--  MyHDL co-simulation support for GHDL
--  * entity for external module implementation
--  
--  Author:  Oscar Diaz <oscar.dc0@gmail.com>
--  Date:    16-02-2013
-- 
--  This code is free software; you can redistribute it and/or
--  modify it under the terms of the GNU Lesser General Public
--  License as published by the Free Software Foundation; either
--  version 3 of the License, or (at your option) any later version.
-- 
--  This code is distributed in the hope that it will be useful,
--  but WITHOUT ANY WARRANTY; without even the implied warranty of
--  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
--  Lesser General Public License for more details.
-- 
--  You should have received a copy of the GNU Lesser General Public
--  License along with this package; if not, see 
--  <http://www.gnu.org/licenses/>.
--  

library ieee;
use ieee.std_logic_1164.all;

package extern_vhpi_interface is
    function startup_simulation (curtime, timeres : time ; from_signal,to_signal : string) return integer;
    attribute foreign of startup_simulation : function is "VHPIDIRECT startup_simulation";

    function update_signal (datain, dataout : std_logic_vector ; curtime : time) return integer;
    attribute foreign of update_signal : function is "VHPIDIRECT update_signal";
    
    function next_timetrigger(curtime : time) return time;
    attribute foreign of next_timetrigger : function is "VHPIDIRECT next_timetrigger";    
end package extern_vhpi_interface;

package body extern_vhpi_interface is
    function startup_simulation (curtime, timeres : time ; from_signal, to_signal : string) return integer is
        begin
            assert false severity failure;
    end function startup_simulation;
    
    function update_signal (datain, dataout : std_logic_vector ; curtime : time) return integer is
        begin
            assert false severity failure;
    end function update_signal;
    
    function next_timetrigger(curtime : time) return time is
        begin
            assert false severity failure;
    end function next_timetrigger;
end extern_vhpi_interface;
