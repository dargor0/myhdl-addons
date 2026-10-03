"""General-purpose register (``IC-FR-130..137``).

One field-based component covers both plain registers and pipeline registers;
a pipeline register is simply a :class:`Register` with multiple fields and
``flush`` enabled.  Control priority is ``reset > flush > load > en > hold``.

Convertibility shapes the implementation: per field, the controls are a chain
of small combinational mux stages (``en`` hold, then ``load``, then ``flush``)
feeding one ``@always(clk.posedge)`` register process; disabled controls simply
omit their stage.
"""

from myhdl import Signal, always, always_comb, block, intbv

from ..common.config import (
    ComponentBase,
    check_bool,
    check_int,
    check_positive,
    mask,
)
from ..common.errors import HdlConfigError
from ..common.views import SignalView

__all__ = ["Register"]


def _check_fields(fields) -> tuple[tuple[str, int], ...]:
    if fields is None:
        return (("q", 32),)
    try:
        entries = tuple(fields)
    except TypeError:
        raise HdlConfigError(
            f"fields must be an iterable of (name, width), got {fields!r}"
        )
    if not entries:
        raise HdlConfigError("fields must not be empty")
    seen: set[str] = set()
    result: list[tuple[str, int]] = []
    for entry in entries:
        if not isinstance(entry, (tuple, list)) or len(entry) != 2:
            raise HdlConfigError(f"field must be a (name, width) pair, got {entry!r}")
        name, width = entry
        if not isinstance(name, str) or not name:
            raise HdlConfigError(f"field name must be a non-empty string, got {name!r}")
        if name in seen:
            raise HdlConfigError(f"duplicate field name {name!r}")
        seen.add(name)
        result.append((name, check_positive(width, f"width of {name!r}")))
    return tuple(result)


def _check_values(values, names: set[str], name: str) -> dict[str, int]:
    if values is None:
        return {}
    if not isinstance(values, dict):
        raise HdlConfigError(f"{name} must be a dict of field->value")
    result: dict[str, int] = {}
    for key, value in values.items():
        if key not in names:
            raise HdlConfigError(f"{name} has unknown field {key!r}")
        result[key] = check_int(value, f"{name}[{key!r}]")
    return result


@block
def hold_mux(en, d, q, y):
    """Write-enable mux: capture ``d`` when enabled, else hold ``q``."""

    @always_comb
    def p():
        if en:
            y.next = d
        else:
            y.next = q

    return p


@block
def ctrl_mux(ctrl, din, value, y):
    """Control override mux: force the constant ``value`` when ``ctrl``."""

    @always_comb
    def p():
        if ctrl:
            y.next = value
        else:
            y.next = din

    return p


@block
def reg_field(clk, resetn, d, q, reset_enable, reset_value):
    """Field register: synchronous capture with optional active-low reset."""

    if reset_enable:

        @always(clk.posedge)
        def p():
            if not resetn:
                q.next = reset_value
            else:
                q.next = d

    else:

        @always(clk.posedge)
        def p():
            q.next = d

    return p


class Register(ComponentBase):
    """Field-based synchronous register (``IC-FR-130..137``).

    Args:
        fields: list of ``(name, width)`` pairs (default ``[("q", 32)]``).
        en: include a write-enable (hold when low).
        flush: include a flush input (force to ``flush_values``).
        load: include a load input (force to ``load_values``).
        reset_enable: reset the fields on active-low ``resetn``.
        reset_values, flush_values, load_values: per-field value dicts.
        init: optional per-field simulation initial values.
    """

    def __init__(
        self,
        fields=None,
        en: bool = True,
        flush: bool = False,
        load: bool = False,
        reset_enable: bool = True,
        reset_values=None,
        flush_values=None,
        load_values=None,
        init=None,
    ) -> None:
        p_fields = _check_fields(fields)
        names = {name for name, _ in p_fields}
        self._params = {
            "fields": p_fields,
            "en": check_bool(en, "en"),
            "flush": check_bool(flush, "flush"),
            "load": check_bool(load, "load"),
            "reset_enable": check_bool(reset_enable, "reset_enable"),
            "reset_values": _check_values(reset_values, names, "reset_values"),
            "flush_values": _check_values(flush_values, names, "flush_values"),
            "load_values": _check_values(load_values, names, "load_values"),
            "init": _check_values(init, names, "init"),
        }

    def _initial(self, name: str, width: int) -> int:
        value = self._params["init"].get(
            name, self._params["reset_values"].get(name, 0)
        )
        return value & mask(width)

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        sig = {"clk": Signal(bool(0)), "resetn": Signal(bool(0))}
        for name, width in self._params["fields"]:
            sig[f"d_{name}"] = Signal(intbv(0)[width:])
            sig[f"q_{name}"] = Signal(intbv(self._initial(name, width))[width:])
        if self._params["en"]:
            sig["en"] = Signal(bool(0))
        if self._params["flush"]:
            sig["flush"] = Signal(bool(0))
        if self._params["load"]:
            sig["load"] = Signal(bool(0))
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the register onto *ports* and return its instances."""
        has_en = self._params["en"]
        has_flush = self._params["flush"]
        has_load = self._params["load"]
        reset_enable = self._params["reset_enable"]
        reset_values = self._params["reset_values"]
        flush_values = self._params["flush_values"]
        load_values = self._params["load_values"]

        proclist = []
        for name, width in self._params["fields"]:
            full = mask(width)
            d = ports[f"d_{name}"]
            q = ports[f"q_{name}"]
            cur = d
            if has_en:
                nxt = Signal(intbv(0)[width:])
                proclist.append(hold_mux(ports.en, cur, q, nxt))
                cur = nxt
            if has_load:
                nxt = Signal(intbv(0)[width:])
                proclist.append(
                    ctrl_mux(ports.load, cur, load_values.get(name, 0) & full, nxt)
                )
                cur = nxt
            if has_flush:
                nxt = Signal(intbv(0)[width:])
                proclist.append(
                    ctrl_mux(ports.flush, cur, flush_values.get(name, 0) & full, nxt)
                )
                cur = nxt
            proclist.append(
                reg_field(
                    ports.clk,
                    ports.resetn,
                    cur,
                    q,
                    reset_enable,
                    reset_values.get(name, 0) & full,
                )
            )

        return proclist
