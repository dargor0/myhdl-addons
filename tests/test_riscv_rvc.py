"""RVC decompressor behaviour (``RC-FR-040/042/044/047``)."""

from myhdl import StopSimulation, block, delay, instance

from myhdl_addons.riscv.rvc import RvcDecompressor, decompress


@block
def _exhaustive(results):
    comp = RvcDecompressor()
    ports = comp.ports()
    dut = comp.hdl(ports)

    @instance
    def stim():
        # prime the combinational process (it is sensitive to instr_i changes)
        ports.instr_i.next = 0xFFFF
        yield delay(1)
        for instr in range(1 << 16):
            ports.instr_i.next = instr
            yield delay(1)
            results.append((int(ports.instr_o), int(ports.illegal)))
        raise StopSimulation

    return dut, stim


def test_reference_directed():
    assert decompress(0x0001) == (0x00000013, False)  # c.nop
    assert decompress(0x0085) == (0x00108093, False)  # c.addi x1, 1
    assert decompress(0x50FD) == (0xFFF00093, False)  # c.li x1, -1
    assert decompress(0x8082) == (0x00008067, False)  # c.jr x1
    assert decompress(0x9002) == (0x00100073, False)  # c.ebreak
    assert decompress(0xA001) == (0x0000006F, False)  # c.j 0
    assert decompress(0xB001) == (0x801FF06F, False)  # c.j with bit 12 sign set
    assert decompress(0x2001) == (0x000000EF, False)  # c.jal 0
    assert decompress(0x3001) == (0x801FF0EF, False)  # c.jal with bit 12 sign set
    assert decompress(0x0000) == (0, True)  # c.addi4spn with nzuimm == 0
    assert decompress(0x0003) == (0, True)  # op == 0b11 (not compressed)
    assert decompress(0x9C01) == (0, True)  # c.sub family with inst[12] == 1


def test_reference_is_total():
    for instr in range(1 << 16):
        word, illegal = decompress(instr)
        assert 0 <= word < (1 << 32)
        assert isinstance(illegal, bool)


def test_decompressor_matches_reference_exhaustively():
    results = []
    _exhaustive(results).run_sim()
    assert len(results) == (1 << 16)
    for instr, (word, illegal) in enumerate(results):
        assert (word, bool(illegal)) == decompress(instr), f"instr={instr:#06x}"
