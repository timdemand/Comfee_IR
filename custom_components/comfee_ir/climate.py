"""Comfee AC climate entity with on-demand Tuya IR command generation."""

from __future__ import annotations

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.components.infrared import InfraredCommand, InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import (
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DEFAULT_NAME,
    DOMAIN,
    FAN_MODES,
    MAX_TEMP,
    MIN_TEMP,
)
from .tuya_ir import build_infrared_command

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


def _effective_fan_for_mode(hvac_mode: HVACMode, fan_mode: str) -> str:
    allowed = SUPPORTED_BY_MODE.get(hvac_mode)
    if not allowed:
        return fan_mode
    return fan_mode if fan_mode in allowed else allowed[0]


def _build_semantic_frame(hvac_mode: HVACMode, temp_c: int, fan_mode: str, power_on: bool) -> list[int]:
    if hvac_mode not in SUPPORTED_BY_MODE:
        raise HomeAssistantError(f"Unsupported mode for generator: {hvac_mode}")

    fan_mode = _effective_fan_for_mode(hvac_mode, fan_mode)
    sem_b1 = _SEM_B1_ON[(hvac_mode, fan_mode)]
    if not power_on:
        sem_b1 &= 0x7F

    t = max(MIN_TEMP, min(MAX_TEMP, int(temp_c)))
    sem_b2 = 0x40 | (t - MIN_TEMP)
    if hvac_mode == HVACMode.FAN_ONLY:
        sem_b2 |= 0x10

    return [0xA1, sem_b1, sem_b2, 0xFF, 0xFF]


def generate_command(hvac_mode: HVACMode, temp_c: int, fan_mode: str, power_on: bool) -> InfraredCommand:
    semantic_frame = _build_semantic_frame(hvac_mode, temp_c, fan_mode, power_on)
    return build_infrared_command(semantic_frame)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comfee IR climate from config entry."""
    entity = ComfeeIrClimateEntity(
        name=entry.data.get(CONF_NAME, DEFAULT_NAME),
        infrared_emitter_entity_id=entry.data[CONF_INFRARED_EMITTER_ENTITY_ID],
    )
    async_add_entities([entity])


class ComfeeIrClimateEntity(ClimateEntity, InfraredEmitterConsumerEntity):
    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = 1

    def __init__(
        self,
        *,
        name: str,
        infrared_emitter_entity_id: str,
    ) -> None:
        self._attr_name = name
        self._infrared_emitter_entity_id = infrared_emitter_entity_id
        self._attr_unique_id = f"{DOMAIN}_{slugify(infrared_emitter_entity_id)}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, infrared_emitter_entity_id)},
            name=name,
            manufacturer="Comfee",
            model="IR Climate",
        )

        self._attr_hvac_mode = HVACMode.OFF
        self._last_on_mode = HVACMode.COOL
        self._attr_target_temperature = INITIAL_TARGET_TEMP
        self._attr_fan_mode = INITIAL_FAN_MODE

        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.DRY, HVACMode.AUTO, HVACMode.FAN_ONLY]
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

        self._attr_target_temperature = max(MIN_TEMP, min(MAX_TEMP, int(temp)))
        self._attr_fan_mode = effective_fan

