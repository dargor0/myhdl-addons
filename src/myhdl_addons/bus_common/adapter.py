"""Adapter framework.

Implements ``CB-FR-120`` (``AdapterBase`` supporting both directions plus a
common loopback/self-check template) and is the base for the cross-bus
adapters required by ``CB-FR-121``/``CB-FR-122``.
"""

from collections.abc import Sequence
from typing import Any

from .errors import BusProtocolError

__all__ = ["AdapterBase"]


class AdapterBase:
    """Base class for protocol translators between two bus endpoints.

    Subclasses implement :meth:`build` (elaboration) and the translation
    hooks (:meth:`convert_request` / :meth:`convert_response`).  Directional
    support is declared through *to_downstream* / *to_upstream*.
    """

    def __init__(
        self,
        upstream: Any = None,
        downstream: Any = None,
        name: str = "adapter",
        *,
        to_downstream: bool = True,
        to_upstream: bool = True,
    ) -> None:
        self.upstream = upstream
        self.downstream = downstream
        self.name = name
        self.to_downstream = bool(to_downstream)
        self.to_upstream = bool(to_upstream)

    @property
    def bidirectional(self) -> bool:
        return self.to_downstream and self.to_upstream

    def build(self) -> Any:
        """Return the MyHDL instances implementing the translation."""
        raise NotImplementedError(f"{type(self).__name__} must implement build()")

    def convert_request(self, addr: int, we: bool, data: Any, sel: Any = None) -> Any:
        """Translate a request for the opposite side (per-bus)."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement convert_request()"
        )

    def convert_response(self, response: Any) -> Any:
        """Translate a response for the opposite side (per-bus)."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement convert_response()"
        )

    def self_check(
        self,
        bfm: Any,
        pairs: Sequence[tuple[int, Any]],
        sel: Any = None,
        readback: bool = True,
    ) -> Any:
        """Common loopback/self-check template (``CB-FR-120``).

        Writes each ``(addr, data)`` pair, optionally reads it back and
        raises :class:`BusProtocolError` on a mismatch.
        """
        for addr, data in pairs:
            yield bfm.write(addr, data, sel=sel)
            if readback:
                yield bfm.read(addr, sel=sel)
                if bfm.last_data != data:
                    raise BusProtocolError(
                        f"{self.name} self-check failed at {addr:#x}: "
                        f"wrote {data!r}, read {bfm.last_data!r}"
                    )
