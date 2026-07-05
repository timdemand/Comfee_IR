"""Comfee AC climate entity with on-demand Tuya IR command generation."""

from __future__ import annotations

import base64
import io
from bisect import bisect
from struct import pack

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import (
    CONF_TEXT_ENTITY_ID,
    DEFAULT_NAME,
    DOMAIN,
    FAN_MODES,
)

INITIAL_TARGET_TEMP = 21
INITIAL_FAN_MODE = "low"

# Command generation profiles calibrated from captured packets.
_SEM_B1_ON = {
    (HVACMode.COOL, "low"): 0x88,
    (HVACMode.COOL, "high"): 0x98,
    (HVACMode.COOL, "auto"): 0xA0,
    (HVACMode.DRY, "low"): 0x81,
    (HVACMode.AUTO, "low"): 0x82,
    (HVACMode.FAN_ONLY, "low"): 0x8C,
    (HVACMode.FAN_ONLY, "high"): 0x9C,
    (HVACMode.FAN_ONLY, "auto"): 0xAC,
}

SUPPORTED_BY_MODE = {
    HVACMode.COOL: ["low", "high", "auto"],
    HVACMode.DRY: ["low"],
    HVACMode.AUTO: ["low"],
    HVACMode.FAN_ONLY: ["low", "high", "auto"],
}

def _reverse_byte(b: int) -> int:
    b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4)
    b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2)
    b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1)
    return b


def _build_semantic_frame(hvac_mode: HVACMode, temp_c: int, fan_mode: str, power_on: bool) -> bytes:
    if hvac_mode not in SUPPORTED_BY_MODE:
        raise HomeAssistantError(f"Unsupported mode for generator: {hvac_mode}")

    allowed_fans = SUPPORTED_BY_MODE[hvac_mode]
    if fan_mode not in allowed_fans:
        fan_mode = allowed_fans[0]

    sem_b1 = _SEM_B1_ON[(hvac_mode, fan_mode)]
    if not power_on:
        sem_b1 &= 0x7F

    t = max(17, min(31, int(temp_c)))
    sem_b2 = 0x40 | (t - 17)
    if hvac_mode == HVACMode.FAN_ONLY:
        sem_b2 |= 0x10

    sem = [0xA1, sem_b1, sem_b2, 0xFF, 0xFF, 0x00]
    wire = [_reverse_byte(x) for x in sem[:5]]
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


def generate_command(hvac_mode: HVACMode, temp_c: int, fan_mode: str, power_on: bool) -> str:
    frame = _build_semantic_frame(hvac_mode, temp_c, fan_mode, power_on)
    inv_frame = bytes((x ^ 0xFF) for x in frame)
    signal = _frame_to_signal(frame) + [4500] + _frame_to_signal(inv_frame)
    return _encode_tuya_ir(signal)


def _effective_fan_for_mode(hvac_mode: HVACMode, fan_mode: str) -> str:
    allowed = SUPPORTED_BY_MODE.get(hvac_mode)
    if not allowed:
        return fan_mode
    return fan_mode if fan_mode in allowed else allowed[0]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comfee IR climate from config entry."""
    entity = ComfeeIrClimateEntity(
        name=entry.data.get(CONF_NAME, DEFAULT_NAME),
        text_entity_id=entry.data[CONF_TEXT_ENTITY_ID],
    )
    async_add_entities([entity])


class ComfeeIrClimateEntity(ClimateEntity):
    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_min_temp = 17
    _attr_max_temp = 31
    _attr_target_temperature_step = 1

    def __init__(
        self,
        *,
        name: str,
        text_entity_id: str,
    ) -> None:
        self._attr_name = name
        self._text_entity_id = text_entity_id
        self._attr_unique_id = f"{DOMAIN}_{slugify(text_entity_id)}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, text_entity_id)},
            name=name,
            manufacturer="Comfee",
            model="IR Climate",
        )

        self._attr_hvac_mode = HVACMode.OFF
        self._last_on_mode = HVACMode.COOL
        self._attr_target_temperature = INITIAL_TARGET_TEMP
        self._attr_fan_mode = INITIAL_FAN_MODE

        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.DRY, HVACMode.AUTO, HVACMode.FAN_ONLY]
        self._attr_fan_modes = FAN_MODES
        self._update_available_fan_modes(self._last_on_mode)

    def _update_available_fan_modes(self, mode: HVACMode) -> None:
        allowed = SUPPORTED_BY_MODE.get(mode, FAN_MODES)
        self._attr_fan_modes = allowed
        if self._attr_fan_mode not in allowed:
            self._attr_fan_mode = allowed[0]

    @property
    def temperature_unit(self) -> str:
        return UnitOfTemperature.CELSIUS

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self._send_off_or_fallback()
            self._attr_hvac_mode = HVACMode.OFF
            self._update_available_fan_modes(self._last_on_mode)
            self.async_write_ha_state()
            return

        await self._send_best_match(hvac_mode, int(self._attr_target_temperature), self._attr_fan_mode)
        self._attr_hvac_mode = hvac_mode
        self._last_on_mode = hvac_mode
        self._update_available_fan_modes(hvac_mode)
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs) -> None:
        temp = int(kwargs["temperature"])
        self._attr_target_temperature = temp

        if self._attr_hvac_mode != HVACMode.OFF:
            await self._send_best_match(self._attr_hvac_mode, temp, self._attr_fan_mode)
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        if fan_mode not in self._attr_fan_modes:
            return

        self._attr_fan_mode = fan_mode

        if self._attr_hvac_mode != HVACMode.OFF:
            await self._send_best_match(self._attr_hvac_mode, int(self._attr_target_temperature), fan_mode)
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(self._last_on_mode)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def _send_off_or_fallback(self) -> None:
        payload = generate_command(
            hvac_mode=self._last_on_mode,
            temp_c=int(self._attr_target_temperature),
            fan_mode=self._attr_fan_mode,
            power_on=False,
        )
        await self._send_command(payload)

    async def _send_best_match(self, hvac_mode: HVACMode, temp: int, fan_mode: str) -> None:
        effective_fan = _effective_fan_for_mode(hvac_mode, fan_mode)
        payload = generate_command(
            hvac_mode=hvac_mode,
            temp_c=temp,
            fan_mode=effective_fan,
            power_on=True,
        )
        await self._send_command(payload)

        self._attr_target_temperature = max(17, min(31, int(temp)))
        self._attr_fan_mode = effective_fan

    async def _send_command(self, tuya_payload: str) -> None:
        try:
            await self.hass.services.async_call(
                "text",
                "set_value",
                {
                    ATTR_ENTITY_ID: self._text_entity_id,
                    "value": tuya_payload,
                },
                blocking=True,
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to send IR command to {self._text_entity_id}: {err}") from err
