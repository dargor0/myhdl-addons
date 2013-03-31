library ieee;
use ieee.std_logic_1164.all;

use work.myhdl_ghdl_core;
use work.bin2gray;

entity dut_bin2gray is
    generic(C_WIDTH : integer := 9 );
end entity dut_bin2gray;

architecture sim of dut_bin2gray is

    -- B
    constant to_width : integer := C_WIDTH;
    -- G
    constant from_width : integer := C_WIDTH;
    -- time res
    constant timeres : time := 1 ns;
    -- input information data (to MyHDL)
    constant to_info : string := "G " & integer'image(to_width);
    -- output information data (from MyHDL)
    constant from_info : string := "B " & integer'image(from_width);
    
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
                
        dut_inst : entity bin2gray
            generic map (C_WIDTH => C_WIDTH)
            port map (
                B => from_vec,
                G => to_vec);

end architecture sim;
