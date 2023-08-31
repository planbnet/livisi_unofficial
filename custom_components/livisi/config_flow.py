"""Config flow for Livisi Home Assistant."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .livisi_controller import LivisiController

from .livisi_connector import LivisiConnection, connect as livisi_connect
from .livisi_errors import (
    WrongCredentialException,
    IncorrectIpAddressException,
    ShcUnreachableException,
)

from .const import CONF_HOST, CONF_PASSWORD, DOMAIN, LOGGER


class LivisiFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Livisi Smart Home config flow."""

    VERSION = 4

    def __init__(self) -> None:
        """Create the configuration file."""
        self.aio_livisi: LivisiConnection = None
        self.data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=self.data_schema)

        errors = {}
        try:
            self.aio_livisi = await livisi_connect(
                user_input[CONF_HOST], user_input[CONF_PASSWORD]
            )
        except WrongCredentialException:
            errors["base"] = "wrong_password"
        except ShcUnreachableException:
            errors["base"] = "cannot_connect"
        except IncorrectIpAddressException:
            errors["base"] = "wrong_ip_address"
        else:
            if self.aio_livisi.controller:
                return await self.create_entity(user_input, self.aio_livisi.controller)

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=self.data_schema, errors=errors
        )

    async def create_entity(
        self, user_input: dict[str, str], controller: LivisiController
    ) -> FlowResult:
        """Create livisi entity."""
        LOGGER.debug(
            "Integrating SHC %s with serial number: %s",
            controller.controller_type,
            controller.serial_number,
        )

        return self.async_create_entry(
            title=f"SHC {controller.controller_type}",
            data={
                **user_input,
            },
        )
