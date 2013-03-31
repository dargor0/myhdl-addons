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
use ieee.numeric_std.all;
use work.extern_vhpi_interface.all;

entity myhdl_ghdl_core is
    generic (
        C_FROM_WIDTH   : integer := 32;
        C_TO_WIDTH     : integer := 32;
        C_TIMERES      : time := 1 ns;
        C_FROM_SIGINFO : string := "";
        C_TO_SIGINFO   : string := ""
        );
    port (
        To_sigvector   : in  std_logic_vector((C_TO_WIDTH-1) downto 0);
        From_sigvector : out std_logic_vector((C_FROM_WIDTH-1) downto 0)
    );
end entity myhdl_ghdl_core;

architecture sim of myhdl_ghdl_core is

    constant to_siginfo_integer_count : integer := (C_TO_WIDTH / 32) + 1;
    constant from_integer_count       : integer := (C_FROM_WIDTH / 32) + 1;
    constant from_lastint_size        : integer := (C_FROM_WIDTH mod 32);

    begin
        startup : process
            variable ret : integer := 0;
            begin
                ret := startup_simulation(now, C_TIMERES, C_FROM_SIGINFO, C_TO_SIGINFO);
                assert ret = 0 report "FATAL: startup_simulation() returned error " & integer'image(ret) severity failure;
                wait;
        end process startup;

        regmanager : process
            variable ret        : integer := 0;
            variable deltasteps : integer := 0;
            variable temp_in    : std_logic_vector((C_TO_WIDTH-1) downto 0) := (others => '0');
            variable temp_out   : std_logic_vector((C_FROM_WIDTH-1) downto 0) := (others => '0');
            variable timedelta  : time := 0 ns;
            begin
                mainloop: loop
                    temp_in := To_sigvector;
                    ret := update_signal(temp_in, temp_out, now);
                    assert ret >= 0 report "FATAL: regmanager->update_signal() returned error " & integer'image(ret) severity failure;
                    From_sigvector <= temp_out;
                    case ret is
                        when 0 =>
                            -- UPDATE_END    0 // end simulation
                            -- assert false report "INFO: end simulation." severity note;
                            wait;
                        when 1 =>
                            -- UPDATE_SIGNAL  1 // next update need a signal trigger or small time delay
                            deltasteps := 0;
                            wait on To_sigvector for C_TIMERES;
                            next;
                        when 2 =>
                            -- UPDATE_TIME   2 // next update will be at a time delay
                            deltasteps := 0;
                            timedelta := next_timetrigger(now);
                            wait for timedelta;
                            next;
                        when 3 =>
                            -- UPDATE_DELTA 3 // next update need a delta step
                            deltasteps := deltasteps + 1;
                            -- Hardcode max deltasteps to 10
                            assert deltasteps < 10 report "FATAL: deltasteps limit reached (10)" severity failure;
                            next;
                        when others =>
                            -- UPDATE_ERROR
                            assert false report "FATAL: update error" severity failure;
                            exit;
                    end case;
                end loop;
        end process regmanager;
end architecture sim;
