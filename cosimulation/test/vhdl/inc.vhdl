library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity inc is
    generic(n : integer := 8);
    port(
        clock  : in  std_logic;
        enable : in  std_logic;
        reset  : in  std_logic;
        count  : out std_logic_vector(15 downto 0)
    );
end entity inc;

architecture rtl of inc is

    signal count_reg : integer := 0;

    begin
        count_proc : process(clock, enable, reset)
            begin
                if rising_edge(clock) or falling_edge(reset) then
                    if reset = '0' then
                        count_reg <= 0;
                    elsif enable = '1' then
                        count_reg <= (count_reg + 1) mod n;
                    end if;
                end if;
        end process count_proc;
        count <= std_logic_vector(to_unsigned(count_reg, 16));
end architecture rtl;
