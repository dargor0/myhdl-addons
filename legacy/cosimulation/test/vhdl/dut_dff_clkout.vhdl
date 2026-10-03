library ieee;
use ieee.std_logic_1164.all;

use work.myhdl_ghdl_core;
use work.dff_clkout;

entity dut_dff_clkout is
end entity dut_dff_clkout;

architecture sim of dut_dff_clkout is

    -- TO: q, clkout
    constant to_width : integer := 2;
    -- FROM: d, clk, reset
    constant from_width : integer := 3;
    -- time res
    constant timeres : time := 1 ns;
    -- input information data (to MyHDL)
    constant to_info : string := "q 1 clkout 1 ";
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
                
        dut_inst : entity dff_clkout
            port map (
                q => to_vec(0),
                clkout => to_vec(1),
                d => from_vec(0),
                clk => from_vec(1),
                reset => from_vec(2));

end architecture sim;
