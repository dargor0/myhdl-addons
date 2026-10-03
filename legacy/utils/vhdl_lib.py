#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# vhdl_lib: base library for VHDL source files
# * Base model for VHDL source files
# * Parser object
# * Code generator
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

import shlex
import StringIO
import re
import os
from collections import OrderedDict

_vhdl_validtypes = ["bit", "bit_vector", "boolean", "character", "integer", 
"natural", "positive", "real", "string", "time", "signed", "unsigned", 
"std_logic", "std_logic_vector"]

_vhdl_typesizes = {"bit": 1, "bit_vector": None, "boolean": 1, "character": 8, "integer": 32, 
"natural": 32, "positive": 32, "real": 32, "string": None, "time": 64, "signed": None, "unsigned": None, 
"std_logic": 1, "std_logic_vector": None}

_vhdl_vector_bases = {"bit_vector": "bit", "std_logic_vector": "std_logic", "signed": "bit", 
"unsigned": "bit", "string": "character"}

class ParseException(Exception):
    def __init__(self, message, token=None):
        super(ParseException, self).__init__(message)
        self._token = token
        if token is not None:
            linestr = ""
            colstr = ""
            if hasattr(token, "_getlinecol"):
                line, col = token._getlinecol()
                if line is not None:
                    linestr = "line %d " % line
                if col is not None:
                    colstr = "col %d " % col
            self._premsg = "[%s%sNear %s] " % (linestr, colstr, repr(token))
        else:
            self._premsg = ""
    def __str__(self):
        return self._premsg + Exception.__str__(self)


class str_token(str):
    """
    string object with related line and col numbers
    """
    def __new__(cls, basestr, line=None, col=None, meta=None):
        return super(str_token, cls).__new__(cls, basestr)
    def __init__(self, basestr, line=None, col=None, meta=None):
        self._linenum = line
        self._colnum = col
        self._meta = meta
    def _getlinecol(self):
        return (self._linenum, self._colnum)
    def _getmeta(self):
        return self._meta

class vhdl_model(object):
    """
    VHDL parser - model object
    
    This object holds a simple model of a VHDL file
    """
    def __init__(self, entity_name=None, package_name=None):
        
        # file sections 
        self._header = []
        self._library_decl = OrderedDict()
        self._package = package_name
        self._entity = entity_name
        self._generics = OrderedDict()
        self._ports = OrderedDict()
        self._constants = {}
        self._architecture_name = None
        self._architecture_body = ""
        self._configuration = None
        
    def add_header(self, header):
        """
        Header: usually comments at the beginning of the file (summary, 
        license, etc.)
        """
        self._header.append(header)
        
    def add_library(self, library, sublib="", element=""):
        """
        Library declaration: include keywords 'library' and 'use'
        """
        s = library.split(".")
        libname = s[0]
        if len(s) == 1:
            # use library, sublib, and use
            slname = sublib
            ename = element
        elif len(s) == 2:
            # ignore sublib
            slname = s[1]
            ename = element
        else:
            # complete route in 'library'
            slname = s[1]
            ename = s[2]
        if libname not in self._library_decl:
            self._library_decl[libname] = OrderedDict()
        if slname != "":
            self._library_decl[libname][slname] = []
            #if ename != "":
            self._library_decl[libname][slname].append(ename)
                
    def add_std_library(self):
        self.add_library("ieee.std_logic_1164.all")
        self.add_library("ieee.numeric_std.all")
    
    def add_package(self, package):
        """
        Packages: Not implemented yet.
        """
        raise NotImplementedError("Packages not yet supported.")
        
    def set_entity_name(self, entity_name):
        """
        A vhdl file can only have one entity
        """
        self._entity = entity_name
        
    def add_generic(self, name, gentype=None, defvalue=None, description="", **kwargs):
        """
        New/edit generic for current entity
        """
        if name in self._generics:
            if gentype is not None:
                # type name is defined
                t = self._check_type(gentype)
                self._generics[name]["typedef"] = t
            if defvalue is not None:
                self._generics[name]["defvalue"] = defvalue
            self._generics[name]["desc"] = description
        else:
            if (gentype is None and defvalue is None):
                raise ValueError("You must pass a type or a default value.")
            elif gentype is not None:
                # type name is defined
#                print "DEBUG TEST: gentype %s" % repr(gentype)
                t = self._check_type(gentype)
            elif defvalue is not None:
                # guess type
                t = self._guess_type(defvalue)
            self._generics[name] = {"typedef": t, "defvalue": defvalue, "desc": description}
            self._constants[name] = self._const_solve(defvalue)
    
    def add_port(self, name, direction, sigtype=None, refvalue=None, description="", **kwargs):
        """
        New/edit port for current entity
        Each port is {"dir", "typedef", "desc"}
        """
        if direction not in ("in", "out", "inout", "buffer"):
            raise ValueError("Unknown signal direction: %s" % dire)
        if name in self._ports:
            if sigtype is not None:
                t = self._check_type(sigtype)
                self._ports[name]["typedef"] = t
            elif defvalue is not None:
                t = self._guess_type(refvalue)
                self._ports[name]["typedef"] = t
            self._ports[name]["dir"] = direction
            self._ports[name]["desc"] = description
        else:
            if (sigtype is None) and (refvalue is None):
                raise ValueError("You must pass a type or a reference value.")
            elif sigtype is not None:
                # type name is defined
                t = self._check_type(sigtype)
            elif refvalue is not None:
                # guess value
                t = self._guess_type(refvalue)
            self._ports[name] = {"dir": direction, "typedef": t, "desc": description}
        
    def set_architecture_name(self, architecture_name):
        self._architecture_name = architecture_name
    def add_architecture_body(self, body):
        self._architecture_body += body
        
    # ******
    # access to model
    def get_entity_name(self):
        return self._entity
        
    def get_generics_iter(self):
        return self._generics.iteritems()
        
    def get_ports_iter(self):
        return self._ports.iteritems()
        
    def get_declared_constants(self):
        return self._constants.iteritems()
        
    def get_constant_value(self, name, as_str=True):
        if name not in self._constants:
            raise ValueError("Constant name '%s' not declared." % name)
        if as_str:
            det = self.type_details(name)
            # WARNING HACK: use 'isarray' data for output formatting
            # TODO: fix this
            if det["isarray"]:
                return '"%d"' % self._constants[name]
            else:
                return str(self._constants[name])
        else:
            return self._constants[name]
        
    # ******
    # utilities
    def type_details(self, object):
        if object in self._generics:
            obj_split = self._generics[object]["typedef"]
        elif object in self._ports:
            obj_split = self._ports[object]["typedef"]
        elif type(object) == list:
            obj = self._check_type(" ".join(object))
        else:
            obj = self._check_type(object)
        retval = {"base": obj_split[0]}
        if len(obj_split) == 1:
            retval["isarray"] = False
            retval["left"] = None
            retval["defdir"] = None
            retval["right"] = None
            retval["bitlen"] = _vhdl_typesizes[retval["base"]]
            retval["rawdef"] = retval["base"]
            retval["solveddef"] = retval["base"]
        else:
            retval["isarray"] = True
            retval["left"] = self._const_solve(obj_split[1])
            retval["defdir"] = obj_split[2]
            retval["right"] = self._const_solve(obj_split[3])
            basesize = _vhdl_typesizes[retval["base"]]
            if basesize is None:
                basesize = _vhdl_typesizes[_vhdl_vector_bases[retval["base"]]]
            if retval["defdir"].lower() == "to":
                retval["bitlen"] = (retval["right"] - retval["left"] + 1) * basesize
            else:
                retval["bitlen"] = (retval["left"] - retval["right"] + 1) * basesize
            retval["rawdef"] = "%s (%s %s %s)" % (retval["base"], obj_split[1], retval["defdir"], obj_split[3])
            retval["solveddef"] = "%s (%s %s %s)" % (retval["base"], retval["left"], retval["defdir"], retval["right"])
        return retval
        
    def set_generic_value(self, name, value):
        if name not in self._constants:
            raise ValueError("Constant name '%s' not declared." % name)
        self._constants[name] = value
    # ******
    
    def _check_type(self, typestr):
        s = [x.strip() for x in typestr.partition("(")]
        if s[0] not in _vhdl_validtypes:
            raise ValueError("Invalid VHDL type: %s" % typestr)
        if s[1] == "":
            return (s[0], )
        if s[2].find("downto"):
            st = [x.strip() for x in s[2].strip()[:-1].partition("downto")]
        elif s[2].find("to"):
            st = [x.strip() for x in s[2].strip()[:-1].partition("to")]
        else:
            raise ValueError("Unknown VHDL type declaration for %s : %s" % (s[0], typestr))
        st.insert(0, s[0])
        return st
        
    def _guess_type(self, value):
        if type(value) == boolean:
            return ["boolean"]
        if type(value) == int:
            return ["integer"]
        elif type(value) == str:
            # guess type based on content
            for i in (2, 8, 10, 16):
                try:
                    midval = int(value)
                    return ["integer"]
                except ValueError:
                    pass
            return ["string"]
        else:
            raise ValueError("Unknown type for %s" % repr(value))
            
    def _const_solve(self, expr):
        return eval(str(expr), globals(), self._constants)
    
class vhdl_codegen(object):
    def __init__(self, model):
        self.model = model
        self.usetab = "    " # 4-space tabs
        
    def write_file(self, filename=None):
        if filename is None:
            filename = self.to_valid_str(self.model._entity) + ".vhdl"
        with open(filename, "w") as f:
            f.write(self.generate_content())
    
    def generate_content(self):
        """
        Generate the entire file from model
        """
        sret = "".join(self.model._header)
        sret += self.generate_libdecl() + "\n"
        sret += self.generate_entity_section() + "\n"
        sret += self.generate_architecture_section() + "\n"
        return sret
        
    def generate_libdecl(self):
        sret = "\n"
        for libname, sublibs in self.model._library_decl.iteritems():
            if libname != "work":
                sret += "library %s;\n" % libname
            for slname, sl in sublibs.iteritems():
                for el in sl:
                    if el != "":
                        sret += "use %s.%s.%s;\n" % (libname, slname, el)
                    else:
                        sret += "use %s.%s;\n" % (libname, slname)
            sret += "\n"
        return sret
            
    def generate_entity_section(self, secbase="entity"):
        """
        Generate entity section
        """
        sret = "%s %s is\n" % (secbase, self.model._entity)
        stmp = self.generate_generics_section()
        if stmp != "":
            sret += self.add_tab(stmp, 1) + ";\n"
        stmp = self.generate_ports_section()
        if stmp != "":
            sret += self.add_tab(stmp, 1) + ";\n"
        sret += "end %s %s;\n" % (secbase, self.model._entity)
        return sret
        
    def generate_architecture_section(self):
        """
        Generate architecture section
        """
        sret = "architecture %s of %s is\n" % (self.model._architecture_name, self.model._entity)
        sret += self.add_tab(self.model._architecture_body, 1)
        sret += "\nend architecture %s;\n" % self.model._architecture_name
        return sret

    def generate_generics_section(self):
        """
        Generate generics section used on entity and component
        """
        sret = "generic (\n"
        l = self.generate_generic_declaration(None, True)
        if len(l) > 0:
            sret += ";\n".join(self.add_tab(l))
            sret += "\n)"
        else:
            # empty generics section
            sret = ""
        return sret
        
    def generate_ports_section(self):
        """
        Generate ports section used on entity and component
        """
        sret = "port (\n"
        l = self.generate_signal_declaration(None)
        if len(l) > 0:
            sret += ";\n".join(self.add_tab(l))
            sret += "\n)"
        else:
            # empty ports section
            sret = ""
        return sret
    def generate_component(self):
        """
        Generate a component definition for this object.
        """
        return self.generate_entity_section("component")

    def generate_generic_declaration(self, generic=None, with_default=False):
        """
        Generate a generic declaration for this object.
        
        Arguments:
        * generic : either a name or a list index for a particular generic
        * with_default : True to add the default value
        
        Returns:
        * A string when generic argument is used
        * A list of strings with all generics 
        """
        if generic is None:
            # all generics
            l = []
            for k in self.model._generics.iterkeys():
                l.append(self.generate_generic_declaration(k, with_default))
            return l
        else:
            # search for correct index
            if isinstance(generic, int):
                gname = self.model._generics.keys()[generic]
            elif isinstance(generic, str):
                gname = generic
            else:
                raise TypeError("Unknown key to generic list: '%s'." % repr(generic))
            gdata = self.model._generics[gname]
            sret = "%s : %s" % (self.to_valid_str(gname), self.to_type_str(gdata["typedef"]))
            if with_default:
                sret += ' := %s' % gdata["defvalue"]
            return sret

    def generate_signal_declaration(self, signal=None):
        """
        Generate a signal declaration for this object.
        
        Arguments:
        * signal : either a name or a list index for a particular signal
        
        Returns:
        * A string when signal argument is used
        * A list of strings with all signals
        """
        if signal is None:
            # all signals
            l = []
            for k in self.model._ports.iterkeys():
                l.append(self.generate_signal_declaration(k))
            return l
        else:
            if isinstance(signal, int):
                sname = self.model._ports.keys()[signal]
            elif isinstance(signal, str):
                sname = signal
            else:
                raise TypeError("Don't know how to search with '%s'." % repr(signal))
            sdata = self.model._ports[sname]
                
            sret = "%s : %s %s" % (self.to_valid_str(sname), sdata["dir"], self.to_type_str(sdata["typedef"]))
            return sret
    
    def to_type_str(self, type_obj):
        if len(type_obj) == 1:
            return type_obj[0]
        else:
            # TODO: guess vector here
            return "%s(%s %s %s)" % tuple(type_obj)
            
    def type_conversion(self, from_type, to_type):
        # TODO: better heuristics for type conversions
        if from_type == to_type:
            return None
        if to_type == "std_logic_vector":
            if from_type in ("unsigned", "signed"):
                return "std_logic_vector(%s)"
            elif from_type == "integer":
                return "std_logic_vector(to_signed(%s))"
            elif from_type in ("positive", "natural"):
                return "std_logic_vector(to_unsigned(%s))"
        elif to_type in ("signed", "unsigned"):
            return str(to_type) + "(%s)"
        elif to_type == "integer":
            return "to_integer(%s)"
        else:
            return "%s"
    
    def to_valid_str(self, str_in):
        """
        Convert an input string, changing special characters used on
        the HDL language. Useful for set names .
        
        Argument:
        * str_in: string to convert
        
        Returns: the converted string.
        """
        # list of transformations:
        # * strip spaces
        # * space,":" with "_"
        s = str_in.strip()
        s = s.replace(" ", "_")
        s = s.replace(":", "_")
        return s
        
    def make_comment(self, data):
        """
        Convert string data to language comment
        
        Argument:
        * data: string or list of strings to convert
        
        Returns: a new string or list of strings with comments added.
        """
        return self._prepend_str(data, "-- ")
            
    def add_tab(self, data, level=1):
        """
        Add an indentation level to the string
        
        Argument:
        * data: string or list of strings
        * level: how many indentation levels to add. Default 1
        
        Returns: string or list of strings with <level> indentation levels.
        """
        leveltabs = self.usetab*level
        return self._prepend_str(data, leveltabs)
        
    def _prepend_str(self, data, pretext):
        if isinstance(data, str):
            return "\n".join(["%s%s" % (pretext, x) for x in data.split("\n")])
        else:
            # don't put exception catch. It is an error if data is not
            # iterable.
            it = iter(data)
            retval = ["%s%s" % (pretext, x) for x in it]
            return retval
            
class vhdl_parser(object):
    """
    VHDL parser - code object
    
    This object holds a simple model of a VHDL file
    """
    def __init__(self, initial_content):
        self.model = vhdl_model()
        self.filename = "Untitled.vhdl"
        
        # use StringIO to save contents
        if initial_content is None:
            self.filecontent = StringIO.StringIO()
        elif type(initial_content) == str:
            if os.path.exists(initial_content):
                self.filename = initial_content
                with open(initial_content) as f:
                    self.filecontent = StringIO.StringIO(f.read())
            else:
                # assume string content
                self.filecontent = StringIO.StringIO(initial_content)
        elif type(initial_content) == file:
            self.filename = initial_content.name
            t = initial_content.tell()
            initial_content.seek(0)
            self.filecontent = StringIO.StringIO(initial_content.read())
            initial_content.seek(t)
        elif isinstance(initial_content, StringIO.StringIO):
            self.filecontent = initial_content
        else:
            raise ValueError("Unable to set initial content with %s" % repr(initial_content))
        self.filecontent.seek(0)
        
    # main methods
    def parse(self):
        """
        Stages:
        """
        token_list = self._tokenize()
        it = iter(token_list)
        # Note: use index to walk token list
        idx = 0
        # header section
        while idx < len(token_list):
            if token_list[idx].startswith("--"):
                self.model.add_header(token_list[idx])
            else:
                break
            idx += 1
        # next section
        while idx < len(token_list):
            sec = token_list[idx]
            # ignore comments (NOTE: could be saved if tied to a keyword, TODO)
            if sec.startswith("--"):
                idx += 1
                continue
            elif sec.lower() in ("library", "use"):
                # read entire line until ";" token
                idx_end = self._find_token(token_list, ";", idx)
                if idx_end is None:
                    raise ParseException("Statement '%s' without ';'." % sec, sec)
                self._p_library(token_list[idx:idx_end])
                idx = idx_end + 1
            elif sec.lower() == "entity":
                # read entire entity until nearest end statement
                idx_end = self._find_token(token_list, "end", idx)
                if idx_end is None:
                    raise ParseException("Statement '%s' without 'end'." % sec, sec)
                # next: either <entity_name> or "sec"
                idx_end += 1
                if token_list[idx_end].lower() == "entity":
                    # next is <section_name>
                    idx_end += 1
                if token_list[idx+1] != token_list[idx_end]:
                    raise ParseException("Ambiguous entity definition: (%s or %s)" % (token_list[idx+1], token_list[idx_end]), sec)
                # next is ";"
                idx_end += 1
                if token_list[idx_end] != ";":
                    raise ParseException("Expected ';'", token_list[idx_end])
                # process section
                self._p_entity(token_list[idx:idx_end])
                idx = idx_end + 1
            elif sec.lower() == "architecture":
                # find correct "end" token: 
                idx_end = idx
                while idx_end < len(token_list):
                    idx_end = self._find_token(token_list, "end", idx_end)
                    if idx_end is None:
                        raise ParseException("Statement 'architecture %s' without 'end'." % token_list[idx+1], sec)
                    # next: either <architecture_name> or "architecture"
                    idx_end += 1
                    if token_list[idx_end].lower() in ("architecture", token_list[idx+1]):
                        break
                if token_list[idx_end].lower() == "architecture":
                    # next is <architecture_name>
                    idx_end += 1
                # next is ";"
                idx_end += 1
                if token_list[idx_end] != ";":
                    raise ParseException("Expected ';'", token_list[idx_end])
                # process architecture
                self._p_architecture(token_list[idx:idx_end])
                idx = idx_end + 1
            else:
                raise ParseException("Unknown section '%s'" % sec, sec)
        
    def _tokenize(self):
        token_list = []
        it = iter(self.filecontent)
        linenum = 0
        for line in it:
            linenum += 1
            # get rid of tabs and spaces at line beginning
            ls_line = line.lstrip()
            # get first line comments
            if ls_line.startswith("--"):
                colnum = line.find("--") + 1
                token_list.append(str_token(ls_line, linenum, colnum))
            else:
                # split by lines
                split_line = re.split(r"(\s|:=|<=|=>|--|\W)", ls_line)
                # check for comments at the end, take entire comment as a token
                try:
                    idx = split_line.index("--")
                    c = "".join(split_line[idx:])
                    split_line[idx] = c
                    del(split_line[idx+1:])
                except:
                    pass
                # add line,col info to all strings
                for i in range(len(split_line)):
                    colnum = line.find(split_line[i]) + 1
                    meta = None
                    if split_line[i].startswith("--"):
                        # hack: use "meta" argument to flag comment as "inline"
                        meta = "inline-comment"
                    split_line[i] = str_token(split_line[i], linenum, colnum, meta)
                token_list.extend(split_line)
        # special case: quotes
        idx = 0
        idx_end = 0
        for quote in ('"', "'"):
            while True:
                try:
                    idx = token_list.index(quote)
                except:
                    break
                try:
                    idx_end = token_list.index(quote, idx+1) + 1
                except:
                    raise ParseException("Found a open <%s>." % quote, token_list[idx])
                t = "".join(token_list[idx:idx_end])
                token_list[idx] = t
                del(token_list[idx+1:idx_end])
            
        # clean whitespaces and empty strings
        for space in ("", " ", "\n"):
            while True:
                try:
                    idx = token_list.index(space)
                except:
                    break
                del(token_list[idx])
        return token_list
                
    def _find_token(self, list, token, start=0, end=-1):
        if end == -1:
            end = len(list)
        for i in range(start, end):
            if list[i].lower() == token.lower():
                return i
        return None
            
    # sections
    def _p_library(self, statements):
        self.model.add_library("".join(statements[1:]))

    def _p_entity(self, statements):
        gp = []
        if statements[0].lower() != "entity":
            raise ParseException("Expected 'entity' statement.", statements[0])
        self.model.set_entity_name(statements[1])
        if statements[2].lower() != "is":
            raise ParseException("Expected 'is' statement.", statements[2])
        stat_count = 3
        while stat_count < len(statements):
            sec = statements[stat_count]
            if sec.startswith("--"):
                stat_count += 1
                continue
            if sec in gp:
                raise ParseException("Duplicate '%s' definition." % sec, sec)
            if sec.lower() in ("generic", "port"):
                stat_count += 1
                if statements[stat_count] != "(":
                    raise ParseException("Expected '(' token.", statements[stat_count])
                parenthesis_count = 0
                stat_count += 1
                while stat_count < len(statements):
                    if statements[stat_count].startswith("--"):
                        stat_count += 1
                        continue
                    # <identifier>  
                    identifier = statements[stat_count]
                    stat_count += 1
                    if statements[stat_count] != ":":
                        raise ParseException("Expected ':' token.", statements[stat_count])
                    # <direction> in port
                    if sec.lower() == "port":
                        stat_count += 1
                        direction = statements[stat_count]
                    # <type>
                    stat_count += 1
                    id_type = []
                    while statements[stat_count] not in (":=", ";"):
                        id_type.append(statements[stat_count])
                        if statements[stat_count] == "(":
                            parenthesis_count += 1
                        elif statements[stat_count] == ")":
                            parenthesis_count -= 1
                        stat_count += 1
                        if stat_count == len(statements):
                            raise ParseException("Error in identifier '%s'" % identifier, statements[stat_count-1])
                        if statements[stat_count] == ")" and parenthesis_count <= 0:
                            break
                    id_type_str = " ".join(id_type)
                    # <optional default value>
                    if statements[stat_count] == ":=":
                        stat_count += 1
                        defval = []
                        while statements[stat_count] not in (";", ")"):
                            defval.append(statements[stat_count])
                            if statements[stat_count] == "(":
                                parenthesis_count += 1
                            elif statements[stat_count] == ")":
                                parenthesis_count -= 1
                            stat_count += 1
                            if stat_count == len(statements):
                                raise ParseException("Error in identifier '%s'" % identifier, statements[stat_count-1])
                            if statements[stat_count] == ")" and parenthesis_count <= 0:
                                break
                        defval_str = " ".join(defval)
                    else:
                        defval_str = None
                    # optional comment description
                    if (statements[stat_count+1].startswith("--")) and (statements[stat_count+1]._getmeta() == "inline-comment"):
                        comment = statements[stat_count+1]
                        del(statements[stat_count+1])
                    else:
                        comment = ""
                    # generic/port definition to model
                    if sec.lower() == "generic":
                        self.model.add_generic(identifier, id_type_str, defval_str, comment)
                    elif sec.lower() == "port":
                        self.model.add_port(identifier, direction, id_type_str, None, comment)
                    if statements[stat_count] == ";":
                        # there's a next generic/port
                        stat_count += 1
                        continue
                    elif statements[stat_count] == ")":
                        # closed generic/port process
                        break
                    else:
                        raise ParseException("Unexpected '%s'" % statements[stat_count], statements[stat_count])
                # close generic/port
                stat_count += 1
                if statements[stat_count] != ";":
                    raise ParseException("Expected ';' token.", statements[stat_count])
                stat_count += 1
                # only one generic/port
                gp.append(sec)
            elif sec.lower() == "end":
                break
            else:
                raise ParseException("Unexpected '%s' statement." % sec, sec)
        
    def _p_architecture(self, line):
        self.model.set_architecture_name(line[1])
        
        # WARNING: copy entire architecture content without further parsing
        # TODO: implement architecture parsing (including model)
        
        # copy all text lines from line[0] to line[-1]. Don't include 'architecture'
        # and 'end architecture' statements
        startline, col = line[0]._getlinecol()
        endline, col = line[-1]._getlinecol()
        startline += 1
        linecount = 0
        self.filecontent.seek(0)
        for fl in self.filecontent:
            linecount += 1
            if linecount >= endline:
                break
            if linecount >= startline:
                self.model.add_architecture_body(fl)
