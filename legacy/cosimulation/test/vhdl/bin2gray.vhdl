library ieee;
use ieee.std_logic_1164.all;

entity bin2gray is
    generic (C_WIDTH : integer := 8);
    port (
        B : in  std_logic_vector((C_WIDTH - 1) downto 0);
        G : out std_logic_vector((C_WIDTH - 1) downto 0)
    );
end entity bin2gray;

architecture rtl of bin2gray is

    signal extB : std_logic_vector(C_WIDTH downto 0) := (others => '0');

    begin
        extB(C_WIDTH) <= '0';
        extB((C_WIDTH-1) downto 0) <= B;
        
        sigs : for i in 0 to (C_WIDTH - 1) generate
            G(i) <= extB(i+1) xor extB(i);
        end generate sigs;
        
end architecture rtl;
