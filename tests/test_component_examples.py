"""Smoke tests for the component examples."""

import importlib.util
import pathlib

_EXAMPLES = pathlib.Path(__file__).resolve().parent.parent / "examples"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _EXAMPLES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_example_components_alu():
    _load("components_alu").alu_demo().run_sim()


def test_example_components_alu_convert(tmp_path):
    out = _load("components_alu").convert_demo(tmp_path)
    assert (out / "alu.v").exists()
    assert (out / "alu.vhd").exists()
