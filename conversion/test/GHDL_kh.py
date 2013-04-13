#!/usr/bin/env python
# -*- coding: utf-8 -*-

from myhdl.conversion import verify, analyze, registerSimulator
import sys
import os
import glob
import subprocess

registerSimulator(
    name="GHDL_kh",
    hdl="VHDL",
    analyze="python GHDL_kh.py %(topname)s",
    elaborate="ghdl -e --workdir=work -o %(unitname)s_ghdl %(topname)s",
    simulate="ghdl -r %(unitname)s_ghdl"
)

verify.simulator = analyze.simulator = "GHDL_kh"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # TODO: change to mimic make-like operation
        #print "DEBUG: Extra analyze for %s" % sys.argv[1]
        files = glob.glob("*.vhd")
        files.sort(cmp=lambda x, y : cmp(os.stat(x).st_mtime, os.stat(y).st_mtime))
        pck = False
        for f in files:
            if f.startswith("pck_myhdl_"):
                pck = f
                #print "Analyze %s" % pck
                retval = subprocess.call("ghdl -a --workdir=work %s" % pck, shell=True)
                if retval != 0:
                    print "GHDL Analyze error (%s)." % pck
                    sys.exit(retval)
                break
        if pck:
            files.remove(pck)
        for f in files:
            if f == "%s.vhd" % sys.argv[1]:
                continue
            if os.path.isfile("work/" + f.replace(".vhd", ".o")):
                if os.stat(f).st_mtime < os.stat("work/" + f.replace(".vhd", ".o")).st_mtime:
                    #print "File up to date %s" % f
                    continue
            #print "Analyze %s" % f
            retval = subprocess.call("ghdl -a --workdir=work %s" % f, shell=True)
            #if retval != 0:
            #    print "GHDL Analyze error (ignore)."
        #print "Analyze %s.vhd" % sys.argv[1]
        retval = subprocess.call("ghdl -a --workdir=work %s.vhd" % sys.argv[1], shell=True)
        if retval != 0:
            print "GHDL Analyze error (%s)." % f
            sys.exit(retval)
