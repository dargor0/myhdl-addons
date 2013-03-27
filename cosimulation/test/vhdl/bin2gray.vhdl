library ieee;
use ieee.std_logic_1164.all;

entity bin2gray is
    generic (c_width : integer := 8);
    port (
        B : in  std_logic_vector((c_width - 1) downto 0);
        G : out std_logic_vector((c_width - 1) downto 0)
    );
end entity bin2gray;

architecture rtl of bin2gray is

    signal extB : std_logic_vector(c_width downto 0) := (others => '0');

    begin
        extB(c_width) <= '0';
        extB((c_width-1) downto 0) <= B;
        
        sigs : for i in 0 to (c_width - 1) generate
            G(i) <= extB(i+1) xor extB(i);
        end generate sigs;
        
end architecture rtl;
