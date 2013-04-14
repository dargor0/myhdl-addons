#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# to_vhdl_kh: vhdl convertor that Keeps Hierarchy
#
# Author:  Oscar Diaz <oscar.dc0@gmail.com>
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

import re
import os
import inspect
import warnings
from myhdl import ToVHDLError, ToVHDLWarning, intbv

import myhdl
from myhdl import *
from myhdl.conversion._misc import _genUniqueSuffix
from myhdl.conversion._analyze import (_analyzeSigs, _analyzeGens, _analyzeTopFunc,
                                       _enumTypeSet)

# current MyHDL 0.8 import
#from myhdl.conversion._toVHDL import (toVHDL, _ToVHDLConvertor, constwires, 
#                                      _converting, _checkArgs, _flatten, _makeDoc,
#                                      _annotateTypes, _writeFileHeader, 
#                                      _writeCustomPackage, _writeModuleHeader, 
#                                      _writeFuncDecls, _writeCompDecls, 
#                                      _writeModuleFooter, _version, 
#                                      _enumPortTypeSet, _writeConstants, 
#                                      _writeTypeDefs, _shortversion)
                                      
from myhdl.conversion._toVHDL import (toVHDL, _ToVHDLConvertor, constwires, 
                                      _converting, _checkArgs, _flatten, _makeDoc,
                                      _annotateTypes, _writeFileHeader, 
                                      _writeCustomPackage, _writeModuleHeader, 
                                      _writeFuncDecls, _writeCompDecls, 
                                      _writeModuleFooter)
                                      
# Version Hack: MyHDL 0.7 doesn't define some objects
try:
    from myhdl.conversion._analyze import _constDict
except:
    _constDict = {}
try:
    from myhdl.conversion._toVHDL import _shortversion
except:
    from myhdl.conversion._toVHDL import _version
try:
    from myhdl.conversion._toVHDL import _enumPortTypeSet
except:
    pass
try:
    from myhdl.conversion._toVHDL import _writeConstants
except:
    pass
try:
    from myhdl.conversion._toVHDL import _writeTypeDefs
except:
    pass
# ****
                                      
from myhdl.conversion._toVHDLPackage import _package
from myhdl._extractHierarchy import (_memInfoMap, _UserCode)

from _mod_hierarchy import _HierExtr
from myhdl._Signal import _Signal

from myhdl.conversion._toVHDL import _writeSigDecls as _original_writeSigDecls
from myhdl.conversion._toVHDL import _convertGens as _original_convertGens

from open_interceptor import open_interceptor, current_interceptor

import sys

# main object
class _ToVHDL_kh_Convertor(_ToVHDLConvertor):
    __slots__ = ("maxdepth", 
                 "no_component_files"
                 )

    def __init__(self):
        _ToVHDLConvertor.__init__(self)
        
        # additional arguments
        self.no_component_files = False
        # Whether to save code from components to files
        # True to try to store code in open_interceptor object
        self.maxdepth = None
        # set recursion depth. use None to unlimited recursion, 
        # 0 will fall back to standard convertor
        # 1 only convert one layer
        
    def __call__(self, func, *args, **kwargs):
        # allows monkey patching
        pass

    # KH Code: added method
    def _convert_filter(self, h, intf, siglist, memlist, genlist):
        # intended to be a entry point for other uses: 
        #  code checking, optimizations, etc
        pass
    
    # KH Code: added method
    def _kh_filter(self, h, intf, genlist):

        if self.maxdepth == 0:
            # disabled kh
            setattr(intf, "kh_discard_siglist", [])
            setattr(intf, "kh_discard_memlist", [])
            setattr(intf, "kh_comp_inst", [])
            setattr(intf, "kh_comp_decls", {})
            genlist.insert(0, intf)
            return
        
        # get list of components for instantiation
        comp_inst = {}
        direct_impl = {}
        missing_idx = range(1, len(h.hierarchy))
        for inst_name, inst in h.hierarchy[0].subs:
            found = False
            for idx, ih in enumerate(h.hierarchy):
                # only read level=2 entries
                if ih.level > 2:
                    continue
                if ih.name.startswith(inst_name):
                    comp_inst[ih.name] = ih
                    missing_idx.remove(idx)
                    found = True
            if not found:
                # instance don't have entry in hierarchy. Store as direct implementation
                direct_impl[inst_name] = inst
        for missing in missing_idx:
            # only read level=2 entries
            if h.hierarchy[missing].level <= 2:
                warnings.warn("Missing instance name for '%s' (level %d)" % 
                                (h.hierarchy[missing].name, 
                                 h.hierarchy[missing].level), 
                                 category=ToVHDLWarning)
                
        # avoid invalid names in port names
        for sname, sig in intf.argdict.items():
            if sname in _VHDL_Invalid_names:
                # change only key in dict and list member in argnames
                warnings.warn("Invalid VHDL name for signal %r. Changgenling to %r" % 
                              (sname, "myhdl_" + sname),category=ToVHDLWarning)
                intf.argdict["myhdl_" + sname] = intf.argdict.pop(sname)
                intf.argnames[intf.argnames.index(sname)] = "myhdl_" + sname
                
        # keep "genlist" with only direct generators
        del_genlist = []
        for tree in genlist:
            # TODO: user code not supported for hierarchical conversion (yet)
            if isinstance(tree, _UserCode):
                warnings.warn("User-defined code is not supported for keep-hierarchy mode.\n" 
                              "  Fallback to standard conversion.\n" 
                              '  In file "%s" line %d, in %s' % 
                              (tree.sourcefile, tree.sourceline, tree.funcname), 
                              category=ToVHDLWarning)
            else:
                for f in tree.body:
                    if f.name not in direct_impl.keys():
                        del_genlist.append(tree)
                    
        del_genlist.reverse()
        for d in del_genlist:
            genlist.remove(d)
            
        # infer internal signals: all signals but arguments
        internals = []
        for sname, sig in h.hierarchy[0].sigdict.iteritems():
            if sname not in intf.argnames:
                internals.append(sig._name)
        
        # all signals in memdict as internals
        for mi in h.hierarchy[0].memdict.itervalues():
            for sig in mi.mem:
                if sig._name not in intf.argnames:
                    # note: signal name could change here for improve context 
                    # in output code. (check if it's worth the change)
                    internals.append(sig._name)
                    
        # unnecesary signals from flat model
        discard_siglist = []
        discard_memlist = []
        for ih in h.hierarchy[1:]:
            for sig in ih.sigdict.itervalues():
                if (sig._name not in discard_siglist) and (sig._name not in internals) and (sig._name not in intf.argnames):
                    discard_siglist.append(sig._name)
            for mi in ih.memdict.itervalues():
                for sig in mi.mem:
                    if (sig._name not in discard_siglist) and (sig._name not in internals) and (sig._name not in intf.argnames):
                        discard_siglist.append(sig._name)
                        if mi.name not in discard_memlist:
                            discard_memlist.append(mi.name)
        
        comp_dict = {}
        for name, inst in comp_inst.items():
            # NOTE: for each instance check argument values when called
            # and generate a different component if the values are 
            # different between instances. That means each component will 
            # have "fixed" generics. This could change in the future, provided
            # the conversor support generics.
            
            # comp_dict has [func_name]: ([<inst_name>,...], <paramdict>), ...
            # paramdict holds data about how the instance was called
            paramdict = inst.argdict.copy()
            strargs = inspect.getargspec(inst.func).args
            # sigdict: get _val from signals
            for k, v in inst.sigdict.items():
                if k in strargs:
                    paramdict[k] = v._val
            
            if inst.func.func_name not in comp_dict:
                comp_dict[inst.func.func_name] = [([name], paramdict)]
            else:
                hit = False
                for cnames, carg in comp_dict[inst.func.func_name]:
                    # special comparison: see function def
                    if _param_compare(carg, paramdict):
                        cnames.append(name)
                        hit = True
                        break
                if not hit:
                    comp_dict[inst.func.func_name].append(([name], paramdict))
                    
        files = {}
        comp_decls = {}
        for func_name, instdata in comp_dict.iteritems():
            for cidx, cdata in enumerate(instdata):
                inst_name = cdata[0][0]
                inst = comp_inst[inst_name]
                argdict = cdata[1]
                
                # GHDL patch: entity names cannot start with "_" 
                # (TODO: probably other characters have the same problem)
                comp_name = func_name
                if func_name[0] == "_":
                    comp_name = "myhdl" + comp_name
                if len(instdata) > 1:
                    # multiple component for a single function
                    comp_name = "%s_%d" % (comp_name, cidx)
                
                # copy list of non-Signal arguments 
                func_args = {}
                strargs = inspect.getargspec(inst.func).args
                for k, v in inst.sigdict.items():
                    if k in strargs:
                        func_args[k] = _Signal(v._val)
                for k, v in argdict.items():
                    if (k not in func_args) and (k in strargs):
                        func_args[k] = v
                
                # check for 'self' in argdict
                if "self" in func_args:
                    warnings.warn("Detected 'self' argument: %s. Removed before recursive calling." 
                                  % repr(func_args["self"]), category=ToVHDLWarning)
                    del func_args["self"]
                
                if self.maxdepth == 1 :
                    # standard convertor
                    convertor = toVHDL
                else:
                    # recursive convertor: create a new one
                    convertor = _ToVHDL_kh_Convertor()
                    convertor.maxdepth = self.maxdepth
                    convertor.no_component_files = self.no_component_files
                    if self.maxdepth is not None:
                        convertor.maxdepth -= 1
                        
                # copy some attributes
                for attr in _ToVHDLConvertor.__slots__:
                    if attr not in ("name", "component_declarations", "no_myhdl_package"):
                        setattr(convertor, attr, getattr(self, attr))
                # Version Hack: MyHDL 0.7 doesn't define all attributes
                try:
                    convertor.no_myhdl_package = True
                except:
                    pass
                convertor.name = comp_name
                
                # NOTE: toVHDL is non-reentrant function
                # save some states prior to call
                state_memInfoMap = _memInfoMap.copy()
                state_genUniqueSuffix = _genUniqueSuffix.i
                state_enumTypeSet = _enumTypeSet.copy()
                state_constDict = _constDict.copy()
                
                # use open_interceptor to store results on StringIO's
                i_files = open_interceptor(("vhd", "vhdl"))
                with i_files.get_interceptor():
                    convertor(inst.func, **func_args)
                
                _genUniqueSuffix.i = state_genUniqueSuffix
                _enumTypeSet.update(state_enumTypeSet)
                _memInfoMap.clear()
                _memInfoMap.update(state_memInfoMap)
                _constDict.clear()
                _constDict.update(state_constDict)
                
                for fname, value in i_files.replaced_files.iteritems():
                    if fname in files:
                        warnings.warn("File %s already generated for component %s." % 
                                      (fname, comp_name), category=ToVHDLWarning)
                        continue
                    files[fname] = value
                    content = value.getvalue()
                    # extract comp_decls
                    if fname.startswith(comp_name + ".vhd"):
                        startidx = re.search(r"entity.*is", content, re.IGNORECASE).regs[0][0]
                        endidx = re.search(r"end entity.*;", content, re.IGNORECASE).regs[0][1]
                        # comp_decls is [<component_name>]: [<code>, <instance_name>...]
                        comp_decls[comp_name] = [re.sub("entity", "component", 
                                                        content[startidx:endidx], re.IGNORECASE)]
                        comp_decls[comp_name].extend(cdata[0])

        if len(files) > 0:
            if self.no_component_files:
                ic_ref = current_interceptor()
                if ic_ref:
                    ic_ref.replaced_files.update(files)
                else:
                    warnings.warn("No open-interceptor detected. Components %s will not be saved." % 
                                  repr(comp_decls.keys()), category=ToVHDLWarning)
            else:
                # save files to disk
                for fname, value in files.iteritems():
                    with open(fname, "w") as f:
                        f.write(value.getvalue())
                        
        # KH transformations done. Save additional data in intf object
        # this will be used on _writeSigDecls and _convertGens
        setattr(intf, "kh_discard_siglist", discard_siglist)
        setattr(intf, "kh_discard_memlist", discard_memlist)
        setattr(intf, "kh_comp_inst", comp_inst)
        setattr(intf, "kh_comp_decls", comp_decls)
        # _convertGens don't get intf as argument. Use genlist to pass
        # intf to _convertGens
        genlist.insert(0, intf)

toVHDL_kh = _ToVHDL_kh_Convertor()

def _monkey_convertor():
    """
    monkey patch
    
    This replaces original _ToVHDLConvertor.__call__ , adding two method calls
    (_convert_filter() and _kh_filter() ) 
    and two assignments (subclass added attributes)
    """
    patched_code = inspect.getsource(_ToVHDLConvertor.__call__)
    # patch required lines
    patch_data = {"intf.name = name": ["self._convert_filter(h, intf, siglist, memlist, genlist)",
                                       "self._kh_filter(h, intf, genlist)"], 
                  "self.name = None": ["self.maxdepth = None", 
                                       "self.no_component_files = False"]}
    for patch_line, insert_lines in patch_data.items():
        m = re.search("[ \t]*%s" % patch_line, patched_code)
        if m is None:
            raise StandardError("Entry point for monkey patching not found.")
        # get indentation level
        indent = m.group().replace(patch_line, "")
        insert_lines.insert(0, patch_line)
        patch_str = indent + (("\n" + indent).join(insert_lines))
        patched_code = patched_code.replace(m.group(), patch_str)
    # quit initial indent
    indent = re.search("\A[ \t]*", patched_code).group()
    patched_code = re.sub("\n"+indent, "\n", patched_code)
    patched_code = re.sub("\A"+indent, "", patched_code)
    # compilation
    patch_object = compile(patched_code, "<monkey>", "exec")
    patch_scope = {} 
    exec patch_object in patch_scope
    _ToVHDL_kh_Convertor.__call__.__func__.__code__ = patch_scope['__call__'].__code__
    #print "MONKEY: patch done! test it"
    
_monkey_convertor()

# override converter functions

def _writeSigDecls(f, intf, siglist, memlist):
    # component declaration
    for c in intf.kh_comp_decls.values():
        print >> f, c[0]
        print >> f
        
    # call original function with a modified siglist: remove discard signals
    for dname in intf.kh_discard_siglist:
        for i in range(len(siglist)):
            if siglist[i]._name == dname:
                del siglist[i]
                break
        
    _original_writeSigDecls(f, intf, siglist, memlist)
    
# Version hack: _convertGens changed from MyHDL 0.7 to add memlist, make vfile optional
def _convertGens(genlist, siglist, memlist, vfile=None):
    intf = genlist.pop(0)
    
    # call original function with a modified siglist: remove discard signals
    # (previously removed in _writeSigDecls)
    # Version hack: _convertGens changed from MyHDL 0.7 to add memlist
    if "memlist" in inspect.getargspec(_original_convertGens).args:
        _original_convertGens(genlist, siglist, memlist, vfile)
    else:
        vfile = memlist
        _original_convertGens(genlist, siglist, vfile)
    
    # instantiations
    for comp_name, comp_data in intf.kh_comp_decls.items():
        for inst_name in comp_data[1:]:
            inst = intf.kh_comp_inst[inst_name]
            print >> vfile, "\n%s : %s \nport map (" % (inst_name, comp_name)
            pmap = []
            strargs = inspect.getargspec(inst.func).args
            for sname, sig in inst.sigdict.items():
                if sname in strargs:
                    # fix invalid name if required
                    if sname in _VHDL_Invalid_names:
                        sname = "myhdl_" + sname
                    pmap.append("    %s => %s" % (sname, sig._name))
            print >> vfile, ",\n".join(pmap) + ");"
        
    print >> vfile, "\n"

# special comparison
def _param_compare(x, y):
    # assume x and y dicts
    # same keys
    if x.keys() != y.keys():
        return False
    # compare each value
    for k in x.keys():
        if x[k] != y[k]:
            return False
        # additional comparison: 
        # if values are intbv, compare its bitlenghts
        if isinstance(x[k], intbv) and isinstance(y[k], intbv):
            if len(x[k]) != len(y[k]):
                return False
        elif isinstance(x[k], intbv) or isinstance(y[k], intbv):
            # one of them is intbv but the other not.
            return False
    # otherwise, equals
    return True
    
# invalid names in VHDL
_VHDL_Invalid_names = ("in", "out", "entity", "architecture", "generic", "port", "map", "end")
