#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# signal_monitor: custom class for signal tracing in MyHDL
#
# Author:  Oscar Diaz <oscar.dc0@gmail.com>
# Version: 0.1
# Date:    02-11-2011
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

import myhdl
import os.path
import time
from collections import OrderedDict
from math import log

"""
signal_monitor: custom class for signal tracing in MyHDL

Usage example:

tracer = signal_monitor()

# reset and clock: Signal(bool)
tracer.add_trace_signal(reset, "Master_reset")
tracer.add_trace_signal(clock, "Master_clock")
# can use "add_trace_signal" with individual signals, lists and dicts that 
# contains Signal objects, or objects with Signal attributes.

...

trace_generator = tracer.traceConfig(sim_max_time, "vcd_filename")

...

# assuming "my_generators" is a list with myhdl generators

my_generators.extend(trace_generator)
sim = myhdl.Simulation(my_generators)
sim.run(sim_max_time)
"""

class signal_monitor():
    def __init__(self):
        self.signal_objects = OrderedDict()
        self.trace_objects = []
        self.unnamed_counter = 0
        self.traceGenerator = None
        self.vcdpath = ""
        self.scope_top = []
        self.scope_tree = {}
        self.traceinfo = {}
        self.sim_max_time = 0
        
    def add_trace_signal(self, signal, name="", scopename=""):
        if isinstance(signal, myhdl.SignalType):
            retname = self._add_myhdl_trace_signal(signal, name)
            if scopename == "":
                # top scope
                self.scope_top.append(retname)
            else:
                if scopename in self.scope_tree:
                    self.scope_tree[scopename].append(retname)
                else:
                    self.scope_tree[scopename] = [retname]
        elif isinstance(signal, (list, tuple)):
            listnames = []
            if isinstance(name, (list, tuple)):
                for i, s in enumerate(signal):
                    retname = self._add_myhdl_trace_signal(s, name[i])
                    listnames.append(retname)
            elif isinstance(name, str):
                # name as basename
                if scopename != "":
                    addname = scopename + "_"
                for i, s in enumerate(signal):
                    retname = self._add_myhdl_trace_signal(s, "%s%s%d" % (addname, name, i))
                    listnames.append(retname)
            else:
                for s in signal:
                    retname = self._add_myhdl_trace_signal(s, "")
                    listnames.append(retname)
            if scopename == "":
                # top scope
                self.scope_top.extend(listnames)
            else:
                if scopename in self.scope_tree:
                    self.scope_tree[scopename].extend(listnames)
                else:
                    self.scope_tree[scopename] = listnames
        elif isinstance(signal, dict):
            # dict name
            listnames = []
            for k, v in signal.iteritems():
                retname = self._add_myhdl_trace_signal(v, "%s_%s" % (name, k), True)
                if retname is not None:
                    listnames.append(retname)
            if scopename == "":
                # use name as scope
                self.scope_tree[name] = listnames
            else:
                if scopename in self.scope_tree:
                    self.scope_tree[scopename].extend(listnames)
                else:
                    self.scope_tree[scopename] = listnames
        else:
            # assume object with myhdl signals as members
            if name != "":
                thename = name
            else:
                thename = signal.__name__
            members = dir(signal)
            listnames = []
            for testmember in members:
                trysignal = getattr(signal, testmember)
                if isinstance(trysignal, myhdl.SignalType):
                    retname = self._add_myhdl_trace_signal(trysignal, "%s_%s" % (thename, testmember))
                    listnames.append(retname)
            if len(listnames) == 0:
                raise ValueError("Object '%s' (%s) doesn't have MyHDL Signal members." % (signal.__name__, repr(signal)))
            if scopename == "":
                self.scope_tree[thename] = listnames
            else:
                if scopename in self.scope_tree:
                    self.scope_tree[scopename].extend(listnames)
                else:
                    self.scope_tree[scopename] = listnames
        self.trace_objects.append(signal)
        
    def build_trace_generator(self):
        # need to build a mirror signal list, in order to trace the signals correctly
        # TODO: is really necessary a mirror signal? assert this.
        
        mirror_signals = {}
        for key, signalref in self.signal_objects.iteritems():
            mirror_signals[key] = myhdl.Signal(signalref.val)
            
        def mirror_proc_gen(base, mirror):
            @myhdl.always_comb
            def mirror_proc():
                mirror.next = base
                
            return mirror_proc
            
        procs = []
        for key, sig in mirror_signals.iteritems():
            procs.append(mirror_proc_gen(self.signal_objects[key], sig))
                
        return procs
        
    def vcd_generator(self):
        header = self._vcd_header()
        signals = self._vcd_signal_header()
        vcdclose = self._vcd_section("vcdclose", "#%d" % self.sim_max_time)
        if self.vcdpath == os.path.splitext(self.vcdpath)[0]:
            self.vcdpath += ".vcd"
        
        def sig_proc_gen(sigref, signame):
            @myhdl.always(sigref)
            def sig_proc():
                curtime = myhdl.now()
                traceval = "%s%s" % (self._vcd_printval(sigref), self._vcd_references[signame])
                if curtime not in self.traceinfo:
                    self.traceinfo[curtime] = []
                self.traceinfo[curtime].append(traceval)
                
            return sig_proc
            
        @myhdl.instance
        def file_driver():
            yield myhdl.delay(self.sim_max_time - 1)
            vcdfile = open(self.vcdpath, 'w')
            vcdfile.write(header)
            vcdfile.write(signals)
            timevals = self.traceinfo.keys()
            timevals.sort()
            for t in timevals:
                vcdfile.write("#%d\n" % t)
                for v in self.traceinfo[t]:
                    vcdfile.write(v+"\n")
            vcdfile.write(vcdclose)
            vcdfile.close()
            return
                    
        generator_list = [file_driver]
        for signame, sigref in self.signal_objects.iteritems():
            generator_list.append(sig_proc_gen(sigref, signame))
            
        return generator_list
        
    def traceConfig(self, sim_max_time, basename=""):
        if basename == "":
            self.vcdpath = "custom_tracer"
        else:
            self.vcdpath = basename
        self.sim_max_time = sim_max_time
        self.traceGenerator = self.vcd_generator()
        return self.traceGenerator

    def _add_myhdl_trace_signal(self, signal, name, ignExcp=False):
        # direct reference, need a correct name
        if name == "":
            name = "Unnamed_%d" % self.unnamed_counter
            self.unnamed_counter += 1
        if name in self.signal_objects:
            raise ValueError("Signal '%s' (%s) already traced." % (name, repr(signal)))
        else:
            if not isinstance(signal, myhdl.SignalType):
                if ignExcp:
                    return
                raise ValueError("Object '%s' not a MyHDL signal." % repr(signal))
            self.signal_objects[name] = signal
        return name
            
    def _vcd_section(self, name, content, cr=False, tab=False):
        if cr:
            if tab:
                return "$%s\n    %s\n$end\n" % (name, content)
            else:
                return "$%s\n%s\n$end\n" % (name, content)
        else:
            return "$%s %s $end\n" % (name, content)
            
    def _vcd_header(self):
        retval = self._vcd_section("date", time.asctime(), True, True)
        retval += self._vcd_section("version", "NoCmodel 0.1 (TEMP)", True, True)
        retval += self._vcd_section("timescale", "1ns", True, True)
        return retval+"\n"
        
    def _vcd_signal_header(self, basename="signal_monitor"):
        self._vcd_references = OrderedDict()
        #index_counter = 33 # ascii '!'
        index_counter = 0
        # main scope
        retval = self._vcd_section("scope", "module %s" % basename)
        # top scope
        for s in self.scope_top:
            width = self.signal_objects[s]._nrbits
            ref = self._vcd_genref(index_counter)
            if width == 0:
                # take as integer (def 64 bits)
                retval += self._vcd_section("var", "integer 64 %s %s" % (ref, s))
            else:
                # reg
                retval += self._vcd_section("var", "reg %d %s %s" % (width, ref, s))
            self._vcd_references[s] = ref
            index_counter += 1
        # sub scopes
        for k, v in self.scope_tree.iteritems():
            retval += self._vcd_section("scope", "module %s" % k)
            for s in v:
                width = self.signal_objects[s]._nrbits
                ref = self._vcd_genref(index_counter)
                if width == 0:
                    # take as integer (def 64 bits)
                    retval += self._vcd_section("var", "integer 64 %s %s" % (ref, s))
                else:
                    # reg
                    retval += self._vcd_section("var", "reg %d %s %s" % (width, ref, s))
                self._vcd_references[s] = ref
                index_counter += 1
            retval += self._vcd_section("upscope", "")
        
        retval += self._vcd_section("upscope", "")
        # end signal header
        retval += self._vcd_section("enddefinitions", "")
        #print "SIGNAL HEADER: index counter = %d (%d)" % (index_counter, index_counter - 33)
        # initial values
        ival = ""
        for sig, ref in self._vcd_references.iteritems():
            ival += "%s%s\n" % (self._vcd_printval(self.signal_objects[sig]), ref)
        retval += self._vcd_section("dumpvars", ival[:-1], True)
        return retval
        
    def _vcd_genref(self, countval):
        if not hasattr(self, "_vcd_signal_count"):
            setattr(self, "_vcd_signal_count", len(self.signal_objects))
            setattr(self, "_vcd_ref_numchr", int(log(self._vcd_signal_count, 94)) + 1)
            setattr(self, "_vcd_ref_range", range(self._vcd_ref_numchr))
        retval = ""
        tempval = countval
        # TODO: check this algorithm!!!
        for i in self._vcd_ref_range:
            if i == len(self._vcd_ref_range) - 1:
                retval += chr((countval % 94)+33) 
            else:
                retval += chr((tempval / 94)+33) 
                tempval -= 94
        return retval
        
    def _vcd_printval(self, value):
        if isinstance(value, myhdl.SignalType):
            thevalue = value.val
            if value._nrbits == 1:
                return str(int(thevalue))
        else:
            thevalue = value
        if isinstance(thevalue, myhdl.intbv):
            if thevalue._nrbits == 1:
                return str(int(thevalue))
            else:
                return "b%s " % myhdl.bin(thevalue)
        elif isinstance(thevalue, bool):
            return str(int(thevalue))
        elif isinstance(thevalue, (int, long)):
            return "b%s " % myhdl.bin(thevalue)
        elif isinstance(thevalue, float):
            return "r%.16g " % thevalue
        elif isinstance(thevalue, str):
            return "s%s " % thevalue
        else:
            # use repr as fallback
            return "s%s " % repr(thevalue)

    