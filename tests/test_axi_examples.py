"""Smoke tests for the AXI examples (AX-FR-121)."""

import importlib.util
import pathlib

_EXAMPLES = pathlib.Path(__file__).resolve().parent.parent / "examples"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _EXAMPLES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_example_axi_lite_csr():
    _load("axi_lite_csr").axi_lite_csr_demo().run_sim()


def test_example_axi_crossbar():
    _load("axi_crossbar").axi_crossbar_demo().run_sim()


def test_example_axi_stream_pipeline():
    _load("axi_stream_pipeline").axi_stream_pipeline_demo().run_sim()
