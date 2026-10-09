"""Non-pipelined RV32I core (``RiscvCore``, ``RC-FR-001/010/011/020..023``).

:class:`RiscvCore` wires the independent and RISC-V-specific blocks into a
single-issue, multi-cycle machine driven by a :class:`CoreConfig`:

* the :class:`FetchUnit` (instruction front-end) drives the router's fetch
  client; the core drives the router's data client;
* the :class:`InstructionDecoder`, ``ImmGen``, ``Alu``/``BarrelShifter``,
  ``BranchUnit`` and ``LoadStoreUnit`` form the datapath;
* the ``RegisterFile`` is a plain 32-entry bank (``x0`` is hard-wired in the
  core, ``RC-FR-021``);
* :class:`ToHost` intercepts ``tohost``/``fromhost`` accesses ahead of the
  router and provides the halt ``signature`` (``RC-FR-111/113``).

The machine is **multi-cycle** (``RC-FR-067``: one issue, one retire): a
``FETCH`` state captures one instruction from the fetch unit, an ``EXECUTE``
state computes the ALU/branch/jump result (register writes happen here for
non-loads), and a ``MEMORY`` state performs a load/store through the router
(one outstanding access, tolerating wait states) before writing back a loaded
value.  ``ECALL``/``EBREAK``/illegal encodings stop the core.
"""

from myhdl import Signal, always, always_comb, block, intbv

from ..common.config import ComponentBase
from ..common.reset import make_reset
from ..common.views import SignalView
from ..components import AVAIL_OPS, Alu, BarrelShifter, RegisterFile
from .branch import BranchUnit
from .decoder import InstructionDecoder
from .fetch import FetchUnit
from .immgen import ImmGen
from .iss import CAUSE
from .lsu import LoadStoreUnit
from .router import MemoryRouter
from .rvc import RvcDecompressor
from .sim import contents_from_config
from .tohost import ToHost

__all__ = ["RiscvCore"]

_FETCH, _EXEC, _MEMORY = 0, 1, 2
_OP_IMM = 0x13
_MASK = 0xFFFFFFFF

# RISC-V cause codes as plain ints (dict subscripts are not convertible).
_CAUSE_FETCH_MISALIGNED = CAUSE["instruction_misaligned"]
_CAUSE_ILLEGAL = CAUSE["illegal_instruction"]
_CAUSE_ECALL = CAUSE["ecall"]
_CAUSE_BREAKPOINT = CAUSE["breakpoint"]
_CAUSE_LOAD_MISALIGNED = CAUSE["load_misaligned"]
_CAUSE_STORE_MISALIGNED = CAUSE["store_misaligned"]
_CAUSE_LOAD_ACCESS = CAUSE["load_access"]
_CAUSE_STORE_ACCESS = CAUSE["store_access"]


class RiscvCore(ComponentBase):
    """Multi-cycle RV32I core assembled from the library blocks.

    Args:
        config: a :class:`CoreConfig` (regions, reset vector, ``tohost``/
            ``fromhost``, ``fetch_buffer``).
        reset_signal: reuse a specific ``ResetSignal`` (active-low default).
    """

    def __init__(self, config, reset_signal=None) -> None:
        self._config = config
        self._contents = contents_from_config(config)
        self._params = {
            "reset_vector": int(config.getint("core", "reset_vector", fallback=0)),
            "tohost": int(config.getint("core", "tohost", fallback=0x1000)),
            "fromhost": int(config.getint("core", "fromhost", fallback=0x1004)),
            "enable_c": "c" in config.extensions,
            "reset_signal": make_reset(reset_signal),
        }

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        return SignalView(
            clk=Signal(bool(0)),
            reset=self._params["reset_signal"],
            halted=Signal(bool(0)),
            signature=Signal(intbv(0)[32:]),
            fault=Signal(bool(0)),
            cause=Signal(intbv(0)[4:]),
            fromhost_data=Signal(intbv(0)[32:]),
            retire_valid=Signal(bool(0)),
            retire_pc=Signal(intbv(0)[32:]),
            retire_instr=Signal(intbv(0)[32:]),
            dbg_addr=Signal(intbv(0, min=0, max=32)),
            dbg_data=Signal(intbv(0)[32:]),
        )

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the core onto *ports* and return its instances."""
        cfg = self._config
        rv = self._params["reset_vector"]
        reset_sig = self._params["reset_signal"]
        active = int(reset_sig.active)
        fetch_buffer = cfg.getint("pipeline", "fetch_buffer", fallback=1)

        router = MemoryRouter(
            cfg.regions, contents=self._contents, reset_signal=reset_sig
        )
        rp = router.ports()
        rp.clk = ports.clk

        fetch = FetchUnit(
            fetch_buffer=fetch_buffer, reset_vector=rv, reset_signal=reset_sig
        )
        fp = fetch.ports()
        fp.clk = ports.clk

        decoder = InstructionDecoder()
        dp = decoder.ports()

        immgen = ImmGen()
        ip = immgen.ports()

        alu = Alu(width=32, ops=AVAIL_OPS, flags=())
        ap = alu.ports()

        shifter = BarrelShifter(width=32)
        sp = shifter.ports()

        regfile = RegisterFile(
            width=32,
            depth=32,
            read_ports=3,
            write_ports=1,
            read_latency=0,
            zero_reg_fix_value=None,
            reset_signal=reset_sig,
        )
        rf = regfile.ports()
        rf.clk = ports.clk

        branch = BranchUnit(width=32)
        bp = branch.ports()

        lsu = LoadStoreUnit(width=32)
        lp = lsu.ports()

        tohost = ToHost(
            tohost_addr=self._params["tohost"],
            fromhost_addr=self._params["fromhost"],
            reset_signal=reset_sig,
        )
        tp = tohost.ports()
        tp.clk = ports.clk

        enable_c = self._params["enable_c"]
        state = Signal(intbv(0, min=0, max=3))
        instr = Signal(intbv(0)[32:])
        dec_instr = Signal(intbv(0)[32:])
        cur_compressed = Signal(bool(0))
        cur_step = Signal(intbv(4, min=2, max=5))
        c_illegal = Signal(bool(0))
        pc_cur = Signal(intbv(rv)[32:])
        stopped = Signal(bool(0))
        take = Signal(bool(0))
        flush = Signal(bool(0))
        flush_target = Signal(intbv(0)[32:])
        rf_we = Signal(bool(0))
        rf_waddr = Signal(intbv(0, min=0, max=32))
        rf_wdata = Signal(intbv(0)[32:])
        wb_x = Signal(intbv(0)[32:])
        mem_we = Signal(bool(0))
        mem_addr = Signal(intbv(0)[32:])
        store_data = Signal(intbv(0)[32:])

        c_procs = []
        if enable_c:
            decomp = RvcDecompressor()
            cp = decomp.ports()

            @always_comb
            def wire_decomp():
                cp.instr_i.next = instr[16:]
                if cur_compressed:
                    dec_instr.next = cp.instr_o
                    c_illegal.next = cp.illegal
                else:
                    dec_instr.next = instr
                    c_illegal.next = 0

            c_procs = [decomp.hdl(cp), wire_decomp]
        else:

            @always_comb
            def wire_no_decomp():
                dec_instr.next = instr
                c_illegal.next = 0

            c_procs = [wire_no_decomp]

        @always_comb
        def step_calc():
            if cur_compressed:
                cur_step.next = 2
            else:
                cur_step.next = 4

        @always_comb
        def wire_fetch():
            rp.f_req_valid.next = fp.mem_req_valid
            rp.f_req_addr.next = fp.mem_req_addr
            fp.mem_resp_valid.next = rp.f_resp_valid
            fp.mem_resp_rdata.next = rp.f_resp_rdata
            fp.mem_resp_error.next = rp.f_resp_error
            fp.take.next = take
            fp.flush.next = flush
            fp.req_pc.next = flush_target

        @always_comb
        def wire_decode():
            dp.instr.next = dec_instr
            ip.instr.next = dec_instr
            ip.imm_sel.next = dp.imm_sel
            rf.raddr0.next = dp.rs1
            rf.raddr1.next = dp.rs2
            rf.raddr2.next = ports.dbg_addr
            rf.we0.next = rf_we
            rf.waddr0.next = rf_waddr
            rf.wdata0.next = rf_wdata

        @always_comb
        def dbg_read():
            # x0 reads zero; index 0 remains ordinary storage in the bank.
            if ports.dbg_addr == 0:
                ports.dbg_data.next = 0
            else:
                ports.dbg_data.next = rf.rdata2

        @always_comb
        def alu_a_mux():
            if dp.alu_a_pc:
                ap.a.next = pc_cur
            else:
                ap.a.next = rf.rdata0

        @always_comb
        def alu_b_mux():
            ap.op.next = dp.alu_op
            if dp.alu_b_imm:
                ap.b.next = ip.imm
            else:
                ap.b.next = rf.rdata1

        @always_comb
        def shift_wire():
            sp.data.next = rf.rdata0
            sp.mode.next = dp.shift_mode
            if (instr & 0x7F) == _OP_IMM:
                sp.shamt.next = ip.imm[5:]
            else:
                sp.shamt.next = rf.rdata1[5:]

        @always_comb
        def branch_wire():
            bp.a.next = rf.rdata0
            bp.b.next = rf.rdata1
            bp.op.next = dp.branch_op

        @always_comb
        def wb_value():
            if dp.jump:
                wb_x.next = (pc_cur + cur_step) & _MASK
            elif dp.shift:
                wb_x.next = sp.y
            else:
                wb_x.next = ap.y

        @always_comb
        def mem_addr_calc():
            mem_addr.next = (rf.rdata0 + ip.imm) & _MASK

        @always_comb
        def store_data_calc():
            store_data.next = rf.rdata1

        @always_comb
        def tohost_wire():
            tp.addr.next = mem_addr
            tp.wdata.next = store_data
            tp.fromhost_data.next = ports.fromhost_data
            tp.store.next = (state == _EXEC) and dp.mem_write
            tp.load.next = (state == _EXEC) and dp.mem_read

        @always_comb
        def lsu_wire():
            lp.addr.next = mem_addr
            lp.wdata.next = store_data
            lp.rdata.next = rp.d_resp_rdata
            lp.size.next = dp.mem_size
            lp.zero_extend.next = dp.mem_unsigned

        @always_comb
        def router_data():
            rp.d_req_valid.next = (state == _MEMORY) and (not stopped)
            rp.d_req_addr.next = mem_addr
            rp.d_req_we.next = mem_we
            rp.d_req_wdata.next = lp.store_data
            rp.d_req_wstrb.next = lp.wstrb

        @always_comb
        def writeback():
            rf_we.next = 0
            rf_waddr.next = dp.rd
            rf_wdata.next = wb_x
            if state == _EXEC:
                if tp.hit and dp.mem_read:
                    rf_we.next = 1
                    rf_wdata.next = tp.rdata
                elif (not dp.mem_read) and (not dp.mem_write):
                    if (dp.reg_write or dp.jump) and (dp.rd != 0):
                        rf_we.next = 1
            elif state == _MEMORY:
                if rp.d_resp_valid and dp.mem_read:
                    rf_we.next = 1
                    rf_wdata.next = lp.load_data

        @always_comb
        def redirect():
            taken = (state == _EXEC) and ((dp.branch and bp.take) or dp.jump)
            flush.next = taken
            if dp.jalr:
                flush_target.next = (rf.rdata0 + ip.imm) & 0xFFFFFFFE
            else:
                flush_target.next = (pc_cur + ip.imm) & _MASK

        @always_comb
        def take_calc():
            take.next = (
                (state == _FETCH)
                and fp.instr_valid
                and (not stopped)
                and (not fp.misaligned)
            )

        @always(ports.clk.posedge)
        def sequencer():
            if ports.reset == active:
                state.next = _FETCH
                instr.next = 0
                cur_compressed.next = 0
                pc_cur.next = rv
                stopped.next = 0
                mem_we.next = 0
                ports.halted.next = 0
                ports.signature.next = 0
                ports.fault.next = 0
                ports.cause.next = 0
                ports.retire_valid.next = 0
            else:
                ports.retire_valid.next = 0
                if tp.halt:
                    stopped.next = 1
                    ports.halted.next = 1
                    ports.signature.next = tp.signature
                    ports.fault.next = 0
                    ports.cause.next = 0
                elif stopped:
                    ports.halted.next = 1
                elif state == _FETCH:
                    if fp.misaligned:
                        stopped.next = 1
                        ports.halted.next = 1
                        ports.fault.next = 1
                        ports.cause.next = _CAUSE_FETCH_MISALIGNED
                        ports.signature.next = _CAUSE_FETCH_MISALIGNED
                    elif fp.instr_valid:
                        instr.next = fp.instr_data
                        cur_compressed.next = fp.instr_compressed
                        pc_cur.next = fp.instr_pc
                        state.next = _EXEC
                elif state == _EXEC:
                    if dp.illegal or c_illegal:
                        stopped.next = 1
                        ports.halted.next = 1
                        ports.fault.next = 1
                        ports.cause.next = _CAUSE_ILLEGAL
                        ports.signature.next = _CAUSE_ILLEGAL
                    elif dp.ecall:
                        stopped.next = 1
                        ports.halted.next = 1
                        ports.fault.next = 1
                        ports.cause.next = _CAUSE_ECALL
                        ports.signature.next = _CAUSE_ECALL
                    elif dp.ebreak:
                        stopped.next = 1
                        ports.halted.next = 1
                        ports.fault.next = 1
                        ports.cause.next = _CAUSE_BREAKPOINT
                        ports.signature.next = _CAUSE_BREAKPOINT
                    elif dp.fence:
                        state.next = _FETCH  # FENCE / FENCE.I: no-op
                        ports.retire_valid.next = 1
                        ports.retire_pc.next = pc_cur
                        ports.retire_instr.next = dec_instr
                    elif (dp.mem_read or dp.mem_write) and lp.misaligned:
                        stopped.next = 1
                        ports.halted.next = 1
                        ports.fault.next = 1
                        if dp.mem_read:
                            ports.cause.next = _CAUSE_LOAD_MISALIGNED
                            ports.signature.next = _CAUSE_LOAD_MISALIGNED
                        else:
                            ports.cause.next = _CAUSE_STORE_MISALIGNED
                            ports.signature.next = _CAUSE_STORE_MISALIGNED
                    elif (dp.mem_read or dp.mem_write) and not tp.hit:
                        mem_we.next = dp.mem_write
                        state.next = _MEMORY
                    else:
                        state.next = _FETCH
                        ports.retire_valid.next = 1
                        ports.retire_pc.next = pc_cur
                        ports.retire_instr.next = dec_instr
                else:
                    if rp.d_resp_error:
                        stopped.next = 1
                        ports.halted.next = 1
                        ports.fault.next = 1
                        if dp.mem_read:
                            ports.cause.next = _CAUSE_LOAD_ACCESS
                            ports.signature.next = _CAUSE_LOAD_ACCESS
                        else:
                            ports.cause.next = _CAUSE_STORE_ACCESS
                            ports.signature.next = _CAUSE_STORE_ACCESS
                    elif rp.d_resp_valid:
                        mem_we.next = 0
                        state.next = _FETCH
                        ports.retire_valid.next = 1
                        ports.retire_pc.next = pc_cur
                        ports.retire_instr.next = dec_instr

        return [
            router.hdl(rp),
            fetch.hdl(fp),
            decoder.hdl(dp),
            immgen.hdl(ip),
            alu.hdl(ap),
            shifter.hdl(sp),
            regfile.hdl(rf),
            branch.hdl(bp),
            lsu.hdl(lp),
            tohost.hdl(tp),
            *c_procs,
            step_calc,
            wire_fetch,
            wire_decode,
            alu_a_mux,
            alu_b_mux,
            shift_wire,
            branch_wire,
            wb_value,
            mem_addr_calc,
            store_data_calc,
            tohost_wire,
            lsu_wire,
            router_data,
            writeback,
            redirect,
            take_calc,
            sequencer,
        ]
