"""RV32I load/store unit (``RC-FR-070..072``).

Little-endian size handling for data accesses:

* **loads** — extract the addressed byte/halfword/word from the memory read word
  and sign- or zero-extend it to 32 bits (``RC-FR-070``);
* **stores** — shift the store value into the addressed byte lane(s) and raise
  the matching byte strobes (``RC-FR-071``);
* **misalignment** — a halfword/word access with a non-zero low address raises
  ``misaligned`` (``RC-FR-072``).

The access address (``rs1 + imm``) is computed by the ALU (``RC-FR-029``); this
block only resolves size/extension/lane behaviour.  Instruction-fetch alignment
(``RC-FR-073``) belongs to the fetch unit.  ``size`` is ``funct3[1:0]``
(``0`` byte, ``1`` halfword, ``2`` word) and ``zero_extend`` selects a
zero- (``LBU``/``LHU``) vs sign-extended load, matching the decoder's
``mem_size`` / ``mem_unsigned`` outputs.
"""

from myhdl import Signal, always_comb, block, concat, intbv

from ..common.config import ComponentBase, check_positive
from ..common.views import SignalView

__all__ = ["LoadStoreUnit"]

_FULL = 0xFFFF_FFFF


class LoadStoreUnit(ComponentBase):
    """Combinational RV32I load/store data path (``RC-FR-070..072``).

    Ports: ``addr``, ``wdata`` (store source) and ``rdata`` (memory read word)
    in; ``size``/``zero_extend`` select the access; ``load_data``,
    ``store_data``/``wstrb`` and ``misaligned`` out.
    """

    def __init__(self, width: int = 32) -> None:
        self._params = {"width": int(check_positive(width, "width"))}

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        width = self._params["width"]
        return SignalView(
            addr=Signal(intbv(0)[width:]),
            wdata=Signal(intbv(0)[width:]),
            rdata=Signal(intbv(0)[width:]),
            size=Signal(intbv(0)[2:]),
            zero_extend=Signal(bool(0)),
            load_data=Signal(intbv(0)[width:]),
            store_data=Signal(intbv(0)[width:]),
            wstrb=Signal(intbv(0)[width // 8 :]),
            misaligned=Signal(bool(0)),
        )

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the load/store unit onto *ports* and return its instances."""
        addr = ports.addr
        rdata = ports.rdata
        wdata = ports.wdata

        byte_val = Signal(intbv(0)[8:])
        half_val = Signal(intbv(0)[16:])
        byte_ext = Signal(intbv(0)[32:])
        half_ext = Signal(intbv(0)[32:])

        @always_comb
        def extract_byte():
            if addr[2:0] == 0:
                byte_val.next = rdata[8:]
            elif addr[2:0] == 1:
                byte_val.next = rdata[16:8]
            elif addr[2:0] == 2:
                byte_val.next = rdata[24:16]
            else:
                byte_val.next = rdata[32:24]

        @always_comb
        def extract_half():
            if addr[1]:
                half_val.next = rdata[32:16]
            else:
                half_val.next = rdata[16:]

        @always_comb
        def extend_byte():
            if ports.zero_extend:
                byte_ext.next = byte_val
            elif byte_val[7]:
                byte_ext.next = concat(intbv(_FULL)[24:], byte_val)
            else:
                byte_ext.next = concat(intbv(0)[24:], byte_val)

        @always_comb
        def extend_half():
            if ports.zero_extend:
                half_ext.next = half_val
            elif half_val[15]:
                half_ext.next = concat(intbv(_FULL)[16:], half_val)
            else:
                half_ext.next = concat(intbv(0)[16:], half_val)

        @always_comb
        def select_load():
            if ports.size == 2:
                ports.load_data.next = rdata
            elif ports.size == 1:
                ports.load_data.next = half_ext
            else:
                ports.load_data.next = byte_ext

        @always_comb
        def store_path():
            if ports.size == 2:
                ports.store_data.next = wdata
                ports.wstrb.next = 0b1111
            elif ports.size == 1:
                if addr[1]:
                    ports.store_data.next = concat(wdata[16:], intbv(0)[16:])
                    ports.wstrb.next = 0b1100
                else:
                    ports.store_data.next = concat(intbv(0)[16:], wdata[16:])
                    ports.wstrb.next = 0b0011
            else:
                if addr[2:0] == 0:
                    ports.store_data.next = concat(intbv(0)[24:], wdata[8:])
                    ports.wstrb.next = 0b0001
                elif addr[2:0] == 1:
                    ports.store_data.next = concat(
                        intbv(0)[16:], wdata[8:], intbv(0)[8:]
                    )
                    ports.wstrb.next = 0b0010
                elif addr[2:0] == 2:
                    ports.store_data.next = concat(
                        intbv(0)[8:], wdata[8:], intbv(0)[16:]
                    )
                    ports.wstrb.next = 0b0100
                else:
                    ports.store_data.next = concat(wdata[8:], intbv(0)[24:])
                    ports.wstrb.next = 0b1000

        @always_comb
        def detect_misaligned():
            # halfword: odd address; word: any non-multiple-of-4; byte: never
            if ports.size == 2:
                ports.misaligned.next = addr[2:0] != 0
            elif ports.size == 1:
                ports.misaligned.next = addr[0]
            else:
                ports.misaligned.next = 0

        return [
            extract_byte,
            extract_half,
            extend_byte,
            extend_half,
            select_load,
            store_path,
            detect_misaligned,
        ]
