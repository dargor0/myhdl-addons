import os
import glob
import warnings
import random
random.seed(2)

from myhdl import *
from myhdl.conversion import verify, analyze
from myhdl.conversion._verify import _hdlMap as hdlMap

# check toVHDL_kh or toVerilog_kh use
if hdlMap[verify.simulator] == "VHDL":
    kh_convertor = toVHDL
    kh_enabled = (str(toVHDL).find("toVHDL_kh") > 0)
    if not kh_enabled:
        warnings.warn("Missing toVHDL_kh() support. Testing standard toVHDL()")
elif hdlMap[verify.simulator] == "Verilog":
    kh_convertor = toVerilog
    kh_enabled = (str(toVerilog).find("toVerilog_kh") > 0)
    if not kh_enabled:
        warnings.warn("Missing toVerilog_kh() support. Testing standard toVerilog()")
    

# test components
def onebit_full_adder(a, b, s, cin, cout):
    """
    1-bit full adder
    """
    @always_comb
    def adder_logic():
        s.next = a ^ b ^ cin
        cout.next = (a & b) | (cin & (a ^ b))
    return adder_logic
    
def structural_adder(a, b, s, cin, cout, width=8):
    """
    Multi-bit full adder: structural description
    """
    adder = []
    carry_list = [cin] + [Signal(False) for x in range(width-1)] + [cout]
    sout_list = [Signal(False) for x in range(width)]
    sout = ConcatSignal(*sout_list)
    for i in range(width):
        adder.append(onebit_full_adder(a(i), b(i), sout_list[i], carry_list[i], carry_list[i+1]))
    @always_comb
    def sproc():
        s.next = sout
    return instances()
    
def functional_adder(a, b, s, cin, cout, width=8):
    """
    Multi-bit full adder: behavioral description
    """
    s_temp = Signal(intbv(0)[width+1:])
    @always_comb
    def adder_proc():
        s_temp.next = a + b + cin
    @always_comb
    def output_proc():
        s.next = s_temp[width:]
        cout.next = s_temp[width]
    return instances()
    
def reg_noparam(clk, rst, d, q):
    """
    Simple register: data width inferred from arguments
    """
    qlen = len(q)
    @always(clk.posedge, rst.negedge)
    def reg():
        if rst == 0:
            q.next = 0
        else:
            q.next = d[qlen:]
    return reg
            
def reg_width(clk, rst, d, q, width=8):
    """
    Simple register: data width passed explicitly
    """
    @always(clk.posedge, rst.negedge)
    def reg():
        if rst == 0:
            q.next = 0
        else:
            q.next = d[width:]
    return reg
    
def compare(a, b, eq):
    """
    Simple comparator
    """
    @always_comb
    def logic():
        eq.next = (a == b)
    return logic
    
def multi_reg0(clk, rst, data_in, eq, widths=[8]):
    """
    Test single component - multiple instances, 
    with constant included
    """
    temp_a = Signal(intbv(0)[widths[0]:])
    temp_b = Signal(intbv(0)[widths[0]:])
    
    reg_a = reg_width(clk, rst, data_in, temp_a, widths[0])
    reg_b = reg_width(clk, rst, data_in, temp_b, widths[0])
    comp = compare(temp_a, temp_b, eq)
        
    return instances()
    
def multi_reg1(clk, rst, data_in, eq, widths=[8]):
    """
    Test single component - multiple instances, 
    without constant
    """
    temp_a = Signal(intbv(0)[widths[0]:])
    temp_b = Signal(intbv(0)[widths[0]:])
    
    reg_a = reg_noparam(clk, rst, data_in, temp_a)
    reg_b = reg_noparam(clk, rst, data_in, temp_b)
    comp = compare(temp_a, temp_b, eq)
        
    return instances()
    
def multi_reg2(clk, rst, data_in, eq, widths=[8, 4]):
    """
    Test multiple component - multiple instances, 
    with constant included
    """
    temp_a = Signal(intbv(0)[widths[0]:])
    temp_b = Signal(intbv(0)[widths[1]:])
    
    reg_a = reg_width(clk, rst, data_in, temp_a, widths[0])
    reg_b = reg_width(clk, rst, data_in, temp_b, widths[1])
    comp = compare(temp_a, temp_b, eq)
        
    return instances()
    
def multi_reg3(clk, rst, data_in, eq, widths=[8, 4]):
    """
    Test multiple component - multiple instances, 
    without constant
    """
    temp_a = Signal(intbv(0)[widths[0]:])
    temp_b = Signal(intbv(0)[widths[1]:])
    
    reg_a = reg_noparam(clk, rst, data_in, temp_a)
    reg_b = reg_noparam(clk, rst, data_in, temp_b)
    comp = compare(temp_a, temp_b, eq)
    
    return instances()
    
def multi_reg4(clk, rst, data_in, eq, widths=[8, 4]):
    """
    Test multiple component - multiple instances, variable,
    with constant included
    """
    temps = [Signal(intbv(0)[x:]) for x in widths]
    eq_mid_l = [Signal(False) for x in range(len(widths)-1)]
    eq_mid = ConcatSignal(*eq_mid_l)
    
    regs = [reg_width(clk, rst, data_in, temps[x], widths[x]) for x in range(len(widths))]
    
    compare_list = []    
    for i in range(len(widths) - 1):
        compare_list.append(compare(temps[0], temps[i+1], eq_mid_l[i]))
        
    @always_comb
    def eq_proc():
        eq.next = (eq_mid != 0)
        
    return instances()
    
# **** Testbench
def adder_bench(adder_func):
    NR_CYCLES = 10
      
    m = 8
    n = 2 ** m

    a, b, s = [Signal(intbv(0)[m:]) for x in range(3)]
    cin, cout = [Signal(bool(0)) for x in range(2)]

    adder_inst = adder_func(a, b, s, cin, cout, width=m)
    
    cin_values = tuple([random.randrange(2) for x in range(NR_CYCLES)])
    a_val, b_val = [tuple([random.randrange(n) for x in range(NR_CYCLES)]) for y in range(2)]

    @instance
    def stimulus():
        for i in range(NR_CYCLES):
            cin.next = cin_values[i]
            a.next = a_val[i]
            b.next = b_val[i]
            yield delay(10)
            print s
            print bool(cout)
            
    return adder_inst, stimulus
    
def multiple_comp_bench(multi_reg_func, widths):
    NR_CYCLES = 10
      
    m = max(widths)
    n = 2 ** m
    nmin = 2 ** min(widths)

    data = Signal(intbv(0)[m:])
    clk, rst, eq = [Signal(bool(0)) for x in range(3)]

    multi_inst = multi_reg_func(clk, rst, data, eq, widths)
    
    din_values = tuple(
                       [random.randrange(n) for x in range(NR_CYCLES/2)] + 
                       [random.randrange(nmin) for x in range(NR_CYCLES/2)])
    dtests_values = tuple(
                          [[int(intbv(din_values[y])[x:]) for x in widths] 
                                                     for y in range(NR_CYCLES)])
    calc_eq_values = tuple(
                           [int(all([din_values[y] == x 
                                     for x in dtests_values[y]])) 
                                     for y in range(NR_CYCLES)])
    
    @instance
    def clockgen():
        clk.next = 1
        while True:
            yield delay(10)
            clk.next = not clk

    @instance
    def stimulus():
        rst.next = 0
        data.next = 0
        yield clk.negedge
        rst.next = 1
        yield clk.negedge
        for i in range(NR_CYCLES):
            data.next = din_values[i]
            calc_eq = calc_eq_values[i]
            yield clk.negedge
            assert eq == calc_eq
            print eq
        raise StopSimulation

    return multi_inst, stimulus, clockgen
    
# utilities
def get_fileinfo():
    """
    Get modification time from all generated files
    """
    files = glob.glob("*.vhd") + glob.glob("*.v")
    modtimes = [os.stat(x).st_mtime for x in files]
    return dict(zip(files, modtimes))

def updated_files(fileinfo, ignore_vhdl_pck=True):
    """
    Get list of modified files
    """
    updated = []
    for file, mtime in fileinfo.items():
        if ignore_vhdl_pck:
            if file.startswith("pck_myhdl"):
                continue
        if os.stat(file).st_mtime > mtime:
            updated.append(file)
    for newfile, mtime in get_fileinfo().items():
        if ignore_vhdl_pck:
            if newfile.startswith("pck_myhdl"):
                continue
        if newfile not in fileinfo:
            updated.append(newfile)
    return updated
    
def file_check(updated, test):
    """
    Test existence of string test in updated list, file extension removed.
    """
    if hdlMap[verify.simulator] == "Verilog":
        strip_ext = ".v"
    elif hdlMap[verify.simulator] == "VHDL":
        strip_ext = ".vhd"
    else:
        raise ValueError("Invalid hdl %s" % verify.simulator)
    updated_strip = [x.replace(strip_ext, "") for x in updated]
    return (test in updated_strip)

# test instances:
# NOTE: all test run verify/analyze and then check generated files.

# 1. check standard conversion 
def test_adder_functional():
    f = get_fileinfo()
    assert verify(adder_bench, functional_adder) == 0
    if not kh_enabled:
        return
    u = updated_files(f)
    assert len(u) == 2
    for m in ("adder_bench", "functional_adder"):
        assert file_check(u, m)
    
def test_adder_structural():  
    f = get_fileinfo()
    assert verify(adder_bench, structural_adder) == 0
    if not kh_enabled:
        return
    u = updated_files(f)
    assert len(u) == 3
    for m in ("adder_bench", "structural_adder", "onebit_full_adder"):
        assert file_check(u, m)
    
# 2. check disable kh
def test_disable_kh():  
    if not kh_enabled:
        return
    f = get_fileinfo()
    kh_convertor.maxdepth = 0
    assert verify(adder_bench, structural_adder) == 0
    # one file: adder_bench
    u = updated_files(f)
    assert len(u) == 1
    assert file_check(u, "adder_bench")
    
# 3. check depth level
def test_depth():  
    if not kh_enabled:
        return
    file_data = [("adder_bench", ), 
                 ("adder_bench", "structural_adder"), 
                 ("adder_bench", "structural_adder", "onebit_full_adder"), 
                 ("adder_bench", "structural_adder", "onebit_full_adder")]
    for i in range(4):
        f = get_fileinfo()
        kh_convertor.maxdepth = i
        assert verify(adder_bench, structural_adder) == 0
        u = updated_files(f)
        assert len(u) == len(file_data[i])
        for m in file_data[i]:
            assert file_check(u, m)

# 4. disable component build
def test_disable_components():
    if not kh_enabled:
        return
    f = get_fileinfo()
    kh_convertor.no_component_files = True
    # analyze only: missing components required for simulation
    assert analyze(adder_bench, structural_adder) == 0
    u = updated_files(f)
    assert len(u) == 1
    assert not file_check(u, "structural_adder")
    assert file_check(u, "adder_bench")
    
# 5. multiple components
t_widths = [4, 8, 12, 12, 16, 16]
def test_multiple_components_sc_mi_ci():
    f = get_fileinfo()
    assert verify(multiple_comp_bench, multi_reg0, t_widths[:1]) == 0
    if not kh_enabled:
        return
    u = updated_files(f)
    assert len(u) == 4
    for m in ("multiple_comp_bench", "multi_reg0", "reg_width", "compare"):
        assert file_check(u, m)
    
def test_multiple_components_sc_mi_nc():
    f = get_fileinfo()
    assert verify(multiple_comp_bench, multi_reg1, t_widths[:1]) == 0
    if not kh_enabled:
        return
    u = updated_files(f)
    assert len(u) == 4
    for m in ("multiple_comp_bench", "multi_reg1", "reg_noparam", "compare"):
        assert file_check(u, m)
    
def test_multiple_components_mc_mi_ci():
    f = get_fileinfo()
    assert verify(multiple_comp_bench, multi_reg2, t_widths[:2]) == 0
    if not kh_enabled:
        return
    u = updated_files(f)
    assert len(u) == 5
    for m in ("multiple_comp_bench", "multi_reg2", "reg_width_0", "reg_width_1", "compare"):
        assert file_check(u, m)
    
def test_multiple_components_mc_mi_nc():
    f = get_fileinfo()
    assert verify(multiple_comp_bench, multi_reg3, t_widths[:2]) == 0
    if not kh_enabled:
        return
    u = updated_files(f)
    assert len(u) == 5
    for m in ("multiple_comp_bench", "multi_reg3", "reg_noparam_0", "reg_noparam_1", "compare"):
        assert file_check(u, m)
    
def test_multiple_components_v():
    f = get_fileinfo()
    assert verify(multiple_comp_bench, multi_reg4, t_widths) == 0
    if not kh_enabled:
        return
    u = updated_files(f)
    f_check = ["multiple_comp_bench", "multi_reg4", "reg_width_0", 
               "reg_width_1", "reg_width_2", "reg_width_3", "compare_0", 
               "compare_1", "compare_2"]
    assert len(u) == len(f_check)
    for m in f_check:
        assert file_check(u, m)
