"""Address map and decoder.

Implements ``WB-FR-060`` (decoder from a parameterised address map),
``WB-FR-061`` (validate overlapping windows at elaboration) and
``WB-FR-062`` (base+size / inclusive-range support).
"""

from collections.abc import Sequence

from myhdl import SignalType, block

from ..bus_common.addrmap import address_decoder as _common_address_decoder
from .checks import WishboneConfigError, check_address_range

__all__ = ["AddressMap", "address_decoder"]


class AddressMap:
    """An ordered, non-overlapping set of slave address windows."""

    def __init__(self, adr_width: int) -> None:
        self.adr_width = adr_width
        self._regions: list[tuple[int, int, str | None]] = []

    def add(self, base: int, size: int, name: str | None = None) -> None:
        """Add a region, raising on any overlap."""
        check_address_range(base, size, self.adr_width, name or "region")
        for b, s, n in self._regions:
            if base < (b + s) and b < (base + size):
                raise WishboneConfigError(
                    f"address region {name!r} [{base:#x}, {base + size:#x}) "
                    f"overlaps {n!r} [{b:#x}, {b + s:#x})"
                )
        self._regions.append((base, size, name))

    @property
    def regions(self) -> list[tuple[int, int, str | None]]:
        return list(self._regions)

    def bases(self) -> list[int]:
        return [r[0] for r in self._regions]

    def sizes(self) -> list[int]:
        return [r[1] for r in self._regions]


@block
def address_decoder(
    adr: SignalType,
    selects: Sequence[SignalType],
    baseaddrs: Sequence[int],
    sizes: Sequence[int],
):
    """Combinational decoder: assert one ``selects[i]`` per address window.

    Thin Wishbone wrapper around the common
    :func:`~myhdl_addons.bus_common.addrmap.address_decoder` (which reuses the
    ``AddressDecoder`` component); it keeps the Wishbone error type for the
    argument validation.

    Args:
        adr: ``Signal(intbv)`` address.
        selects: list of ``Signal(bool)`` chip-selects.
        baseaddrs, sizes: parallel lists of window base/size.
    """
    if not (len(selects) == len(baseaddrs) == len(sizes)):
        raise WishboneConfigError("selects/baseaddrs/sizes must have equal length")
    return _common_address_decoder(adr, selects, baseaddrs, sizes)
