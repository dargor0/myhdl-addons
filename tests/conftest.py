"""Shared pytest fixtures and HDL toolchain helpers for the test-suite.

The helpers build, for an elaborated ``@block``:

* a converted Verilog module, a thin Verilog wrapper exposing its ports to
  MyHDL via ``$from_myhdl`` / ``$to_myhdl``, and a ``Cosimulation`` bound to
  the component's ``SignalView`` (Option A: the same Python testbench drives
  either the Python block or the converted RTL); and
* a Yosys ``synth`` run used as a technology-independent synthesizability
  smoke test.

The external tools (``iverilog``/``vvp`` plus a C compiler for cosim, ``yosys``
for synthesis) are optional: the fixtures below skip those checks when a tool
is absent, per the maintainer's instruction that the full run happens in a
reference environment that provides them.
"""

import os
import re
import shutil
import site
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(__file__))


class CosimUnavailable(RuntimeError):
    """Raised when the HDL toolchain required for a check is not available."""


_MODULE_RE = re.compile(r"^\s*module\s+(\w+)\s*\(([^)]*)\)", re.MULTILINE | re.DOTALL)
_PORT_RE = re.compile(
    r"^\s*(input|output|inout)\s+(signed\s+)?(\[[^\]]*\]\s+)?(\w+)\s*;",
    re.MULTILINE,
)


def convert_verilog(dut, path, name, initial_values=False):
    """Convert an elaborated block to Verilog and return the ``.v`` path.

    ``initial_values`` selects whether the converted Verilog emits signal/memory
    power-on values (MyHDL writes them for read-only memories regardless).  It
    is passed explicitly so the converter's global setting never leaks between
    calls.
    """
    out = Path(path) / f"{name}.v"
    dut.convert(
        hdl="Verilog",
        path=str(path),
        name=name,
        testbench=False,
        initial_values=initial_values,
    )
    if not out.exists():
        raise CosimUnavailable(f"conversion did not produce {out}")
    return out


def parse_module(v_path):
    """Return ``(module_name, ports)`` parsed from a converted Verilog file.

    Each port is a dict with ``name``, ``direction`` and ``decl`` (the
    ``[msb:lsb]`` range and any ``signed`` keyword, or an empty string).
    """
    text = Path(v_path).read_text()
    match = _MODULE_RE.search(text)
    if not match:
        raise CosimUnavailable(f"no module declaration found in {v_path}")
    # only names listed in the module header are ports; this avoids picking up
    # the `input`/`output` declarations that appear inside generated functions
    order = [name.strip() for name in match.group(2).split(",") if name.strip()]
    wanted = set(order)
    decls = {}
    for item in _PORT_RE.finditer(text):
        direction, sign, rng, name = item.groups()
        if name in wanted:
            decl = f"{sign or ''}{rng or ''}".strip()
            decls[name] = {"name": name, "direction": direction, "decl": decl}
    ports = [decls[name] for name in order if name in decls]
    return match.group(1), ports


def write_wrapper(w_path, module_name, ports):
    """Write a Verilog testbench that binds ``ports`` to MyHDL."""
    decls = []
    conns = []
    to_myhdl = []
    from_myhdl = []
    for port in ports:
        kind = "reg" if port["direction"] == "input" else "wire"
        decl = f" {port['decl']}" if port["decl"] else ""
        decls.append(f"    {kind}{decl} {port['name']};")
        conns.append(f"        .{port['name']}({port['name']})")
        if port["direction"] == "input":
            from_myhdl.append(port["name"])
        else:
            to_myhdl.append(port["name"])

    lines = ["module tb;", "", *decls, ""]
    lines.append(f"    {module_name} dut (")
    lines.append(",\n".join(conns))
    lines.append("    );")
    lines.append("")
    lines.append("    initial begin")
    if from_myhdl:
        lines.append("        $from_myhdl({});".format(", ".join(from_myhdl)))
    if to_myhdl:
        lines.append("        $to_myhdl({});".format(", ".join(to_myhdl)))
    lines.append("    end")
    lines.append("")
    lines.append("endmodule")
    Path(w_path).write_text("\n".join(lines) + "\n")


def _require(*tools):
    missing = [tool for tool in tools if shutil.which(tool) is None]
    if missing:
        raise CosimUnavailable("missing tool(s): " + ", ".join(missing))


def _find_myhdl_cosim_sources():
    env = os.environ.get("MYHDL_COSIM_DIR")
    if env and (Path(env) / "myhdl.c").exists():
        return Path(env)

    import myhdl

    pkg = Path(myhdl.__file__).resolve().parent
    roots = [Path(sys.prefix), Path(getattr(sys, "base_prefix", sys.prefix))]
    user_base = getattr(site, "USER_BASE", None)
    if user_base:
        roots.append(Path(user_base))
    roots.extend(pkg.parents[:5])
    roots.append(Path("/usr"))

    rel = ("share", "myhdl", "cosimulation", "icarus")
    for root in roots:
        candidate = root.joinpath(*rel)
        if (candidate / "myhdl.c").exists():
            return candidate
    raise CosimUnavailable("myhdl cosimulation sources (myhdl.c) not found")


def _port_key(view, converted):
    """Map a converted module port name back to its ``SignalView`` member.

    MyHDL flattens an interface argument ``ports`` into ``<argname>_<member>``
    (e.g. ``ports_a``), so the member is the longest suffix match.
    """
    names = list(view.names)
    if converted in names:
        return converted
    matches = [name for name in names if converted.endswith("_" + name)]
    if not matches:
        raise CosimUnavailable(
            f"cannot map module port {converted!r} to a port-view member"
        )
    return max(matches, key=len)


def _cc():
    return os.environ.get("CC", "cc")


def _iverilog_include():
    """Locate the directory holding ``vpi_user.h`` for the active Icarus."""
    env = os.environ.get("IVERILOG_INCLUDE")
    if env and (Path(env) / "vpi_user.h").exists():
        return env

    vpi_tool = shutil.which("iverilog-vpi")
    if vpi_tool:
        try:
            out = subprocess.run([vpi_tool, "--cflags"], capture_output=True, text=True)
        except OSError:
            out = None
        if out is not None and out.returncode == 0:
            for token in f"{out.stdout} {out.stderr}".split():
                if token.startswith("-I") and (Path(token[2:]) / "vpi_user.h").exists():
                    return token[2:]

    candidates = []
    iverilog = shutil.which("iverilog")
    if iverilog:
        prefix = Path(iverilog).resolve().parent.parent
        candidates += [prefix / "include" / "iverilog", prefix / "include"]
    candidates += [
        Path("/usr/include/iverilog"),
        Path("/usr/local/include/iverilog"),
        Path("/usr/include"),
        Path("/usr/local/include"),
    ]
    for candidate in candidates:
        if (candidate / "vpi_user.h").exists():
            return str(candidate)
    return None


def build_vpi(build_dir):
    """Compile the MyHDL Icarus VPI module and return its path.

    Compiled directly with the C compiler (``cc -fPIC -shared``) rather than
    through ``iverilog-vpi``, which on some distributions mangles its compiler
    arguments.
    """
    cc = _cc()
    _require(cc)
    include = _iverilog_include()
    if include is None:
        raise CosimUnavailable("cannot locate Icarus vpi_user.h (set IVERILOG_INCLUDE)")
    sources = _find_myhdl_cosim_sources()
    build_dir = Path(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    for name in ("myhdl.c", "myhdl_table.c"):
        shutil.copy(sources / name, build_dir / name)
    vpi = build_dir / "myhdl.vpi"
    result = subprocess.run(
        [
            cc,
            "-fPIC",
            "-shared",
            "-o",
            str(vpi),
            f"-I{include}",
            "myhdl.c",
            "myhdl_table.c",
        ],
        cwd=build_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not vpi.exists():
        # a build failure is a real problem, not a missing tool: surface it
        raise RuntimeError(f"myhdl.vpi build failed:\n{result.stdout}\n{result.stderr}")
    return vpi


def make_cosim(dut, ports, path, name, vpi, initial_values=False):
    """Convert ``dut`` and return a ``Cosimulation`` bound to ``ports``."""
    _require("iverilog", "vvp")
    path = Path(path)
    dut_v = convert_verilog(dut, path, name, initial_values=initial_values)
    module_name, parsed = parse_module(dut_v)
    tb_v = path / f"tb_{name}.v"
    write_wrapper(tb_v, module_name, parsed)
    obj = path / f"tb_{name}.o"
    compile_result = subprocess.run(
        ["iverilog", "-o", str(obj), "-s", "tb", str(tb_v), str(dut_v)],
        capture_output=True,
        text=True,
    )
    if compile_result.returncode != 0:
        raise RuntimeError(
            "iverilog failed:\n"
            f"{compile_result.stdout}\n{compile_result.stderr}\n"
            f"--- {tb_v} ---\n{tb_v.read_text()}\n"
            f"--- {dut_v} ---\n{dut_v.read_text()}"
        )
    from myhdl import Cosimulation

    portmap = {port["name"]: ports[_port_key(ports, port["name"])] for port in parsed}
    return Cosimulation(f"vvp -m {vpi} {obj}", **portmap)


def snippet(v_path, output, context=8):
    """Append the generated-Verilog lines around a Yosys error to *output*."""
    match = re.search(r"(\S+\.v):(\d+):", output)
    if not match:
        return output
    lines = Path(v_path).read_text().splitlines()
    line_no = int(match.group(2))
    low = max(0, line_no - context - 1)
    high = min(len(lines), line_no + context)
    body = "\n".join(f"{i + 1:4}: {lines[i]}" for i in range(low, high))
    return f"{output}\n--- {v_path} around line {line_no} ---\n{body}"


def run_synth(dut, path, name, yosys):
    """Convert ``dut`` and run a technology-independent Yosys synthesis.

    The returned result carries ``dut_v`` (the generated Verilog path) and
    ``report`` (Yosys output with the offending Verilog lines inlined), so
    tests can assert without reaching into these helpers.
    """
    path = Path(path)
    dut_v = convert_verilog(dut, path, name)
    module_name, _ = parse_module(dut_v)
    script = (
        f"read_verilog -sv {dut_v}; "
        f"hierarchy -check -top {module_name}; "
        "proc; opt; "
        f"synth -top {module_name}; "
        "stat"
    )
    result = subprocess.run(
        [yosys, "-p", script],
        capture_output=True,
        text=True,
    )
    result.dut_v = str(dut_v)
    result.report = snippet(result.dut_v, result.stdout + result.stderr)
    return result


@pytest.fixture
def convert_dut(tmp_path):
    """Return a helper that converts an elaborated block to Verilog and VHDL.

    The generated files are written under a per-test temporary directory and
    discarded automatically; only success/failure of the conversion matters.
    """

    def _convert(dut, hdl, name, initial_values=False):
        if hdl == "Verilog":
            dut.convert(
                hdl="Verilog",
                path=str(tmp_path),
                name=name,
                testbench=False,
                initial_values=initial_values,
            )
        else:
            dut.convert(
                hdl="VHDL",
                path=str(tmp_path),
                name=name,
                initial_values=initial_values,
            )

    return _convert


@pytest.fixture(scope="session")
def _hdl_toolchain(tmp_path_factory):
    """Locate the optional HDL toolchain once; build the MyHDL VPI if possible.

    The maintainer runs the full cosim/synthesis checks in a reference
    environment that provides the tools; here they are optional and their
    absence only skips the corresponding checks.
    """
    try:
        vpi = build_vpi(tmp_path_factory.mktemp("myhdl_vpi"))
    except (CosimUnavailable, OSError):
        vpi = None
    return {"vpi": vpi, "yosys": shutil.which("yosys")}


@pytest.fixture
def hdl_cosim(_hdl_toolchain, tmp_path):
    """Return a factory that builds a ``Cosimulation`` for an elaborated block."""
    if _hdl_toolchain["vpi"] is None:
        pytest.skip("verilog cosimulation toolchain (iverilog + myhdl.vpi) unavailable")

    def _make(dut, ports, name, initial_values=False):
        return make_cosim(
            dut,
            ports,
            tmp_path,
            name,
            _hdl_toolchain["vpi"],
            initial_values=initial_values,
        )

    return _make


@pytest.fixture
def hdl_synth(_hdl_toolchain, tmp_path):
    """Return a factory that runs a Yosys synth smoke test on an elaborated block."""
    if _hdl_toolchain["yosys"] is None:
        pytest.skip("yosys unavailable")

    def _run(dut, name):
        return run_synth(dut, tmp_path, name, _hdl_toolchain["yosys"])

    return _run
