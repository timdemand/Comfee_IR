"""Comfee IR button entity for toggling the AC's LED display."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import CONF_TEXT_ENTITY_ID, DEFAULT_NAME, DOMAIN
from .tuya_ir import build_frame, encode_command, send_ir_command

# The AC's "Display" button is a fixed, state-independent command in the
# Comfee/Midea A1 IR protocol (same frame format as climate.py, header 0xA2).
_LED_TOGGLE_SEMANTIC_FRAME = [0xA2, 0x08, 0xFF, 0xFF, 0xFF]


def generate_led_toggle_command() -> str:
    return encode_command(build_frame(_LED_TOGGLE_SEMANTIC_FRAME))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comfee IR button from config entry."""
    entity = ComfeeIrLedToggleButton(
        name=entry.data.get(CONF_NAME, DEFAULT_NAME),
        text_entity_id=entry.data[CONF_TEXT_ENTITY_ID],
    )
    async_add_entities([entity])


class ComfeeIrLedToggleButton(ButtonEntity):
    _attr_has_entity_name = False
    _attr_icon = "mdi:television-ambient-light"

    def __init__(self, *, name: str, text_entity_id: str) -> None:
        self._text_entity_id = text_entity_id
        self._attr_name = f"{name} LED Display"
        self._attr_unique_id = f"{DOMAIN}_{slugify(text_entity_id)}_led_toggle"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, text_entity_id)},
            name=name,
            manufacturer="Comfee",
            model="IR Climate",
        )

    async def async_press(self) -> None:
        await send_ir_command(self.hass, self._text_entity_id, generate_led_toggle_command())
