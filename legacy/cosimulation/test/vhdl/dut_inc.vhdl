library ieee;
use ieee.std_logic_1164.all;

use work.myhdl_ghdl_core;
use work.ghdl_env.all;
use work.inc;

entity dut_inc is
end entity dut_inc;

architecture sim of dut_inc is

    -- runtime parameter
    constant inc_n : integer := getenv("INC_N", 8);

    -- TO: count
    constant to_width : integer := 16;
    -- FROM: enable, clock, reset
    constant from_width : integer := 3;
    -- time res
    constant timeres : time := 1 ns;
    -- input information data (to MyHDL)
    constant to_info : string := "count 16 ";
    -- output information data (from MyHDL)
    constant from_info : string := "enable 1 clock 1 reset 1 ";
    
    -- signals
    signal to_vec : std_logic_vector((to_width - 1) downto 0) := (others => '0');
    signal from_vec : std_logic_vector((from_width - 1) downto 0) := (others => '0');

    begin
        cosim_inst : entity myhdl_ghdl_core
            generic map (
                C_TO_WIDTH => to_width,
                C_FROM_WIDTH => from_width,
                C_TIMERES => timeres,
                C_TO_SIGINFO => to_info,
                C_FROM_SIGINFO => from_info)
            port map (
                To_sigvector => to_vec,
                From_sigvector => from_vec);
                
        dut_inst : entity inc
            generic map(n => inc_n)
            port map (
                enable => from_vec(0),
                clock => from_vec(1),
                reset => from_vec(2),
                count => to_vec);

end architecture sim;
