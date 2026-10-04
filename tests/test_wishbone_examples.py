"""Smoke tests for the Wishbone examples (WB-FR-120)."""

import importlib.util
import pathlib

_EXAMPLES = pathlib.Path(__file__).resolve().parent.parent / "examples"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _EXAMPLES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_example_wishbone_p2p_csr():
    _load("wishbone_p2p_csr").p2p_demo().run_sim()
