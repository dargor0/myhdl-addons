#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# _mod_hierarchy.py: _HierExtr subclass
#
# Author:  Oscar Diaz <oscar.dc0@gmail.com>
#
# Based on myhdl/_extractHierarchy.py
# Original Author: Jan Decaluwe
# Copyright (C) 2003-2008 Jan Decaluwe
#
# This code is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
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

from inspect import getargspec

from myhdl._misc import _isGenSeq
from myhdl._Signal import _Signal, _isListOfSigs

from myhdl._extractHierarchy import _userCodeMap, _inferArgs, _makeMemInfo, _addUserCode
from myhdl._extractHierarchy import _HierExtr as _original_HierExtr

""" 
_HierExtr subclass: added support for extra information on hierarchy extraction
Includes
* _Instance 
* _HierExtr
"""

class _Instance(object):
    __slots__ = ['level', 'obj', 'subs', 'sigdict', 'memdict', 'name', 'func', 'argdict']
    def __init__(self, level, obj, subs, sigdict, memdict, func, argdict):
        # add two more members to _Instance object:
        # * func: reference to called function
        # * argdict : all other arguments and values not in sigdict or memdict
        self.level = level
        self.obj = obj
        self.subs = subs
        self.sigdict = sigdict
        self.memdict = memdict
        self.func = func
        self.argdict = argdict


class _HierExtr(_original_HierExtr):
    # modified to add information through _Instance objects
    def extractor(self, frame, event, arg):
        if event == "call":
            funcname = frame.f_code.co_name
            # skip certain functions
            if funcname in self.skipNames:
                self.skip +=1
            if not self.skip:
                self.level += 1
        elif event == "return":
            funcname = frame.f_code.co_name
            func = frame.f_globals.get(funcname)            
            if func is None:
                # Didn't find a func in the global space, try the local "self"
                # argument and see if it has a method called *funcname*
                obj = frame.f_locals.get('self')
                if hasattr(obj, funcname):
                    func = getattr(obj, funcname)                
            if not self.skip:
                isGenSeq = _isGenSeq(arg)
                if isGenSeq:
                    specs = {}
                    for hdl in _userCodeMap:
                        spec = "__%s__" % hdl
                        if spec in frame.f_locals and frame.f_locals[spec]:
                            specs[spec] = frame.f_locals[spec]
                        spec = "%s_code" % hdl
                        if func and hasattr(func, spec) and getattr(func, spec):
                            specs[spec] = getattr(func, spec)
                        spec = "%s_instance" % hdl
                        if func and hasattr(func, spec) and getattr(func, spec):
                            specs[spec] = getattr(func, spec)
                    if specs: 
                        _addUserCode(specs, arg, funcname, func, frame)
                # building hierarchy only makes sense if there are generators
                if isGenSeq and arg:
                    sigdict = {}
                    memdict = {}
                    # **** KH added code
                    argdict = {} 
                    if func:
                        arglist = getargspec(func).args 
                    else:
                        arglist = []
                    # ----
                    cellvars = frame.f_code.co_cellvars
                    for dict in (frame.f_globals, frame.f_locals):
                        for n, v in dict.items():
                            # extract signals and memories
                            # also keep track of whether they are used in generators
                            # only include objects that are used in generators
##                             if not n in cellvars:
##                                 continue
                            if isinstance(v, _Signal):
                                sigdict[n] = v
                                if n in cellvars:
                                    v._markUsed()
                            if _isListOfSigs(v):
                                m = _makeMemInfo(v)
                                memdict[n] = m
                                if n in cellvars:
                                    m._used = True
                            # **** KH added code: save any other variable in argdict
                            if (n in arglist) and (n not in sigdict) and (n not in memdict):
                                argdict[n] = v
                            # -----
                    subs = []
                    for n, sub in frame.f_locals.items():
                        for elt in _inferArgs(arg):
                            if elt is sub:
                                subs.append((n, sub))
                    # **** KH modified code: add "func" and "argdict"
                    inst = _Instance(self.level, arg, subs, sigdict, memdict, func, argdict)
                    # -----
                    self.hierarchy.append(inst)
                self.level -= 1
            if funcname in self.skipNames:
                self.skip -= 1
