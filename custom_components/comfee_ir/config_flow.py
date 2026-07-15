"""Config flow for Comfee IR integration."""

from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME

from .const import (
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DEFAULT_NAME,
    DOMAIN,
)


class ComfeeIRConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Comfee IR."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            emitter_entity = user_input.get(CONF_INFRARED_EMITTER_ENTITY_ID, "").strip()
            if not emitter_entity:
                errors[CONF_INFRARED_EMITTER_ENTITY_ID] = "required"
            elif "." not in emitter_entity:
                errors[CONF_INFRARED_EMITTER_ENTITY_ID] = "invalid_entity_id"

            if not errors:
                await self.async_set_unique_id(emitter_entity)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data=user_input,
                )

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_INFRARED_EMITTER_ENTITY_ID): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"example_entity": "switch.ir_blaster"},
        )

