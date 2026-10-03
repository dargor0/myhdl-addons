"""Independence of the component library (``IC-FR-006``, ``IC-NFR-008``)."""

import ast
import importlib
import inspect
import pkgutil

import myhdl_addons.components as pkg

_FORBIDDEN = (
    "myhdl_addons.riscv",
    "myhdl_addons.wishbone",
    "myhdl_addons.axi",
    "myhdl_addons.bus_common",
)

_ALLOWED_ROOTS = {
    "myhdl",
    "myhdl_addons",
    "typing",
    "collections",
    "__future__",
    "abc",
    "dataclasses",
    "math",
    "copy",
}


def _modules():
    for info in pkgutil.iter_modules(pkg.__path__):
        yield importlib.import_module(f"myhdl_addons.components.{info.name}")


def _imports(module):
    tree = ast.parse(inspect.getsource(module))
    absolute = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            absolute.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            absolute.add(node.module)
    return absolute


def test_no_forbidden_cross_dependencies():
    for module in _modules():
        for name in _imports(module):
            assert not name.startswith(_FORBIDDEN), (module.__name__, name)


def test_dependencies_are_stdlib_or_myhdl():
    for module in _modules():
        for name in _imports(module):
            root = name.split(".")[0]
            assert root in _ALLOWED_ROOTS, (module.__name__, name)
