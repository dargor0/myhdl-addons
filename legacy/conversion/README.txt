Conversion while keeping hierarchy
==================================

Use
---

from toVHDL_kh import toVHDL_kh

toVHDL_kh(func[, *args][, **kwargs])

This converter is used exactly the same way as the original toVHDL(),
with two additional attributes:

    maxdepth : set the recursion depth.
        0: don't extract hierarchy. This is equivalent to toVHDL()
        1: only extract hierarchy from top module. 
           Sub-components will be converted with toVHDL()
        > 1: try to extract hierarchy as deep as maxdepth value.
        None: Unlimited recursion. Converter try to use component instantiation 
              as possible (Default)

    no_component_files : 
        False : all sub-components code is saved to disk
        True : try to use open_interceptor objects to keep sub-components code
               in memory (see Files in memory). If not, discard sub-components code.
               
Hierarchy conservation
----------------------

Converter works by finding function calls that returns generators, call recursively 
the converter with this functions, extract a "component" declaration from generated code
and then instantiate components based on that function. 

Generators defined along with function generators are converted the same way as the
standard converter does.

Call recursion is controlled with "maxdepth" attribute. 

Component generation is based not only in its function generators, but also on 
the arguments which the function was called. This means that, if a function is called
with different arguments, the converter will generate different sub-components related 
to each call. Converter checks each of the signal's base type and all non-signal 
arguments to decide how many components generate based on a single function call.
    
Files in memory
---------------

Along with the converter, utility open-interceptor allows to keep converter from
writing files to disk; instead it saves generated code in StringIO objects. 
It's used this way:

i_files = open_interceptor(("vhd",))
with i_files.get_interceptor():
    toVHDL_kh(topmodule, signals)

i_files.replaced_files is a dict with filenames as keys and StringIO objects as 
values. An easy way to write to disk after conversion is:

for fname, value in replaced_files.iteritems():
    with open(fname, "w") as f:
        f.write(value.getvalue())
        
open_interceptor() is a class that takes a tuple as argument with the file 
extensions to "intercept" while a function wants to open a file for writing. 
All other open() operations remain intact.

Internals
---------

Module toVHDL_kh.py defines toVHDL_kh() as an object of class _ToVHDL_kh_Convertor, 
subclassed from _ToVHDLConvertor.

_ToVHDL_kh_Convertor adds two attributes and two additional methods:

    _convert_filter(self, h, intf, siglist, memlist, genlist)
    _kh_filter(self, h, intf, genlist)
    
_convert_filter() is intended as an entry point to extend converter functionality through
subclassing (currently unused).
_kh_filter() method modifies internal structure, call converter recursively and manages 
components generated code.

Since there's only a single function call added to toVHDL.__call__(), instead of copy-paste
original code, a monkey-patch adds the needed function calls in runtime. Rationale behind 
this behavior is to keep up with latest code from main repository. This will change 
when a viable entry point is included in the main code.

ToVHDL_kh overrides two functions from _toVHDL original module:
    
    _writeSigDecls(f, intf, siglist, memlist)
    _convertGens(genlist, siglist, memlist, vfile)
    
_writeSigDecls() writes component declarations and call its original function.
_convertGens() call its original function and then writes component 
instantiations with its port maps.

ToVHDL_kh also requires a modified _HierExtr() class. Module _mod_hierarchy.py defines 
two classes based on myhdl._extractHierarchy module:

    class _Instance(object):
    Defines two additional members to original _Instance object from myhdl._extractHierarchy
    
        func: reference to called function
        argdict : all other arguments and values not in sigdict or memdict
        
    class _HierExtr(_original_HierExtr)
        Subclass _HierExtr from myhdl._extractHierarchy to support "func" and "argdict" 
        members of _Instance
        
Last update: Fri, 12 Apr 2013 18:23:23 +0200