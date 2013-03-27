library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb is
end entity tb;

architecture rtl of tb is

    signal a : std_logic_vector(16 downto 0);
    signal b : std_logic_vector(4 downto 0);
    signal c : std_logic_vector(9 downto 0);
    signal clk : std_logic;

    begin
        sum_proc : process(a, b)
            begin
                c <= a + b;
                assert false report "VHDL c=" & integer'image(to_integer(c)) & " a=" & integer'image(to_integer(a)) & " b=" & integer'image(to_integer(b)) severity note;
        end process sum_proc;
        count <= std_logic_vector(unsigned(count_reg));
        
        clk_proc : process
            begin
                clk <= '0';
                wait for 50ns;
                clk <= '1';
                wait for 50ns;
        end process;
end architecture rtl;

-- module tb;
--    
--    reg [16:0] a;
--    reg [4:0] b;
--    reg [9:0] c;
--    reg 	     clk;
--    
--   
--    initial
--      begin
-- 	$to_myhdl(c);
-- 	$from_myhdl(a, b);
--      end
-- 
--    always @ (a, b) begin
--       c = a + b;
--       $display("Verilog: %d c =%d a=%d b=%d", $time, c, a, b);
--       
--    end
-- 
--    initial begin
--       clk = 0;
-- 
--       forever begin
-- 	 clk = #50 ~clk;
--       end
--    end
--    
--    
-- endmodule // tb
