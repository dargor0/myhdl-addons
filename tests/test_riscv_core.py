"""``RiscvCore`` multi-cycle RV32I programs (``RC-FR-020`` etc.).

Small programs are assembled, loaded into an internal region and run until the
``tohost`` store halts the core; the signature is checked.
"""

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.riscv import CoreConfig, RiscvCore


def _i(imm, rs1, f3, rd, op=0x13):
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op


def _s(imm, rs2, rs1, f3):
    imm &= 0xFFF
    return (
        ((imm >> 5) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (f3 << 12)
        | ((imm & 0x1F) << 7)
        | 0x23
    )


def _b(imm, rs2, rs1, f3):
    imm &= 0x1FFF
    return (
        (((imm >> 12) & 1) << 31)
        | (((imm >> 5) & 0x3F) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (f3 << 12)
        | (((imm >> 1) & 0xF) << 8)
        | (((imm >> 11) & 1) << 7)
        | 0x63
    )


def _u(imm, rd):
    return (imm & 0xFFFFF000) | (rd << 7) | 0x37


def _j(imm, rd):
    imm &= 0x1FFFFF
    return (
        (((imm >> 20) & 1) << 31)
        | (((imm >> 1) & 0x3FF) << 21)
        | (((imm >> 11) & 1) << 20)
        | (((imm >> 12) & 0xFF) << 12)
        | (rd << 7)
        | 0x6F
    )


def _config(tmp_path, program, size=0x2000, tohost=0x1000, enable_c=True):
    path = tmp_path / "prog.hex"
    path.write_text("".join(f"{word:08x}\n" for word in program))
    mapping = {
        "core": {
            "reset_vector": "0x0",
            "tohost": hex(tohost),
            "fromhost": hex(tohost + 4),
        },
        "region.ram": {
            "base": "0x0",
            "size": hex(size),
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


@block
def _python_device(comp, ports):
    return comp.hdl(ports)


@block
def _core_tb(make_device, results, config, limit):
    comp = RiscvCore(config)
    ports = comp.ports()
    dut = make_device(comp, ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0
        yield ports.clk.posedge
        ports.reset.next = 1
        guard = 0
        while not ports.halted and guard < limit:
            yield ports.clk.posedge
            guard += 1
        results.append(
            (
                int(ports.halted),
                int(ports.signature),
                int(ports.fault),
                int(ports.cause),
            )
        )
        raise StopSimulation

    return clkgen, dut, stim


def _run(config, limit=3000, make_device=_python_device):
    results = []
    _core_tb(make_device, results, config, limit).run_sim()
    return results


def test_core_add_to_tohost(tmp_path):
    program = [
        _i(5, 0, 0, 1),  # addi x1, x0, 5
        _i(7, 0, 0, 2),  # addi x2, x0, 7
        _i(0, 1, 0, 3, 0x33) | (2 << 20),  # add x3, x1, x2
        _u(0x1000, 4),  # lui x4, 0x1
        _s(0, 3, 4, 2),  # sw x3, 0(x4)
    ]
    assert _run(_config(tmp_path, program)) == [(1, 12, 0, 0)]


def test_core_load_store_to_tohost(tmp_path):
    program = [
        _i(0x100, 0, 0, 1),  # addi x1, x0, 0x100
        _i(42, 0, 0, 2),  # addi x2, x0, 42
        _s(0, 2, 1, 2),  # sw x2, 0(x1)
        _i(0, 1, 2, 3, 0x03),  # lw x3, 0(x1)
        _u(0x1000, 5),  # lui x5, 0x1
        _s(0, 3, 5, 2),  # sw x3, 0(x5)
    ]
    assert _run(_config(tmp_path, program)) == [(1, 42, 0, 0)]


def test_core_branch_to_tohost(tmp_path):
    program = [
        _i(0, 0, 0, 1),  # addi x1, x0, 0
        _i(1, 0, 0, 2),  # addi x2, x0, 1
        _b(8, 2, 1, 0),  # beq x1, x2, +8 (not taken)
        _i(5, 0, 0, 3),  # addi x3, x0, 5
        _b(8, 1, 1, 0),  # beq x1, x1, +8 (taken)
        _i(9, 0, 0, 4),  # addi x4, x0, 9 (skipped)
        _u(0x1000, 5),  # lui x5, 0x1
        _s(0, 3, 5, 2),  # sw x3, 0(x5)
    ]
    assert _run(_config(tmp_path, program)) == [(1, 5, 0, 0)]


def test_core_jal_to_tohost(tmp_path):
    program = [
        _j(8, 1),  # jal x1, +8
        _i(0xBAD, 0, 0, 2),  # skipped
        _i(3, 0, 0, 3),  # addi x3, x0, 3
        _u(0x1000, 5),  # lui x5, 0x1
        _s(0, 3, 5, 2),  # sw x3, 0(x5)
    ]
    assert _run(_config(tmp_path, program)) == [(1, 3, 0, 0)]


def _c_li(rd, imm):
    return 0x4000 | ((imm & 0x20) << 7) | (rd << 7) | ((imm & 0x1F) << 2) | 0x01


def test_core_compressed_to_tohost(tmp_path):
    # c.li x1, 5 ; c.li x2, 7 packed into word 0 (two 16-bit parcels)
    word0 = _c_li(1, 5) | (_c_li(2, 7) << 16)
    program = [
        word0,
        _i(0, 1, 0, 3, 0x33) | (2 << 20),  # add x3, x1, x2
        _u(0x1000, 5),  # lui x5, 0x1
        _s(0, 3, 5, 2),  # sw x3, 0(x5)
    ]
    assert _run(_config(tmp_path, program)) == [(1, 12, 0, 0)]


def test_core_compressed_disabled_stops(tmp_path):
    program = [
        _c_li(3, 21) | (_i(0, 0, 0, 0) << 16),  # compressed when C is off
        _u(0x1000, 5),
        _s(0, 3, 5, 2),
    ]
    # with C disabled the 16-bit parcel is illegal -> fault cause 2
    assert _run(_config(tmp_path, program, enable_c=False)) == [(1, 2, 1, 2)]


def test_core_illegal_instruction(tmp_path):
    assert _run(_config(tmp_path, [0x00000000])) == [(1, 2, 1, 2)]


def test_core_ecall_and_ebreak(tmp_path):
    assert _run(_config(tmp_path, [0x00000073])) == [(1, 11, 1, 11)]
    assert _run(_config(tmp_path, [0x00100073])) == [(1, 3, 1, 3)]


def test_core_misaligned_load_store(tmp_path):
    load = [_i(2, 0, 0, 1), _i(0, 1, 2, 2, 0x03)]  # lw from addr 2
    assert _run(_config(tmp_path, load)) == [(1, 4, 1, 4)]
    store = [_i(1, 0, 0, 1), _s(0, 2, 1, 2)]  # sw to addr 1
    assert _run(_config(tmp_path, store)) == [(1, 6, 1, 6)]


def test_core_access_faults(tmp_path):
    load = [_u(0x4000, 1), _i(0, 1, 2, 2, 0x03)]  # lw from unmapped 0x4000
    assert _run(_config(tmp_path, load)) == [(1, 5, 1, 5)]
    store = [_u(0x4000, 1), _s(0, 2, 1, 2)]  # sw to unmapped 0x4000
    assert _run(_config(tmp_path, store)) == [(1, 7, 1, 7)]
