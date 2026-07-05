"""Shared Tuya IR frame/signal encoding for the Comfee/Midea A1 protocol."""

from __future__ import annotations

import base64
import io
from bisect import bisect
from struct import pack

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


def _reverse_byte(b: int) -> int:
    b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4)
    b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2)
    b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1)
    return b


def build_frame(semantic_bytes: list[int]) -> bytes:
    """Reverse each semantic byte's bits and append a checksum byte."""
    wire = [_reverse_byte(x) for x in semantic_bytes]
    checksum = (256 - sum(wire)) % 256
    wire.append(checksum)
    return bytes(wire)


def _frame_to_signal(frame: bytes) -> list[int]:
    out = [4500, 4500]
    for b in frame:
        for bit in range(8):
            out.append(560)
            out.append(1680 if ((b >> bit) & 1) else 560)
    out.append(560)
    return out


def _emit_literal_blocks(out: io.BytesIO, data: bytes) -> None:
    for i in range(0, len(data), 32):
        chunk = data[i:i + 32]
        out.write(bytes([len(chunk) - 1]))
        out.write(chunk)


def _emit_distance_block(out: io.BytesIO, length: int, distance: int) -> None:
    distance -= 1
    length -= 2
    block = bytearray()
    if length >= 7:
        block.append(length - 7)
        length = 7
    block.insert(0, length << 5 | distance >> 8)
    block.append(distance & 0xFF)
    out.write(block)


def _compress_tuya(out: io.BytesIO, data: bytes, level: int = 2) -> None:
    if level == 0:
        _emit_literal_blocks(out, data)
        return

    window = 2**13
    max_len = 255 + 9

    suffixes: list[int] = []
    next_pos = 0
    pos = 0

    def key(n: int) -> bytes:
        return data[n:]

    def find_idx(n: int) -> int:
        return bisect(suffixes, key(n), key=key)

    def distance_candidates() -> list[int]:
        nonlocal next_pos
        while next_pos <= pos:
            if len(suffixes) == window:
                suffixes.pop(find_idx(next_pos - window))
            suffixes.insert(find_idx(next_pos), next_pos)
            next_pos += 1

        idx = find_idx(pos)
        candidates: list[int] = []
        for off in (1, -1):
            nidx = idx + off
            if 0 <= nidx < len(suffixes):
                candidates.append(pos - suffixes[nidx])
        return candidates

    def length_for_distance(start: int) -> int:
        length = 0
        limit = min(max_len, len(data) - pos)
        while length < limit and data[pos + length] == data[start + length]:
            length += 1
        return length

    block_start = 0
    while pos < len(data):
        best: tuple[int, int] | None = None
        for dist in distance_candidates():
            if dist <= 0:
                continue
            cand = (length_for_distance(pos - dist), dist)
            if cand[0] >= 3 and (best is None or (cand[0], -cand[1]) > (best[0], -best[1])):
                best = cand

        if best is not None:
            _emit_literal_blocks(out, data[block_start:pos])
            _emit_distance_block(out, best[0], best[1])
            pos += best[0]
            block_start = pos
        else:
            pos += 1

    _emit_literal_blocks(out, data[block_start:pos])


def _encode_tuya_ir(signal: list[int]) -> str:
    payload = b"".join(pack("<H", t) for t in signal)
    out = io.BytesIO()
    _compress_tuya(out, payload, level=2)
    return base64.b64encode(out.getvalue()).decode("ascii")


def encode_command(frame: bytes) -> str:
    """Encode a 6-byte wire frame (plus its bitwise-inverted copy) as a Tuya IR base64 payload."""
    inv_frame = bytes((x ^ 0xFF) for x in frame)
    signal = _frame_to_signal(frame) + [4500] + _frame_to_signal(inv_frame)
    return _encode_tuya_ir(signal)


async def send_ir_command(hass: HomeAssistant, text_entity_id: str, payload: str) -> None:
    """Send an encoded Tuya IR payload through a text helper entity."""
    try:
        await hass.services.async_call(
            "text",
            "set_value",
            {
                ATTR_ENTITY_ID: text_entity_id,
                "value": payload,
            },
            blocking=True,
        )
    except Exception as err:
        raise HomeAssistantError(f"Failed to send IR command to {text_entity_id}: {err}") from err
