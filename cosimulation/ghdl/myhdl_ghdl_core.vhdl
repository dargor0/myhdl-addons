-- Cosimulation core: glue for external module implementation

-- Author: Oscar Diaz

package extern_vhpi_interface is
    type intreg_t is array (integer range <>) of integer;
    
    function startup_simulation (curtime, timeres : time ; from_signal,to_signal : string) return integer;
    attribute foreign of startup_simulation : function is "VHPIDIRECT startup_simulation";

    function update_signal (datain, dataout : intreg_t ; curtime : time) return integer;
    attribute foreign of update_signal : function is "VHPIDIRECT update_signal";
    
    function next_timetrigger(curtime : time) return time;
    attribute foreign of next_timetrigger : function is "VHPIDIRECT next_timetrigger";
end package extern_vhpi_interface;

package body extern_vhpi_interface is
    function startup_simulation (curtime, timeres : time ; from_signal, to_signal : string) return integer is
        begin
            assert false severity failure;
    end function startup_simulation;
    
    function update_signal (datain, dataout : intreg_t ; curtime : time) return integer is
        begin
            assert false severity failure;
    end function update_signal;
    
    function next_timetrigger(curtime : time) return time is
        begin
            assert false severity failure;
    end function next_timetrigger;
end extern_vhpi_interface;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.extern_vhpi_interface.all;

entity myhdl_ghdl_core is
    generic (
        C_FROM_WIDTH  : integer := 32;
        C_TO_WIDTH : integer := 32;
        C_TIMERES      : time := 1 ns;
        C_FROM_SIGINFO : string := "";
        C_TO_SIGINFO   : string := ""
        );
    port (
        To_sigvector   : in  std_logic_vector((C_TO_WIDTH-1) downto 0); -- input
        From_sigvector : out std_logic_vector((C_FROM_WIDTH-1) downto 0) -- output
    );
end entity myhdl_ghdl_core;

architecture sim of myhdl_ghdl_core is

    constant to_siginfo_integer_count : integer := (C_TO_WIDTH / 32) + 1;
    constant from_integer_count : integer := (C_FROM_WIDTH / 32) + 1;
    constant from_lastint_size : integer := (C_FROM_WIDTH mod 32);

    begin
        startup : process
            variable ret : integer := 0;
            begin
                ret := startup_simulation(now, C_TIMERES, C_FROM_SIGINFO, C_TO_SIGINFO);
                assert ret = 0 report "FATAL: startup_simulation() returned error" severity failure;
                wait;
        end process startup;

        regmanager : process
            variable ret : integer := 0;
            variable deltasteps : integer := 0;
            variable out_slv : std_logic_vector((C_FROM_WIDTH-1) downto 0);
            variable temp_in : intreg_t(0 to (to_siginfo_integer_count - 1)) := (others => 0);
            variable temp_out : intreg_t(0 to (from_integer_count - 1)) := (others => 0);
            variable timedelta : time := 0 ns;
            begin
                mainloop: loop
                    assert false report "INFO: regmanager -> update running..." severity note;
                    for i in (to_siginfo_integer_count - 1) downto 0 loop
                        if i = (to_siginfo_integer_count - 1) then
                            temp_in(i) := to_integer(unsigned(To_sigvector((C_TO_WIDTH-1) downto (i*32))));
                            assert false report "INFO: last temp_in(" & integer'image(i) & ")=" & integer'image(temp_in(i)) severity note;
                            assert false report "INFO: last temp_out(" & integer'image(i) & ")=" & integer'image(temp_out(i)) severity note;
                        else
                            temp_in(i) := to_integer(unsigned(To_sigvector(((i*32)+31) downto (i*32))));
                            assert false report "INFO: temp_in(" & integer'image(i) & ")=" & integer'image(temp_in(i)) severity note;
                            assert false report "INFO: temp_out(" & integer'image(i) & ")=" & integer'image(temp_out(i)) severity note;
                        end if;
                    end loop;
                    ret := update_signal(temp_in, temp_out, now);
                    assert false report "INFO: update_signal returns " & integer'image(ret) severity note;
                    assert ret >= 0 report "FATAL: regmanager->update_signal() returned error" severity failure;
                    for i in (from_integer_count - 1) downto 0 loop
                        if i = (from_integer_count - 1) then
                            out_slv((C_FROM_WIDTH-1) downto (i*32)) := std_logic_vector(to_unsigned(temp_out(i), from_lastint_size));
                            assert false report "INFO: last temp_out(" & integer'image(i) & ")=" & integer'image(temp_out(i)) severity note;
                        else
                            out_slv(((i*32)+31) downto (i*32)) := std_logic_vector(to_unsigned(temp_out(i), 32));
                            assert false report "INFO: temp_out(" & integer'image(i) & ")=" & integer'image(temp_out(i)) severity note;
                        end if;
                    end loop;
                    assert false report "INFO: timetrigger -> finish update" severity note;
                    From_sigvector <= out_slv;
                    case ret is
                        when 0 =>
                            -- UPDATE_END    0 // end simulation
                            assert false report "INFO: end simulation." severity note;
                            wait;
                        when 1 =>
                            -- UPDATE_SIGNAL  1 // next update need a signal trigger or small time delay
                            deltasteps := 0;
                            assert false report "INFO: update signal" severity note;
                            wait on To_sigvector for C_TIMERES;
                            next;
                        when 2 =>
                            -- UPDATE_TIME   2 // next update will be at a time delay
                            deltasteps := 0;
                            timedelta := next_timetrigger(now);
                            assert false report "INFO: update time delta=" & time'image(timedelta) severity note;
                            wait for timedelta;
                            next;
                        when 3 =>
                            -- UPDATE_DELTA 3 // next update need a delta step
                            assert false report "INFO: update delta count=" & integer'image(deltasteps) severity note;
                            deltasteps := deltasteps + 1;
                            -- Hardcode max deltasteps to 10
                            if deltasteps > 10 then
                                assert false report "FATAL: deltasteps limit reached (10)" severity failure;
                            end if;
                            next;
                        when others =>
                            -- UPDATE_ERROR
                            assert false report "FATAL: update error" severity failure;
                            exit;
                    end case;
                end loop;
        end process regmanager;
end architecture sim;
