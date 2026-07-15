"""Comfee IR button entity for toggling the AC's LED display."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.components.infrared import InfraredCommand, InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import CONF_INFRARED_EMITTER_ENTITY_ID, DEFAULT_NAME, DOMAIN
from .tuya_ir import build_infrared_command

# The AC's "Display" button is a fixed, state-independent command in the
# Comfee/Midea A1 IR protocol (same frame format as climate.py, header 0xA2).
_LED_TOGGLE_SEMANTIC_FRAME = [0xA2, 0x08, 0xFF, 0xFF, 0xFF]


def generate_led_toggle_command() -> InfraredCommand:
    return build_infrared_command(_LED_TOGGLE_SEMANTIC_FRAME)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comfee IR button from config entry."""
    entity = ComfeeIrLedToggleButton(
        name=entry.data.get(CONF_NAME, DEFAULT_NAME),
        infrared_emitter_entity_id=entry.data[CONF_INFRARED_EMITTER_ENTITY_ID],
    )
    async_add_entities([entity])


class ComfeeIrLedToggleButton(ButtonEntity, InfraredEmitterConsumerEntity):
    _attr_has_entity_name = False
    _attr_icon = "mdi:television-ambient-light"

    def __init__(self, *, name: str, infrared_emitter_entity_id: str) -> None:
        self._infrared_emitter_entity_id = infrared_emitter_entity_id
        self._attr_name = f"{name} LED Display"
        self._attr_unique_id = f"{DOMAIN}_{slugify(infrared_emitter_entity_id)}_led_toggle"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, infrared_emitter_entity_id)},
            name=name,
            manufacturer="Comfee",
            model="IR Climate",
        )

    async def async_press(self) -> None:
        await self._send_command(generate_led_toggle_command())
