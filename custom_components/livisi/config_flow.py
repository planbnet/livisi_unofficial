"""Config flow for Livisi Home Assistant."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from livisi import LivisiController
from livisi import LivisiConnection, connect as livisi_connect
from livisi import (
    ErrorCodeException,
    WrongCredentialException,
    IncorrectIpAddressException,
    ShcUnreachableException,
)

from .const import CONF_HOST, CONF_HOST_SECONDARY, CONF_PASSWORD, DOMAIN, LOGGER

# Exceptions that indicate a network/connectivity problem (not auth)
_CONNECT_ERRORS = (ShcUnreachableException, IncorrectIpAddressException, ErrorCodeException)


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
                vol.Optional(CONF_HOST_SECONDARY): str,
            }
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle reconfiguration of an existing entry (e.g. to add a secondary host)."""
        entry = self._get_reconfigure_entry()

        if user_input is None:
            schema = self._reconfigure_schema(entry.data)
            return self.async_show_form(
                step_id="reconfigure", data_schema=schema
            )

        errors = {}
        host_secondary = user_input.get(CONF_HOST_SECONDARY) or None
        try:
            self.aio_livisi = await self._try_connect(
                user_input[CONF_HOST], host_secondary, user_input[CONF_PASSWORD]
            )
        except WrongCredentialException:
            errors["base"] = "wrong_password"
        except IncorrectIpAddressException:
            errors["base"] = "wrong_ip_address"
        except (ShcUnreachableException, ErrorCodeException):
            errors["base"] = "cannot_connect"
        else:
            await self.aio_livisi.close()
            data = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            if host_secondary:
                data[CONF_HOST_SECONDARY] = host_secondary
            return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._reconfigure_schema(user_input),
            errors=errors,
        )

    def _reconfigure_schema(self, current: dict) -> vol.Schema:
        """Build the reconfigure form schema pre-filled with current values."""
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=current.get(CONF_HOST, "")): str,
                vol.Required(CONF_PASSWORD, default=current.get(CONF_PASSWORD, "")): str,
                vol.Optional(
                    CONF_HOST_SECONDARY,
                    default=current.get(CONF_HOST_SECONDARY, ""),
                ): str,
            }
        )

    async def async_step_reauth(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle configuration by re-authentication."""
        return self.async_show_form(step_id="user", data_schema=self.data_schema)

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=self.data_schema)

        errors = {}
        host_secondary = user_input.get(CONF_HOST_SECONDARY) or None
        try:
            self.aio_livisi = await self._try_connect(
                user_input[CONF_HOST], host_secondary, user_input[CONF_PASSWORD]
            )
        except WrongCredentialException:
            errors["base"] = "wrong_password"
        except IncorrectIpAddressException:
            errors["base"] = "wrong_ip_address"
        except (ShcUnreachableException, ErrorCodeException):
            errors["base"] = "cannot_connect"
        else:
            try:
                if self.aio_livisi.controller:
                    data = {
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    }
                    if host_secondary:
                        data[CONF_HOST_SECONDARY] = host_secondary
                    return await self.create_entity(data, self.aio_livisi.controller)
            finally:
                await self.aio_livisi.close()

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=self.data_schema, errors=errors
        )

    async def _try_connect(
        self, host: str, host_secondary: str | None, password: str
    ) -> LivisiConnection:
        """Try connecting to primary host, then secondary if primary fails."""
        try:
            return await livisi_connect(host, password)
        except WrongCredentialException:
            raise
        except _CONNECT_ERRORS as exc:
            if host_secondary is None:
                raise
            LOGGER.debug(
                "Primary host %s unreachable during config flow, trying secondary %s: %s",
                host,
                host_secondary,
                exc,
            )

        # Primary failed with connectivity error — try secondary
        try:
            conn = await livisi_connect(host_secondary, password)
            LOGGER.info(
                "Config flow: connected via secondary host %s (primary %s unreachable)",
                host_secondary,
                host,
            )
            return conn
        except WrongCredentialException:
            raise
        except _CONNECT_ERRORS as exc:
            # Both hosts failed — raise a generic ShcUnreachableException
            raise ShcUnreachableException(
                f"Neither {host} nor {host_secondary} is reachable."
            ) from exc

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
