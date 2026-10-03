#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import myhdl
from toVHDL_kh import toVHDL_kh

oldconv = myhdl.toVHDL
for k, v in sys.modules.items():
    if k == "toVHDL_kh":
        continue
    elif "toVHDL" in dir(v):
        if v.toVHDL != toVHDL_kh:
            setattr(v, "toVHDL", toVHDL_kh)
            
# keep old reference in main module
if oldconv != toVHDL_kh:
    setattr(myhdl, "_old_toVHDL", oldconv)
print "Monkey patch toVHDL to %r" % myhdl.toVHDL

