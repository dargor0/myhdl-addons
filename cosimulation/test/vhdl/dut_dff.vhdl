library ieee;
use ieee.std_logic_1164.all;

use work.myhdl_ghdl_core;
use work.ghdl_env.all;
use work.dff;

entity dut_dff is
end entity dut_dff;

architecture sim of dut_dff is

    -- TO: q
    constant to_width : integer := 1;
    -- FROM: d, clk, reset
    constant from_width : integer := 3;
    -- time res
    constant timeres : time := 1 ns;
    -- input information data (to MyHDL)
    constant to_info : string := "q 1 ";
    -- output information data (from MyHDL)
    constant from_info : string := "d 1 clk 1 reset 1 ";
    
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
                
        dut_inst : entity dff
            port map (
                q => to_vec(0),
                d => from_vec(0),
                clk => from_vec(1),
                reset => from_vec(2));

end architecture sim;
