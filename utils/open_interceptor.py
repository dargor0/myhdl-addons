#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# open_interceptor: 
#    intercept open() calls to avoid direct file writing
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

import __builtin__
import StringIO

_replaced_stack = []
_original_open = __builtin__.open

class StringIO_noclose(StringIO.StringIO):
    def close(self):
        return None
        
    def true_close(self):
        return StringIO.close(self)
        
class open_interceptor():
    """
    open_interceptor: simple interceptor based on file extensions
    """
    def __init__(self, file_extensions, enabled=True):
        self.file_extensions = file_extensions
        self.enable_replace = enabled
        self.replaced_files = {}
        
    def get_interceptor(self):
        return interceptor(self)
        
    def intercept_enter(self):
        global _replaced_stack
        _replaced_stack.append(self)
        
    def intercept_exit(self):
        global _replaced_stack
        if _replaced_stack.pop() != self:
            raise ValueError("Stack inconsistent.")
            
    def filter(self, name, mode, buffering):
        # simple filter based on file extension
        for xt in self.file_extensions:
            if name.endswith(xt):
                return True
        return False
        
class interceptor():
    def __init__(self, ic_ref):
        self.ic_ref = ic_ref
        self.built_module = __import__("__builtin__")
        self.prev_open = getattr(self.built_module, "open")
    
    def __enter__(self):
        self.ic_ref.intercept_enter()
        setattr(self.built_module, "open", intercept_open)
        
    def __exit__(self, exc_type, exc_value, traceback):
        self.ic_ref.intercept_exit()
        setattr(self.built_module, "open", self.prev_open)
        
def intercept_open(name, mode='r', buffering=0):
    global _replaced_stack
    ic_ref = _replaced_stack[-1]
    if ic_ref.enable_replace:
        # only replace new files
        if mode == 'w':
            if ic_ref.filter(name, mode, buffering):
                f = StringIO_noclose()
                ic_ref.replaced_files[name] = f
                return f
    # otherwise, use original open
    return _original_open(name, mode, buffering)
    
def current_interceptor():
    global _replaced_stack
    return _replaced_stack[-1]
