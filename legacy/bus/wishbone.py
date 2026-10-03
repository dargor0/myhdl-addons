#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Wishbone blocks and support for MyHDL
#
# Author:  Oscar Diaz
# Version: 1.0
# Date:    05-03-2010
# WishBone compliant

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
# License along with this library; if not, write to the
# Free Software  Foundation, Inc., 59 Temple Place, Suite 330,
# Boston, MA  02111-1307  USA
#

from myhdl import Signal, intbv, enum, always, always_comb
import types

# Wishbone Interconnection types
class wishbone_intercon_p2p():
	"""
	Wishbone point-to-point interconnect
	This interconnection class implements a simple connection between a 
	master and a slave cores.
	Arguments:
	* adr_width
	* data_width
	* data_gran
	Note: The signals defined here are named from the master point of view
	"""
	def __init__(self, adr_width=8, data_width=8, data_gran=8, *opt_signals, **kwargs):
		# parameters
		self.data_width = data_width
		self.data_gran = data_gran
		self.adr_width = adr_width
		# required signals
		self.CLK = Signal(intbv(0)[1:])
		self.RST = Signal(intbv(0)[1:])
		self.DAT_I = Signal(intbv(0)[data_width:])
		self.DAT_O = Signal(intbv(0)[data_width:])
		self.ADR = Signal(intbv(0)[adr_width:])
		self.WE = Signal(intbv(0)[1:])
		self.STB = Signal(intbv(0)[1:])
		self.CYC = Signal(intbv(0)[1:])
		self.SEL = Signal(intbv(0)[data_width/data_gran:])
		self.ACK = Signal(intbv(0)[1:])
		# optional signals
		if ("RTY" in opt_signals):
			self.RTY = Signal(intbv(0)[1:])
		else:
			self.RTY = None
		if ("ERR" in opt_signals):
			self.ERR = Signal(intbv(0)[1:])
		else:
			self.ERR = None
		if ("LOCK" in opt_signals):
			self.LOCK = Signal(intbv(0)[1:])
		else:
			self.LOCK = None
		# optional TAG signals
		if "TGD_I" in kwargs:
			self.TGD_I = kwargs["TGD_I"]
		else
			self.TGD_I = None
		if "TGD_O" in kwargs:
			self.TGD_O = kwargs["TGD_O"]
		else
			self.TGD_O = None
		if "TGA" in kwargs:
			self.TGA = kwargs["TGA"]
		else
			self.TGA = None
		if "TGC" in kwargs:
			self.TGC = kwargs["TGC"]
		else
			self.TGC = None

# wishbone data interface:
class wishbone_master_sig():
"""
	Class for wishbone master signals
	An instantiation of this class contains a list of signals 
	used by a master core.
	Arguments:
	* intercon: the intercon to connect
"""
	def __init__(self, intercon):
		# basic parameters
		self.data_width = intercon.data_width
		self.data_gran = intercon.data_gran
		self.adr_width = intercon.adr_width
		# intercon reference
		self.intercon = intercon
		# signal mapping
		if isinstance(intercon, wishbone_intercon_p2p):
			# mapping from a simple point-to-point intercon
			self.CLK_I = intercon.CLK
			self.RST_I = intercon.RST
			self.DAT_I = intercon.DAT_I
			self.DAT_O = intercon.DAT_O
			self.ADR_O = intercon.ADR
			self.WE_O = intercon.WE
			self.STB_O = intercon.STB
			self.CYC_O = intercon.CYC
			self.SEL_O = intercon.SEL
			self.ACK_I = intercon.ACK
			# optional signals
			self.RTY_I = intercon.RTY
			self.ERR_I = intercon.ERR
			self.LOCK_O = intercon.LOCK
			# optional TAG signals
			self.TGD_I = intercon.TGD_I
			self.TGD_O = intercon.TGD_O
			self.TGA_O = intercon.TGA
			self.TGC_O = intercon.TGC
		else
			raise AttributeError("Unknown intercon type for %s" % str(intercon))

class wishbone_slave_sig():
"""
	Class for wishbone slave signals
	An instantiation of this class contains a list of signals 
	used by a slave core.
	Arguments:
	* intercon: the intercon to connect
"""
	def __init__(self, intercon):
		# basic parameters
		self.data_width = intercon.data_width
		self.data_gran = intercon.data_gran
		self.adr_width = intercon.adr_width
		# intercon reference
		self.intercon = intercon
		# signal mapping
		if isinstance(intercon, wishbone_intercon_p2p):
			# mapping from a simple point-to-point intercon
			self.CLK_I = intercon.CLK
			self.RST_I = intercon.RST
			self.DAT_I = intercon.DAT_O
			self.DAT_O = intercon.DAT_I
			self.ADR_I = intercon.ADR
			self.WE_I = intercon.WE
			self.STB_I = intercon.STB
			self.CYC_I = intercon.CYC
			self.SEL_I = intercon.SEL
			self.ACK_O = intercon.ACK
			# optional signals
			self.RTY_O = intercon.RTY
			self.ERR_O = intercon.ERR
			self.LOCK_I = intercon.LOCK
			# optional TAG signals
			self.TGD_I = intercon.TGD_O
			self.TGD_O = intercon.TGD_I
			self.TGA_I = intercon.TGA
			self.TGC_I = intercon.TGC
		else
			raise AttributeError("Unknown intercon type for %s" % str(intercon))

# wishbone process generators
class wishbone_master_generator():
"""
	Generator class for wishbone master
	This class have functions that returns generators to manage the wishbone bus for
	different bus transfers types.
"""
	def __init__(self, mastersig):
		if isinstance(mastersig, wishbone_master_sig):
			self.wbmsig = mastersig
		else
			raise AttributeError("Argument mastersig  must be of type wishbone_master_sig. Arg: %s" % str(mastersig))
		# prepare chip-enable signal list
		# ce_list structure: elements of: tuple of (ce_signal, baseaddr, highaddr)
		self.ce_list = []
		
	# all the functions defined here will be used as modules to be instantiated.
	def gen_wbm_stm(self, *operations):
	"""
		State machine generator for master
		This function generate the state signal and generator for the state machine
		Basic operations: Single read/write, Block read/write
		Arguments:
		* operations: a list of optional supported operations for the state machine. 
		Example:
		mygen = wishbone_master_generator(themaster)
		mygen.gen_wbm_stm("")
	"""
		# states definition
		self.wbmstate_t = enum("wbm_idle", "wbm_incycle", "wbm_read_wait", "wbm_write_wait", "wbm_rmw_rdwait", "wbm_rmw_midwait", "wbm_rmw_wrwait")
		self.wbmstate_cur = Signal(self.wbmstate_t.wbm_idle)
		
		# list of trigger signals and related states
		self.list_trigsignals = []
		for i in zip(("trig_read", "trig_write", "trig_rmw"), self.wbmstate_t._names[2:5]):
			self.list_trigsignals.append({"name": i[0], "initstate": i[1], "trig": Signal(intbv(0)[1:])})
			
		# Vector of triggers: for use in state machine
		trig_vector = Signal(intbv(0)[3:])
		trig_list = (x["trig"] for x in self.list_trigsignals)
		@always_comb
		def trigvectgen():
			trig_vector.next = concat(*trig_list)
			
		# Vector of acknowledge signals: for use in state machine
		ack_list = [self.ACK_I]
		if self.RTY_I != None:
			ack_list.append(self.RTY_I)
		if self.ERR_I != None:
			ack_list.append(self.ERR_I)
		ack_vector = Signal(intbv(0)[len(ack_list):])
		# the error signals can be sliced with [1:]
		@always_comb
		def ackvectgen():
			ack_vector.next = concat(*ack_list)
		
		# state machine: transitions
		@always(self.wbmsig.CLK_I.posedge, self.wbmsig.RST_I.negedge)
		def wbmstate_proc():
			if self.wbmsig.RST_I = 1:
				self.wbmstate_cur.next = self.wbmstate_t.wbm_idle
			else:
				# state transitions
				if self.wbmstate_cur == self.wbmstate_t.wbm_idle:
					# IDLE state: this state represents no access in master bus
					# transition: a signal trigger that leads to initstate of that trigger
					if trig_vector = 0:
						self.wbmstate_cur.next = self.wbmstate_t.wbm_idle
					else:
						# a transition has been triggered
						for i in self.list_trigsignals:
							if i["trig"] == 1:
								self.wbmstate_cur.next = i["initstate"]
				elif self.wbmstate_cur == self.wbmstate_t.wbm_incycle:
					# INCYCLE state: this state represents a current cycle in progress
					# but inactive. CYC_O is asserted but STB_O is deasserted
					# transition: a signal trigger that leads to initstate of that trigger
					# or no trigger signal to return to idle state
					if trig_vector = 0:
						self.wbmstate_cur.next = self.wbmstate_t.wbm_idle
					else:
						# a transition has been triggered
						for i in self.list_trigsignals:
							if i["sig"] == 1:
								self.wbmstate_cur.next = i["initstate"]
				# operations transitions
				elif self.wbmstate_cur == self.wbmstate_t.wbm_read_wait:
					# READWAIT state: read operation in the bus
					# transition: wait for ACK/ERR/RTY
					if ack_vector = 0:
						self.wbmstate_cur.next == self.wbmstate_t.wbm_read_wait
					else:
						# check if ack or error
						if len(ack_vector) > 1:
							# with ERR/RTY signal
							if ack_vector[1:] = 0:
								# no error in cycle
								if trig_vector = 0:
									# end of cycle
									self.wbmstate_cur.next = self.wbmstate_t.wbm_idle
								else:
									# still in cycle
									self.wbmstate_cur.next = self.wbmstate_t.wbm_incycle
							else:
								# error in cycle (TODO)
								self.wbmstate_cur.next = self.wbmstate_t.wbm_idle
						else:
							# no ERR/RTY signal
							if trig_vector = 0:
								# end of cycle
								self.wbmstate_cur.next = self.wbmstate_t.wbm_idle
							else:
								# still in cycle
								self.wbmstate_cur.next = self.wbmstate_t.wbm_incycle
				elif self.wbmstate_cur == self.wbmstate_t.wbm_write_wait:
					# WRITEWAIT state: write operation in the bus
					# transition: wait for ACK/ERR/RTY
					if ack_vector = 0:
						self.wbmstate_cur.next == self.wbmstate_t.wbm_write_wait
					else:
						# check if ack or error
						if len(ack_vector) > 1:
							# with ERR/RTY signal
							if ack_vector[1:] = 0:
								# no error in cycle
								if trig_vector = 0:
									# end of cycle
									self.wbmstate_cur.next = self.wbmstate_t.wbm_idle
								else:
									# still in cycle
									self.wbmstate_cur.next = self.wbmstate_t.wbm_incycle
							else:
								# error in cycle (TODO)
								self.wbmstate_cur.next = self.wbmstate_t.wbm_idle
						else:
							# no ERR/RTY signal
							if trig_vector = 0:
								# end of cycle
								self.wbmstate_cur.next = self.wbmstate_t.wbm_idle
							else:
								# still in cycle
								self.wbmstate_cur.next = self.wbmstate_t.wbm_incycle
				elif self.wbmstate_cur == self.wbmstate_t.wbm_rmw_rdwait:
					# RMW_READWAIT state: read stage for RMW operation
					# transition: wait for ACK to go to write stage
					if ack_vector = 0:
						self.wbmstate_cur.next == self.wbmstate_t.wbm_rmw_rdwait
					else:
						# check if ack or error
						if len(ack_vector) > 1:
							# with ERR/RTY signal
							if ack_vector[1:] = 0:
								# no error in cycle, next stage
								self.wbmstate_cur.next = self.wbmstate_t.wbm_rmw_midwait
							else:
								# error in cycle (TODO)
								self.wbmstate_cur.next = self.wbmstate_t.wbm_idle
						else:
							# no ERR/RTY signal
							self.wbmstate_cur.next = self.wbmstate_t.wbm_rmw_midwait
				elif self.wbmstate_cur == self.wbmstate_t.wbm_rmw_midwait:
					# RMW_MIDWAIT state: middle wait stage for RMW operation
					# transition: go directly to write stage
					self.wbmstate_cur.next = self.wbmstate_t.wbm_rmw_wrwait
				elif self.wbmstate_cur == self.wbmstate_t.wbm_rmw_wrwait:
					# RMW_WRITEWAIT state: write stage for RMW operation
					# transition: wait for ACK to end the cycle
					if ack_vector = 0:
						self.wbmstate_cur.next == self.wbmstate_t.wbm_rmw_wrwait
					else:
						# (TODO: change when err state available)
						self.wbmstate_cur.next = self.wbmstate_t.wbm_idle
						# check if ack or error
						#if len(ack_vector) > 1:
						#	# with ERR/RTY signal
						#	if ack_vector[1:] = 0:
						#		self.wbmstate_cur.next = self.wbmstate_t.wbm_idle
						#	else:
						#		# error in cycle (TODO)
						#		self.wbmstate_cur.next = self.wbmstate_t.wbm_idle
						#else:
						#	self.wbmstate_cur.next = self.wbmstate_t.wbm_idle
				else:
					self.wbmstate_cur.next == self.wbmstate_t.wbm_idle

		# state machine: signal management on bus
		@always_comb
		def wbmstate_sig():
			# CYC_O generation
			if (self.wbmstate_cur = self.wbmstate_t.wbm_idle):
				self.wbmsig.CYC_O.next = 0
			else:
				self.wbmsig.CYC_O.next = 1
			# STB_O generation
			if (self.wbmstate_cur = self.wbmstate_t.wbm_idle) or (self.wbmstate_cur = self.wbmstate_t.wbm_incycle) or (self.wbmstate_cur = self.wbmstate_t.wbm_rmw_midwait):
				self.wbmsig.STB_O.next = 0
			else:
				self.wbmsig.STB_O.next = 1
			# WE_O generation
			if (self.wbmstate_cur = self.wbmstate_t.wbm_write_wait) or (self.wbmstate_cur = self.wbmstate_t.wbm_rmw_wrwait):
				self.wbmsig.WE_O.next = 1
			else:
				self.wbmsig.WE_O.next = 0
			# LOCK_O generation (TODO)
			if self.wbmsig.LOCK_O != None:
				self.wbmsig.LOCK_O.next = 0
			
			
		# return: a generators tuple. the added signals exists as object attributes
		return (trigvectgen, ackvectgen, wbmstate_proc, wbmstate_sig)
	
	def gen_addrdec(self, baseaddr, addrlen=None, highaddr=None):
	"""
	Address decoder generation: this function generate an address decoder based on ADR_O.
	It creates a chip enable signal with its generator, and store in the ce_sets list
	Argument: 
	"""
		# check upper limits on arguments
		if baseaddr < 0 or baseaddr >= self.wbmsig.ADR_O.max:
			raise AttributeError("Argument baseaddr must lie between 0 and %s. Arg: %s" % (str(self.wbmsig.ADR_O.max-1),str(baseaddr)))
		if addrlen == None and highaddr == None:
			# follow python convention: higher byte is not included in the interval
			highaddr = baseaddr + 1
		elif highaddr == None:
			highaddr = baseaddr + addrlen
		if baseaddr >= highaddr:
			raise AttributeError("Incorrect decoder interval: [ %s , %s )" % (str(baseaddr),str(highaddr)))
		
		# ce_list structure: elements of: tuple of (ce_signal, baseaddr, highaddr)
		ce_sig = Signal(intbv(0)[1:])
		ce_elem = (ce_sig, baseaddr, highaddr)
		self.ce_list.append(ce_elem)

		# generator
		@always_comb
		def ce_gen():
			if self.wbmsig.ADR_O >= baseaddr and self.wbmsig.ADR_O < highaddr:
				ce_sig.next = 1
			else
				ce_sig.next = 0
					
		# return tuple: a CE signal and generator for that CE signal stored in self.ce_list
		return (ce_sig, ce_gen)

class wishbone_slave_generator():
"""
	Generator class for wishbone slave
	This class have functions that returns generators to manage the wishbone bus for
	different bus transfers types.
"""
	def __init__(self, slavesig):
		if isinstance(slavesig, wishbone_slave_sig):
			self.wbssig = slavesig
		else
			raise AttributeError("Argument slavesig  must be of type wishbone_slave_sig. Arg: %s" % str(slavesig))
		# prepare chip-enable signal list
		# ce_list structure: elements of: tuple of (ce_signal, baseaddr, highaddr)
		self.ce_list = []

	# all the functions defined here will be used as modules to be instantiated.
	def gen_wbs_stm(self, *operations):
	"""
		State machine generator for slave
		This function generate the state signal and generator for the state machine
		Basic operations: Single read/write, Block read/write
		Arguments:
		* operations: a list of optional supported operations for the state machine. 
		Example:
		mygen = wishbone_slave_generator(theslave)
		mygen.gen_wbs_stm("")
	"""
		# states definition
		self.wbsstate_t = enum("wbs_idle", "wbs_incycle", "wbs_read_wait", "wbs_write_wait")
		self.wbsstate_cur = Signal(self.wbsstate_t.wbs_idle)
		
		# flag answer signals
		self.flagbusy = Signal(intbv(0)[1:])
		self.flagerr = Signal(intbv(0)[1:])
		# throttle flag
		self.flagwait = Signal(intbv(0)[1:])
		
		# state machine: transitions
		@always(self.wbssig.CLK_I.posedge, self.wbssig.RST_I.negedge)
		def wbsstate_proc():
			if self.wbssig.RST_I = 1:
				self.wbsstate_cur.next = self.wbsstate_t.wbs_idle
			else:
				# state transitions
				if self.wbsstate_cur == self.wbsstate_t.wbs_idle:
					# IDLE state: this state represents no access in slave bus
					# transition: a CYC signal
					if self.wbssig.CYC_I = 0:
						self.wbsstate_cur.next = self.wbsstate_t.wbs_idle
					else:
						# new cycle
						if self.wbssig.STB_I = 0:
							self.wbsstate_cur.next = self.wbsstate_t.wbs_incycle
						else:
							if self.wbssig.WE_I = 0:
								self.wbsstate_cur.next = self.wbsstate_t.wbs_read_wait
							else:
								self.wbsstate_cur.next = self.wbsstate_t.wbs_write_wait
				elif self.wbmstate_cur == self.wbmstate_t.wbm_incycle:
					# INCYCLE state: this state represents a current cycle in progress
					# but inactive. CYC_I is asserted but STB_I is deasserted
					# transition: a STB_I signal
					if self.wbssig.CYC_I = 0:
						self.wbsstate_cur.next = self.wbsstate_t.wbs_idle
					else:
						if self.wbssig.STB_I = 0:
							self.wbsstate_cur.next = self.wbsstate_t.wbs_incycle
						else:
							if self.wbssig.WE_I = 0:
								self.wbsstate_cur.next = self.wbsstate_t.wbs_read_wait
							else:
								self.wbsstate_cur.next = self.wbsstate_t.wbs_write_wait
				# operations transitions
				elif self.wbmstate_cur == self.wbmstate_t.wbm_read_wait:
					# READWAIT state: read operation in the bus
					# transition: depends on waitstate flag
					if flagwait = 1:
						self.wbmstate_cur.next == self.wbmstate_t.wbm_read_wait
					else:
						if self.wbssig.CYC_I = 0:
							self.wbsstate_cur.next = self.wbsstate_t.wbs_idle
						else:
							if self.wbssig.STB_I = 0:
								self.wbsstate_cur.next = self.wbsstate_t.wbs_incycle
							else:
								if self.wbssig.WE_I = 0:
									self.wbsstate_cur.next = self.wbsstate_t.wbs_read_wait
								else:
									self.wbsstate_cur.next = self.wbsstate_t.wbs_write_wait
				elif self.wbmstate_cur == self.wbmstate_t.wbm_write_wait:
					# WRITEWAIT state: write operation in the bus
					# transition: depends on waitstate flag
					if flagwait = 1:
						self.wbmstate_cur.next == self.wbmstate_t.wbm_write_wait
					else:
						if self.wbssig.CYC_I = 0:
							self.wbsstate_cur.next = self.wbsstate_t.wbs_idle
						else:
							if self.wbssig.STB_I = 0:
								self.wbsstate_cur.next = self.wbsstate_t.wbs_incycle
							else:
								if self.wbssig.WE_I = 0:
									self.wbsstate_cur.next = self.wbsstate_t.wbs_read_wait
								else:
									self.wbsstate_cur.next = self.wbsstate_t.wbs_write_wait
				else:
					self.wbsstate_cur.next == self.wbsstate_t.wbs_idle

		# state machine: signal management on bus
		@always_comb
		def wbsstate_sig():
			# ack answers
			if (self.wbsstate_cur = self.wbsstate_t.wbs_idle):
				self.wbssig.CYC_O.next = 0
			else:
				self.wbmsig.CYC_O.next = 1
			# STB_O generation
			if (self.wbmstate_cur = self.wbmstate_t.wbm_idle) or (self.wbmstate_cur = self.wbmstate_t.wbm_incycle) or (self.wbmstate_cur = self.wbmstate_t.wbm_rmw_midwait):
				self.wbmsig.STB_O.next = 0
			else:
				self.wbmsig.STB_O.next = 1
			# WE_O generation
			if (self.wbmstate_cur = self.wbmstate_t.wbm_write_wait) or (self.wbmstate_cur = self.wbmstate_t.wbm_rmw_wrwait):
				self.wbmsig.WE_O.next = 1
			else:
				self.wbmsig.WE_O.next = 0
			# LOCK_O generation (TODO)
			if self.wbmsig.LOCK_O != None:
				self.wbmsig.LOCK_O.next = 0
			
			
		# return: a generators tuple. the added signals exists as object attributes
		return (trigvectgen, ackvectgen, wbmstate_proc, wbmstate_sig)