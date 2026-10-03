# `myhdl_addons.components` — authoring pattern

This package holds the independent, ISA-neutral, synthesizable building
blocks. The **reference implementation is `alu.py`** — read it before writing
or changing a component. The requirements live in
`reqs/07_independent_components.md`.

Non-negotiable principles (see `reqs/00` §1.2 / `reqs/07` §1.2):

1. **Simplicity first** — the simplest solution that works; no unearned
   abstraction.
2. **Minimal interfaces** — a plain `SignalView` is the container; do **not**
   add `XxxPorts`/view classes without a concrete need.
3. **Convertibility is mandatory** — every component MUST convert to **both
   Verilog and VHDL**. Many small `@always`/`@always_comb` processes are fine.
4. **Tests prove behaviour, not coverage** — sign interpretation, boundaries,
   edge cases, interactions.

## The pattern

```python
from myhdl import ResetSignal, Signal, always, always_comb, block, intbv, concat
from ..common.config import ComponentBase, ceil_log2, check_positive, to_signed
from ..common.errors import HdlConfigError, HdlTypeError
from ..common.views import SignalView

AVAIL_MODES = ("MODE_A", "MODE_B")  # allowed feature names (module-level)


class Foo(ComponentBase):
    """One-paragraph docstring; cite requirement IDs (IC-FR-0xx)."""

    def __init__(
        self,
        width: int = 32,
        modes=None,
        registered: bool = False,
        en: bool = False,
        reset_value: int = 0,
        reset_signal: ResetSignal | None = None,
    ) -> None:
        # 1) validate + normalise every tunable
        p_width = int(check_positive(width, "width"))
        p_modes = AVAIL_MODES if modes is None else tuple(set(modes))
        # 2) store the *effective* config in self._params (an ordered dict)
        self._params = {
            "width": p_width,
            "modes": p_modes,
            "registered": bool(registered),
            "en": bool(en),
            "reset_value": reset_value,
            "reset_signal": reset_signal
            if isinstance(reset_signal, ResetSignal)
            else None,
        }

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        sig = {
            "a": Signal(intbv(0)[self._params["width"] :]),
            "y": Signal(intbv(0)[self._params["width"] :]),
        }
        if self._params["registered"]:
            sig["clk"] = Signal(bool(0))
            if self._params["reset_signal"] is None:
                self._params["reset_signal"] = ResetSignal(0, active=0, isasync=False)
                sig["reset"] = self._params["reset_signal"]
            if self._params["en"]:
                sig["en"] = Signal(bool(0))
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Build the processes onto *ports* and return a list of instances."""
        proclist = []
        # ... one process per enabled feature (see below) ...
        return proclist

    # helper methods are fine when they earn their keep (see Alu):
    #   get_op_intmap(), register_op(), ...
```

### `ComponentBase` constructor — configuration

* Every tunable is an **elaboration-time keyword parameter with a default**.
* Validate with `common.config` helpers; invalid input raises `HdlConfigError`.
* Store the **effective** config in `self._params` (an ordered `dict`).
  `as_dict()`/`repr()` come from `ComponentBase`; no extra config object.
* Module-level `AVAIL_*` tuples name the allowed feature values.
* Feature subsets (ops/flags/modes/outputs) **default to the full `AVAIL_*`
  set**; a caller passes a subset to disable features. Do not add a separate
  `_DEFAULT_*` subset constant.
* Normalise feature subsets at construction (e.g. `tuple(set(ops))`).

### `ports()` — the interface signals

* Allocate signals here and return a **name→signal** `SignalView`
  (`Signal(intbv(0)[width:])`, `Signal(bool(0))`).
* Include `clk`/`reset`/`en` **only** when the feature needs them; a
  combinational component has no clock.
* Use `myhdl.ResetSignal(0, active=0, isasync=False)` for the reset port
  (named `reset` in the Alu pattern).

### `@block hdl(self, ports)` — the implementation

* Return a **list of instances** (`proclist`).
* **One process per enabled feature**, created conditionally at elaboration —
  disabling a feature removes its logic (zero overhead):

  ```python
  proclist = []
  if "MODE_A" in self._params["modes"]:

      @always_comb
      def foo_mode_a():
          ports.y.next = ports.a + 1

      proclist.append(foo_mode_a)
  ```

* Decorators:
  * combinational → `@always_comb`; state → `@always(clk.posedge)`.
  * `@instance` is **testbench-only** (not convertible).
  * `@always_comb` only sees signals read *directly*; when the body indexes a
    tuple/list of signals or calls a helper, use an explicit sensitivity list:
    `@always(ports.sel, *partial_y)`.
  * prefer `@always(clk.posedge)` with explicit reset over `@always_seq`
    (its reset handling was not detected).
* Typical structure: compute per-feature partial results into a **tuple of
  signals**, then a mux process selects the result; add a registered output
  stage (`@always(clk.posedge)`) when `registered` is set.

### Helper methods

Add helpers only when they simplify the block (e.g. `get_op_intmap()` maps
names→codes, `register_op(name, cb)` is an extension hook). Keep them
elaboration-time Python; do not wrap `@always` creation in a plain helper
function — the function that creates a process must itself be a `@block`.

## Convertibility rules (inside every process body and any function it calls)

MyHDL's converter rejects: tuple unpacking/assignment, dict literals and
subscripts, list literals, `lambda`, nested `def`, `try`, `import`, multiple
assignment, chained comparisons, true division (`/`), and ternary
(`x if c else y`). A called function's free variables must be only `int` or
`Signal` — inline logic instead of closing over `self`/sets/lists.

Useful idioms: `concat(intbv(0)[1:], sig)` to widen; keep a carry bit in a
`width+1` signal and read `partial[width]` / `partial[width:]`;
`common.config.to_signed(int(sig), width)` for signed compare.

## Testing

Two files per component:

* `tests/test_component_<name>_<aspect>.py` — **behaviour-first** simulation.
  Drive `ports.x.next`, `yield delay(1)` / `clk.posedge`, then assert on
  `int(ports.y)`. Cover every enabled feature, sign interpretation,
  boundaries/edge operands, and interactions.
* `tests/test_component_<name>_conversion.py` — a smoke test that elaborates
  with `comp.hdl(comp.ports())` and converts **both** HDLs via the
  `convert_dut` fixture in `tests/conftest.py`.

```python
@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_foo_converts(hdl, convert_dut):
    comp = Foo(width=8)
    convert_dut(comp.hdl(comp.ports()), hdl, f"foo_{hdl.lower()}")
```

Coverage ≥ 85 %/file is the floor, not the goal.
