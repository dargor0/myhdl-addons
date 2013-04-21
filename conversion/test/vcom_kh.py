#!/usr/bin/env python
# -*- coding: utf-8 -*-

from myhdl.conversion import verify, analyze, registerSimulator
import sys
import os
import glob
import subprocess

registerSimulator(
    name="vcom_kh",
    hdl="VHDL",
    analyze="python vcom_kh.py %(topname)s",
    #analyze="vcom -work work_vcom pck_myhdl_%(version)s.vhd %(topname)s.vhd",
    simulate='vsim work_vcom.%(topname)s -quiet -c -do "run -all; quit -f"',
    skiplines=6,
    skipchars=2,
    ignore=("# **", "#    Time:", "# //", "# run", "#  quit")
)

verify.simulator = analyze.simulator = "vcom_kh"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # TODO: change to mimic make-like operation
        #print "DEBUG: Extra analyze for %s" % sys.argv[1]
        files = glob.glob("*.vhd")
        files.sort(cmp=lambda x, y : cmp(os.stat(x).st_mtime, os.stat(y).st_mtime))
        pck = []
        # Analyze packages first
        for f in files:
            if f.startswith("pck_"):
                pck.append(f)
                #print "Pck Analyze %s" % f
                retval = subprocess.call("vcom -work work_vcom %s" % f, shell=True)
                if retval != 0:
                    print "vcom Analyze error (%s)." % f
                    sys.exit(retval)
        for f in pck:
            files.remove(f)
        for f in files:
            if f == "%s.vhd" % sys.argv[1]:
                continue
            if os.stat(f).st_size == 0:
                continue
            # assume existing "work_vcom"
            if os.path.isdir("work_vcom/" + f.replace(".vhd", "").lower()):
                if os.stat(f).st_mtime < os.stat("work_vcom/" + f.replace(".vhd", "").lower()).st_mtime:
                    #print "File up to date %s" % f
                    continue
            #print "Sub Analyze %s" % f
            retval = subprocess.call("vcom -work work_vcom %s" % f, shell=True)
            #if retval != 0:
            #    print "vcom Analyze error (ignore)."
        #print "Analyze %s.vhd" % sys.argv[1]
        retval = subprocess.call("vcom -work work_vcom %s.vhd" % sys.argv[1], shell=True)
        if retval != 0:
            print "vcom Analyze error (%s)." % f
            sys.exit(retval)
