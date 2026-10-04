"""Address map and decoder.

Implements ``CB-FR-060`` (``AddressMap`` plus a protocol-agnostic decoder),
``CB-FR-061`` (overlap/out-of-range windows raise at elaboration) and
``CB-FR-062`` (reused by every per-bus fabric; only the field width differs).
"""

from collections.abc import Iterator, Sequence

from myhdl import SignalType, block

from ..common.views import SignalView
from ..components import AddressDecoder
from .checks import check_address_range
from .errors import BusConfigError
from .params import check_positive_int

__all__ = ["AddressMap", "address_decoder"]


class AddressMap:
    """An ordered, non-overlapping set of slave address windows."""

    def __init__(self, adr_width: int) -> None:
        check_positive_int(adr_width, "adr_width")
        self.adr_width = adr_width
        self._regions: list[tuple[int, int, str | None]] = []

    def add(self, base: int, size: int, name: str | None = None) -> int:
        """Add a region, raising on any overlap or out-of-range window."""
        check_address_range(base, size, self.adr_width, name or "region")
        for b, s, n in self._regions:
            if base < (b + s) and b < (base + size):
                raise BusConfigError(
                    f"address region {name!r} [{base:#x}, {base + size:#x}) "
                    f"overlaps {n!r} [{b:#x}, {b + s:#x})"
                )
        self._regions.append((base, size, name))
        return base

    @property
    def regions(self) -> list[tuple[int, int, str | None]]:
        return list(self._regions)

    def bases(self) -> list[int]:
        return [r[0] for r in self._regions]

    def sizes(self) -> list[int]:
        return [r[1] for r in self._regions]

    def names(self) -> list[str | None]:
        return [r[2] for r in self._regions]

    def find(self, address: int) -> int | None:
        """Return the index of the region containing *address*, or ``None``."""
        for i, (base, size, _) in enumerate(self._regions):
            if base <= address < base + size:
                return i
        return None

    def __len__(self) -> int:
        return len(self._regions)

    def __iter__(self) -> Iterator[tuple[int, int, str | None]]:
        return iter(self._regions)

    def __repr__(self) -> str:
        return f"AddressMap(adr_width={self.adr_width}, regions={len(self._regions)})"


@block
def address_decoder(
    adr: SignalType,
    selects: Sequence[SignalType],
    baseaddrs: Sequence[int],
    sizes: Sequence[int],
):
    """Combinational decoder: assert one ``selects[i]`` per address window.

    A thin, converting wrapper around the independent
    :class:`~myhdl_addons.components.AddressDecoder` component: it adopts the
    caller's ``adr``/``selects`` signals and reuses the component's logic.

    Args:
        adr: ``Signal(intbv)`` address.
        selects: list of ``Signal(bool)`` chip-selects.
        baseaddrs, sizes: parallel lists of window base/size.
    """
    if not (len(selects) == len(baseaddrs) == len(sizes)):
        raise BusConfigError("selects/baseaddrs/sizes must have equal length")
    n = len(selects)
    windows = tuple((int(baseaddrs[i]), int(sizes[i])) for i in range(n))
    decoder = AddressDecoder(adr_width=len(adr), windows=windows)
    view = {"adr": adr}
    for i in range(n):
        view[f"sel{i}"] = selects[i]
    return decoder.hdl(SignalView(**view))
