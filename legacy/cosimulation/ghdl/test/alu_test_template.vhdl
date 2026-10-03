library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use work.myhdl_ghdl_core;

entity alu_test is
    generic(
        a_width : integer := MYHDL_TEMPLATE_A_WIDTH;
        b_width : integer := MYHDL_TEMPLATE_B_WIDTH;
        c_width : integer := MYHDL_TEMPLATE_C_WIDTH;
        res_width : integer := MYHDL_TEMPLATE_RES_WIDTH;
        op_width : integer := MYHDL_TEMPLATE_OP_WIDTH
    );
end entity alu_test;

architecture rtl of alu_test is
    
    constant c_barrel : integer := 2**c_width;
--     constant res_width : integer := max(a_width, b_width) + (c_barrel - 1) + 1;

    signal a_term : std_logic_vector((a_width - 1) downto 0) := (others => '0');
    signal b_term : std_logic_vector((b_width - 1) downto 0) := (others => '0');
    signal c_term : std_logic_vector((c_width - 1) downto 0) := (others => '0');
    signal operation : std_logic_vector((op_width - 1) downto 0) := (others => '0');
    signal x_term : std_logic_vector((res_width - 1) downto 0) := (others => '0');
    signal y_term : std_logic_vector((res_width - 1) downto 0) := (others => '0');
    signal clk : std_logic := '0';
    signal rst : std_logic := '0';
    signal opzero : std_logic := '0';
    signal opone : std_logic := '0';

    signal x_calc : std_logic_vector((res_width - 1) downto 0) := (others => '0');
    signal y_calc : std_logic_vector((res_width - 1) downto 0) := (others => '0');
    signal x_barr : std_logic_vector((res_width - 1) downto 0) := (others => '0');
    signal y_barr : std_logic_vector((res_width - 1) downto 0) := (others => '0');
    signal op_int : integer := 0;

    -- **** Co-simulation stuff
    -- TO: x_term, y_term
    constant to_width : integer := 2*res_width;
    -- FROM: clk, rst, a_term, b_term, c_term, operation
    constant from_width : integer := a_width + b_width + c_width + op_width + 2 ;
    -- time res
    constant timeres : time := 1 ns;
    -- input information data (to MyHDL)
    constant to_info : string := "x_term " & integer'image(res_width) & " y_term " & integer'image(res_width);
    -- output information data (from MyHDL)
    constant from_info : string := "clk 1 rst 1 a_term " & integer'image(a_width) & " b_term " & integer'image(b_width)  & " c_term " & integer'image(c_width) & " operation " & integer'image(op_width);
    
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
        -- signal mapping
        to_vec((res_width-1) downto 0) <= x_term;
        to_vec(((2*res_width)-1) downto res_width) <= y_term;

        clk <= from_vec(0);
        rst <= from_vec(1);
        a_term <= from_vec(((a_width-1) + 2) downto 2);
        b_term <= from_vec(((b_width-1) + a_width + 2) downto (a_width + 2));
        c_term <= from_vec(((c_width-1) + b_width + a_width + 2) downto (b_width + a_width + 2));
        operation <= from_vec(((op_width-1) + c_width + b_width + a_width + 2) downto (c_width + b_width + a_width + 2));

        -- ALU functions
        op_conv: process(rst, operation)
            begin
                if rst = '0' then
                    op_int <= to_integer(unsigned(operation));
                else
                    op_int <= 0;
                end if;
        end process op_conv;
        
        alu_proc : process(a_term, b_term, op_int)
            begin
                case op_int is
                    when 0 =>
                        x_calc <= (others => '0');
                        y_calc <= (others => '0');
                        opzero <= '1';
                        opone  <= '0';
                    when 1 =>
                        x_calc <= std_logic_vector(to_signed(to_integer(signed(a_term)) + to_integer(signed(b_term)), res_width));
                        y_calc <= std_logic_vector(to_signed(to_integer(signed(a_term)) - to_integer(signed(b_term)), res_width));
                        opzero <= '0';
                        opone  <= '0';
                    when 2 =>
                        for i in 0 to (res_width - 1) loop
                            if (i < a_width) and (i < b_width) then
                                x_calc(i) <= a_term(i) and b_term(i);
                                y_calc(i) <= a_term(i) or b_term(i);
                            elsif (i >= a_width) and (i < b_width) then
                                x_calc(i) <= '0';
                                y_calc(i) <= b_term(i);
                            elsif (i < a_width) and (i >= b_width) then
                                x_calc(i) <= '0';
                                y_calc(i) <= a_term(i);
                            else
                                x_calc(i) <= '0';
                                y_calc(i) <= '0';
                            end if;
                        end loop;
                        opzero <= '0';
                        opone  <= '0';
                    when others =>
                        x_calc <= (others => '1');
                        y_calc <= (others => '1');
                        opzero <= '0';
                        opone  <= '1';
                end case;
        end process alu_proc;
        
        shift_proc: process(rst, x_calc, y_calc, c_term)
            variable idesp : integer := 0;
            begin
                if rst = '0' then
                    for i in 0 to (res_width - 1) loop
                        idesp := i - to_integer(unsigned(c_term));
                        if idesp < 0 then
                            x_barr(i) <= '0';
                            y_barr(i) <= '0';
                        else
                            x_barr(i) <= x_calc(idesp);
                            y_barr(i) <= y_calc(idesp);
                        end if;
                    end loop;
                else
                    x_barr <= (others => '0');
                    y_barr <= (others => '0');
                end if;
        end process shift_proc;
        
        reg_proc: process(clk, rst, x_barr, y_barr)
            begin
                if rising_edge(clk) then
                    if rst = '1' then
                        x_term <= (others => '0');
                        y_term <= (others => '0');
                    else
                        if opzero = '1' then
                            x_term <= (others => '0');
                            y_term <= (others => '0');
                        elsif opone = '1' then
                            x_term <= (others => '1');
                            y_term <= (others => '1');
                        else
                            x_term <= x_barr;
                            y_term <= y_barr;
                        end if;
                    end if;
                end if;
        end process reg_proc;
end architecture rtl;
