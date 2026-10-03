#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Tests for unused / unconnected signals

import os
import glob
import random
random.seed(2)

from myhdl import *
from myhdl.conversion import verify

# reuse some stuff from test_structural
from test_structural import kh_convertor, kh_enabled, get_fileinfo, updated_files, file_check

NR_CYCLES = 10
M_DEFAULT = 8

# test components
def and_operator1(a, b, x, s_unused):
    """
    bitwise AND operator, plus top-module unused signal
    """
    @always_comb
    def logic():
        x.next = a & b
    return logic
    
def and_operator2(a, b, x):
    """
    bitwise AND operator, plus internal unused signal
    """
    s_unused = Signal(True)
    @always_comb
    def logic():
        x.next = a & b
    return logic
    
def and_operator3(a, b, c, x):
    """
    bitwise AND operator, 3 inputs
    """
    midres = Signal(intbv(0, min=a.min, max=a.max))
    @always_comb
    def logic_a():
        midres.next = a & b
    @always_comb
    def logic_b():
        x.next = midres & c
    return logic_a, logic_b
    
def and_operator4(a, b, x, y):
    """
    bitwise AND operator, OR operator
    """
    @always_comb
    def logic():
        x.next = a & b
        y.next = a | b
    return logic
    
# **** Testbench
def unused1_bench(m):
    """
    Unused "u"
    """
    n = 2**m
    
    a, b, s, u = [Signal(intbv(0)[m:]) for x in range(4)]
    
    dut_inst = and_operator1(a, b, s, u)
    
    a_val, b_val = [tuple([random.randrange(n) for x in range(NR_CYCLES)]) for y in range(2)]
    s_val = tuple([a_val[x] & b_val[x] for x in range(NR_CYCLES)])

    @instance
    def stimulus():
        for i in range(NR_CYCLES):
            a.next = a_val[i]
            b.next = b_val[i]
            s_calc = s_val[i]
            yield delay(10)
            assert s == s_calc
            print s
            
    return dut_inst, stimulus
    
def unused2_bench(m):
    """
    Unused inside component
    """
    n = 2**m
    
    a, b, s = [Signal(intbv(0)[m:]) for x in range(3)]
    
    dut_inst = and_operator2(a, b, s)
    
    a_val, b_val = [tuple([random.randrange(n) for x in range(NR_CYCLES)]) for y in range(2)]
    s_val = tuple([a_val[x] & b_val[x] for x in range(NR_CYCLES)])

    @instance
    def stimulus():
        for i in range(NR_CYCLES):
            a.next = a_val[i]
            b.next = b_val[i]
            s_calc = s_val[i]
            yield delay(10)
            assert s == s_calc
            print s
            
    return dut_inst, stimulus
    
def unused3_bench(m, default_value):
    """
    Undriven signal with default value
    """
    n = 2**m
    
    a, b, s = [Signal(intbv(0)[m:]) for x in range(3)]
    c = Signal(intbv(default_value)[m:])
    
    dut_inst = and_operator3(a, b, c, s)
    
    a_val, b_val = [tuple([random.randrange(n) for x in range(NR_CYCLES)]) for y in range(2)]
    s_val = tuple([a_val[x] & b_val[x] & default_value for x in range(NR_CYCLES)])

    @instance
    def stimulus():
        for i in range(NR_CYCLES):
            a.next = a_val[i]
            b.next = b_val[i]
            s_calc = s_val[i]
            yield delay(10)
            assert s == s_calc
            print s
            
    return dut_inst, stimulus
    
def unused4_bench(m):
    """
    Ignore one output
    """
    n = 2**m
    
    a, b, s = [Signal(intbv(0)[m:]) for x in range(3)]
    c = Signal(intbv(0)[m:])
    
    dut_inst = and_operator4(a, b, s, c)
    
    a_val, b_val = [tuple([random.randrange(n) for x in range(NR_CYCLES)]) for y in range(2)]
    s_val = tuple([a_val[x] & b_val[x] for x in range(NR_CYCLES)])

    @instance
    def stimulus():
        for i in range(NR_CYCLES):
            a.next = a_val[i]
            b.next = b_val[i]
            s_calc = s_val[i]
            yield delay(10)
            assert s == s_calc
            print s
            
    return dut_inst, stimulus
    
# test instances:
# NOTE: all test run verify and then check generated files.

def test_unused1():
    f = get_fileinfo()
    assert verify(unused1_bench, M_DEFAULT) == 0
    if not kh_enabled:
        return
    u = updated_files(f)
    assert len(u) == 2
    for m in ("unused1_bench", "and_operator1"):
        assert file_check(u, m)

def test_unused2():
    f = get_fileinfo()
    assert verify(unused2_bench, M_DEFAULT) == 0
    if not kh_enabled:
        return
    u = updated_files(f)
    assert len(u) == 2
    for m in ("unused2_bench", "and_operator2"):
        assert file_check(u, m)

def test_unused3a():
    f = get_fileinfo()
    assert verify(unused3_bench, M_DEFAULT, 0) == 0
    if not kh_enabled:
        return
    u = updated_files(f)
    assert len(u) == 2
    for m in ("unused3_bench", "and_operator3"):
        assert file_check(u, m)
        
def test_unused3b():
    f = get_fileinfo()
    defval = random.randrange(2**M_DEFAULT)
    assert verify(unused3_bench, M_DEFAULT, defval) == 0
    if not kh_enabled:
        return
    u = updated_files(f)
    assert len(u) == 2
    for m in ("unused3_bench", "and_operator3"):
        assert file_check(u, m)
        
def test_unused4():
    f = get_fileinfo()
    assert verify(unused4_bench, M_DEFAULT) == 0
    if not kh_enabled:
        return
    u = updated_files(f)
    assert len(u) == 2
    for m in ("unused4_bench", "and_operator4"):
        assert file_check(u, m)
