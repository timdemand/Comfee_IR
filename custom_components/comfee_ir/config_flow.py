"""Config flow for Comfee IR integration."""

from typing import Any, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import (
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DEFAULT_NAME,
    DOMAIN,
)


class ComfeeIRConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Comfee IR."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_emitters")

        if user_input is not None:
            emitter_entity_id = user_input[CONF_INFRARED_EMITTER_ENTITY_ID]

            await self.async_set_unique_id(emitter_entity_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, DEFAULT_NAME),
                data=user_input,
            )

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_INFRARED_EMITTER_ENTITY_ID): EntitySelector(
                    EntitySelectorConfig(
                        domain=INFRARED_DOMAIN,
                        include_entities=emitter_entity_ids,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if config_entry is None:
            return self.async_abort(reason="reconfigure_failed")

        errors: dict[str, str] = {}

        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_emitters")

        if user_input is not None:
            config_entry.data = {
                **config_entry.data,
                CONF_NAME: user_input.get(CONF_NAME, config_entry.data.get(CONF_NAME, DEFAULT_NAME)),
                CONF_INFRARED_EMITTER_ENTITY_ID: user_input[CONF_INFRARED_EMITTER_ENTITY_ID],
            }
            self.hass.config_entries.async_update_entry(config_entry)
            await self.hass.config_entries.async_reload(config_entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NAME,
                    default=config_entry.data.get(CONF_NAME, DEFAULT_NAME),
                    description="Device Name",
                ): str,
                vol.Required(
                    CONF_INFRARED_EMITTER_ENTITY_ID,
                    default=config_entry.data.get(CONF_INFRARED_EMITTER_ENTITY_ID),
                    description="Infrared Emitter",
                ): EntitySelector(
                    EntitySelectorConfig(
                        domain=INFRARED_DOMAIN,
                        include_entities=emitter_entity_ids,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "current_emitter": config_entry.data.get(CONF_INFRARED_EMITTER_ENTITY_ID)
            },
        )

