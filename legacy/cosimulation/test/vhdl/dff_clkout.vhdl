library ieee;
use ieee.std_logic_1164.all;

entity dff_clkout is
    port(
        clkout : out std_logic;
        q      : out std_logic;
        d      : in  std_logic;
        clk    : in  std_logic;
        reset  : in  std_logic
    );
end entity dff_clkout;

architecture rtl of dff_clkout is

    begin
        dff_proc : process(clk, reset, d)
            begin
                if rising_edge(clk) or falling_edge(reset) then
                    if reset = '0' then
                        q <= '0';
                    else
                        q <= d;
                    end if;
                end if;
        end process dff_proc;
        
        clkout <= clk;
end architecture rtl;
