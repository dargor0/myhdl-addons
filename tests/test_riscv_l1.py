"""L1 ``riscv-tests`` runner and example ISA test (``RC-FR-140/146/152``).

The example (``config/riscv_tests.ini`` + ``share/riscv_isa_test.hex``) always
runs: it exercises RV32I operations and writes pass to ``tohost``.  The
``rv32ui``/``rv32uc`` suite runs when its prebuilt ELFs are present (set
``RISCV_TESTS_DIR`` or drop them in ``riscv-tests/``); it otherwise skips
(``RC-NFR-009``).
"""

import os
from pathlib import Path

import pytest
from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.riscv import (
    CoreConfig,
    MemoryImage,
    RiscvCore,
    SignatureChecker,
    elf_symbols,
)

_ROOT = Path(__file__).resolve().parents[1]


@block
def _core_tb(result, config, limit):
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
        guard = 0
        while not ports.halted and guard < limit:
            yield ports.clk.posedge
            guard += 1
        result.append(
            (
                int(ports.halted),
                int(ports.signature),
                int(ports.fault),
                int(ports.cause),
            )
        )
        raise StopSimulation

    return clkgen, dut, stim


def _run(config, limit=400000):
    result = []
    _core_tb(result, config, limit).run_sim()
    return result[0]


def _check(config, tohost, limit=400000):
    halted, signature, fault, cause = _run(config, limit)
    checker = SignatureChecker(tohost)
    checker.feed(signature)
    assert halted == 1
    assert not fault, cause
    assert checker.passed, signature


def test_l1_example_isa_test():
    config = CoreConfig.from_ini(str(_ROOT / "config" / "riscv_tests.ini"))
    _check(config, config.getint("core", "tohost"))


def _tests_dir():
    env = os.environ.get("RISCV_TESTS_DIR")
    if env and Path(env).is_dir():
        return Path(env)
    local = _ROOT / "riscv-tests"
    if local.is_dir():
        return local
    return None


def _elf_config(elf_path):
    image = MemoryImage.from_elf(elf_path)
    symbols = elf_symbols(elf_path)
    low = min(addr for addr, _ in image.segments)
    high = max(addr + len(data) for addr, data in image.segments)
    tohost = symbols.get("tohost", high)
    fromhost = symbols.get("fromhost", tohost + 4)
    # the intercepted tohost/fromhost need not be inside a loaded segment
    high = max(high, tohost + 8, fromhost + 4)
    size = 4
    while size < high - low:
        size <<= 1
    base = low & ~(size - 1)
    config = CoreConfig.from_mapping(
        {
            "core": {
                "reset_vector": hex(image.entry),
                "tohost": hex(tohost),
                "fromhost": hex(fromhost),
            },
            "region.ram": {
                "base": hex(base),
                "size": hex(size),
                "perms": "ID",
                "access": "RW",
                "target": "internal",
                "init": str(elf_path),
                "init_format": "elf",
            },
        }
    )
    return config, tohost


def test_l1_riscv_tests():
    tests_dir = _tests_dir()
    if tests_dir is None:
        pytest.skip("riscv-tests binaries not present (set RISCV_TESTS_DIR)")
    elfs = sorted(tests_dir.glob("rv32u[ic]-p-*"))
    if not elfs:
        pytest.skip("no rv32ui/rv32uc ELFs found")
    for elf in elfs:
        config, tohost = _elf_config(elf)
        _check(config, tohost)
