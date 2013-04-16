#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# VHDL co-simulation helper
#
# Author:  Oscar Diaz <oscar.dc0@gmail.com>
# Version: 0.1
# Date:    03-03-2013
#
#
# This code is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This code is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this package; if not, see 
# <http://www.gnu.org/licenses/>.
#

import os
import StringIO
from datetime import datetime
import vhdl_lib

#from myhdl import *
#from open_interceptor import open_interceptor

#def tb_stub():
#    @instance
#    def empty():
#        yield delay(1)
#    return empty
  
def gen_cosim_testbench(source, generics_values={}):
    """
    Generate a VHDL testbench for use in GHDL co-simulation
    * source: base design (str, file, path or StringIO)
    * generics_values: dict with optional generic values
    """
    if type(source) == str:
        if os.path.exists(source):
            filename = source
            with open(source) as f:
                filecontent = StringIO.StringIO(f.read())
        else:
            # assume string content
            filecontent = StringIO.StringIO(source)
    elif type(source) == file:
        filename = source.name
        t = source.tell()
        source.seek(0)
        filecontent = StringIO.StringIO(source.read())
        source.seek(t)
    elif isinstance(source, StringIO.StringIO):
        filecontent = source
    else:
        raise ValueError("Unable to get any VHDL source with %s" % repr(source))
    
    vp = vhdl_parser.vhdl_parser(filecontent)
    vp.parse()
    dut_name = vp.model.get_entity_name()
    tb_name = "%s_tb" % dut_name
    for g, v in generics_values.items():
        vp.model.set_generic_value(g, v)
        
    vcg = vhdl_parser.vhdl_codegen(vp.model)
    
    ghdl_constdata = {"to_width": 0, "from_width": 0, "to_info": "", "from_info": ""}
    signal_decl = []
    signal_mapping = []
    port_map = []
    generic_map = []
    to_idx = 0
    from_idx = 0
    for sname, sdata in vp.model.get_ports_iter():
        sdet = vp.model.type_details(sname)
        slen = sdet["bitlen"]
        signal_decl.append("signal %s : %s;" % (sname, sdet["solveddef"]))
        port_map.append("%s => %s" % (sname, sname))
        if sdata["dir"] == "out":
            ghdl_constdata["to_info"] += "%s %d " % (sname, slen)
            ghdl_constdata["to_width"] += slen
            if slen == 1:
                sidx = str(to_idx)
                if sdet["base"] != "std_logic":
                    conv_sname = vcg.type_conversion(sdet["base"], "std_logic") % sname
                else:
                    conv_sname = sname
            else:
                sidx = "%d downto %d" % ((slen+to_idx-1), to_idx)
                if sdet["base"] != "std_logic_vector":
                    conv_sname = vcg.type_conversion(sdet["base"], "std_logic_vector") % sname
                else:
                    conv_sname = sname
            signal_mapping.append("to_vec(%s) <= %s;" % (sidx, conv_sname))
            to_idx += slen
        elif sdata["dir"] == "in":
            ghdl_constdata["from_info"] += "%s %d " % (sname, slen)
            ghdl_constdata["from_width"] += slen
            if slen == 1:
                sidx = "from_vec(%d)" % from_idx
                if sdet["base"] != "std_logic":
                    conv_sname = vcg.type_conversion("std_logic", sdet["base"]) % sidx
                else:
                    conv_sname = sidx
            else:
                sidx = "from_vec(%d downto %d)" % ((slen+from_idx-1), from_idx)
                if sdet["base"] != "std_logic_vector":
                    conv_sname = vcg.type_conversion("std_logic_vector", sdet["base"]) % sidx
                else:
                    conv_sname = sidx
            signal_mapping.append("%s <= %s;" % (sname, conv_sname))
            from_idx += slen
        else:
            raise ValueError("Unsupported direction '%s' for signal '%s'" % (sdata["dir"], sname))
            
    for gname, gdata in vp.model.get_generics_iter():
        generic_map.append("%s => %s" % (gname, vp.model.get_constant_value(gname)))
    
    dut_decl = "\n".join(signal_decl)
    dut_decl += "\n" + vcg.generate_component()
    decl_dict = dict(ghdl_constdata)
    decl_dict["dut_decl"] = dut_decl
    
    signal_map = "\n".join(signal_mapping)
    if len(generic_map) > 0:
        gm_str = "generic map (\n    %s\n)" % ",\n    ".join(generic_map)
    else:
        gm_str = ""
    if len(port_map) > 0:
        pm_str = "port map (\n    %s\n)" % ",\n    ".join(port_map)
    else:
        pm_str = ""
    dut_inst = "%s_dut : %s %s %s;\n" % (dut_name, dut_name, gm_str, pm_str)
    
    cosim_decl = _cosim_template_declaration % decl_dict
    cosim_code = _cosim_template_code % {"dut_inst": dut_inst, "signal_map": signal_map}
    
    # test with MyHDL generator
    #toVHDL.header = ''
    #toVHDL.no_myhdl_header = False
    #toVHDL.no_myhdl_package = True
    #toVHDL.library = "work"
    #toVHDL.architecture = "tb"
    #toVHDL.name = tb_name
    #toVHDL.component_declarations = cosim_decl
    #tb_stub.vhdl_code = cosim_code
    
    #i_files = open_interceptor(("vhd", "vhdl"))
    #with i_files.get_interceptor():
    #    toVHDL(tb_stub)
    #return i_files.replaced_files[".vhd" % tb_name].getvalue()
    
    # test with parser generator
    tb_model = vhdl_parser.vhdl_model(entity_name = tb_name)
    tb_model.add_std_library()
    tb_model.add_library("work.myhdl_ghdl_core")
    tb_model.set_architecture_name("tb")
    tb_model.add_architecture_body("%s\nbegin\n%s" % (cosim_decl, cosim_code))
    tb_model.add_header(_cosim_header % {"filename": "%s.vhdl" % tb_name, "date": datetime.today().ctime()})
    return vhdl_parser.vhdl_codegen(tb_model).generate_content()
        
_cosim_header = """-- File: %(filename)s
-- Generated by "cosim_helper"
-- Date: %(date)s
"""        

_cosim_template_declaration = """
constant to_width : integer := %(to_width)d;
constant from_width : integer := %(from_width)d;
constant timeres : time := 1 ns;
constant to_info : string := "%(to_info)s";
constant from_info : string := "%(from_info)s";
signal to_vec : std_logic_vector((to_width - 1) downto 0) := (others => '0');
signal from_vec : std_logic_vector((from_width - 1) downto 0) := (others => '0');
%(dut_decl)s
"""

_cosim_template_code = """
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

%(dut_inst)s
-- signal mapping
%(signal_map)s
"""
