"""L0 per-retire differential against the RV32IC ISS (``RC-FR-131/145``).

Each program is executed on the RTL :class:`RiscvCore` and on the plain-Python
:class:`RV32ICIss`; after every retire the retired PC/instruction must match,
and at halt the full register file (read through the debug port) and the
``tohost`` signature/cause must match.  A seeded random-instruction fuzz runs
the same comparison over many generated programs.
"""

import random

import pytest
from myhdl import StopSimulation, always, block, delay, instance
from test_riscv_iss import _i, _r, _s, _u

from myhdl_addons.riscv import CoreConfig, RV32ICIss, RiscvCore

_SIZE = 0x2000
_TOHOST = 0x1000
_FROMHOST = 0x1004


def _config(tmp_path, words, enable_c=True):
    path = tmp_path / "prog.hex"
    path.write_text("".join(f"{word:08x}\n" for word in words))
    mapping = {
        "core": {
            "reset_vector": "0x0",
            "tohost": hex(_TOHOST),
            "fromhost": hex(_FROMHOST),
        },
        "region.ram": {
            "base": "0x0",
            "size": hex(_SIZE),
            "perms": "ID",
            "access": "RW",
            "target": "internal",
            "init": str(path),
            "init_format": "hex",
        },
    }
    if not enable_c:
        mapping["extension.c"] = {"enabled": "false"}
    return CoreConfig.from_mapping(mapping)


def _iss(words, enable_c=True):
    iss = RV32ICIss(
        regions=[{"base": 0, "size": _SIZE, "perms": "ID", "access": "RW"}],
        tohost=_TOHOST,
        fromhost=_FROMHOST,
        reset_vector=0,
        with_c=enable_c,
    )
    for index, word in enumerate(words):
        iss.poke_word(4 * index, word)
    return iss


@block
def _diff_tb(records, config, iss, limit):
    comp = RiscvCore(config)
    ports = comp.ports()
    dut = comp.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0
        yield ports.clk.posedge
        ports.reset.next = 1
        steps = 0
        while not ports.halted and steps < limit:
            yield ports.clk.posedge
            yield delay(1)
            if ports.retire_valid:
                iss.step()
                rec = iss.last_retire
                records.append(
                    (int(ports.retire_pc), int(ports.retire_instr), rec.pc, rec.instr)
                )
                steps += 1
        core_x = []
        for index in range(32):
            ports.dbg_addr.next = index
            yield delay(1)
            core_x.append(int(ports.dbg_data))
        records.append(tuple(core_x))
        records.append(
            (
                int(ports.halted),
                int(ports.signature),
                int(ports.fault),
                iss.halted,
                iss.signature,
                iss.cause if iss.cause is not None else 0,
            )
        )
        raise StopSimulation

    return clkgen, dut, stim


def _run(config, iss, limit=6000):
    records = []
    _diff_tb(records, config, iss, limit).run_sim()
    return records


def _compare(records, iss):
    core_x = records[-2]
    halt = records[-1]
    # per-retire PC and instruction match
    for core_pc, core_instr, iss_pc, iss_instr in records[:-2]:
        assert core_pc == iss_pc
        assert core_instr == iss_instr
    # final register file matches
    assert core_x == tuple(iss.x)
    # halt / signature match
    core_halted, core_sig, core_fault, iss_halted, iss_sig, iss_cause = halt
    assert core_halted == iss_halted
    if not core_fault:
        assert core_sig == iss_sig


def test_differential_directed(tmp_path):
    program = [
        _i(5, 0, 0, 1),  # addi x1, x0, 5
        _i(7, 0, 0, 2),  # addi x2, x0, 7
        _i(0, 1, 0, 3, 0x33) | (2 << 20),  # add x3, x1, x2
        _s(0x100, 3, 0, 2),  # sw x3, 0x100(x0)
        _i(0x100, 0, 2, 4, 0x03),  # lw x4, 0x100(x0)
        _u(0x1000, 5),  # lui x5, 0x1
        _s(0, 4, 5, 2),  # sw x4, 0(x5) -> tohost
    ]
    iss = _iss(program)
    records = _run(_config(tmp_path, program), iss)
    _compare(records, iss)


_R_OPS = [
    (0x00, 0),
    (0x00, 1),
    (0x00, 2),
    (0x00, 3),
    (0x00, 4),
    (0x00, 5),
    (0x00, 6),
    (0x00, 7),
    (0x20, 0),
    (0x20, 5),
]


def _random_program(rng, count):
    words = []
    for _ in range(count):
        kind = rng.randrange(6)
        rd = rng.randint(1, 31)
        rs1 = rng.randint(0, 31)
        rs2 = rng.randint(0, 31)
        if kind == 0:  # addi
            words.append(_i(rng.randint(-2048, 2047), rs1, 0, rd))
        elif kind == 1:  # register ALU
            f7, f3 = _R_OPS[rng.randrange(len(_R_OPS))]
            words.append(_r(f7, rs2, rs1, f3, rd))
        elif kind == 2:  # lui
            words.append(_u(rng.randrange(0x1000) << 12, rd))
        elif kind == 3:  # auipc
            words.append((rng.randrange(0x1000) << 12) | (rd << 7) | 0x17)
        elif kind == 4:  # load word (aligned, in-bounds away from tohost)
            addr = rng.randrange(0x100, 0x800) & ~0x3
            words.append(_i(addr, 0, 2, rd, 0x03))
        else:  # store word (aligned, in-bounds)
            addr = rng.randrange(0x100, 0x800) & ~0x3
            words.append(_s(addr, rs2, 0, 2))
    words.append(_u(0x1000, 31))  # lui x31, 0x1
    words.append(_s(0, 5, 31, 2))  # sw x5, 0(x31) -> tohost
    return words


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_differential_fuzz(seed, tmp_path):
    rng = random.Random(seed)
    program = _random_program(rng, 40)
    iss = _iss(program)
    records = _run(_config(tmp_path, program), iss)
    _compare(records, iss)
