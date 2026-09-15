"""Config flow for FortiOS-KD."""

from typing import Any

from aiohttp import ClientError, ClientResponseError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FortiOSApi
from .const import (
    CONF_INCLUDE_UNASSIGNED_SSIDS,
    CONF_MASK_AP_NAMES,
    CONF_MASK_CLIENT_HOSTNAMES,
    CONF_MASK_CLIENT_MACS,
    CONF_MASK_SERIAL_NUMBERS,
    CONF_MASK_SSIDS,
    CONF_MASK_VLAN_IDS,
    DEFAULT_INCLUDE_UNASSIGNED_SSIDS,
    DEFAULT_MASK_AP_NAMES,
    DEFAULT_MASK_CLIENT_HOSTNAMES,
    DEFAULT_MASK_CLIENT_MACS,
    DEFAULT_MASK_SERIAL_NUMBERS,
    DEFAULT_MASK_SSIDS,
    DEFAULT_MASK_VLAN_IDS,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): selector.TextSelector(),
        vol.Required(CONF_PORT): selector.NumberSelector(),
        vol.Required(CONF_API_KEY): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Optional(
            CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_INCLUDE_UNASSIGNED_SSIDS,
            default=DEFAULT_INCLUDE_UNASSIGNED_SSIDS,
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_MASK_SERIAL_NUMBERS,
            default=DEFAULT_MASK_SERIAL_NUMBERS,
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_MASK_SSIDS,
            default=DEFAULT_MASK_SSIDS,
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_MASK_CLIENT_MACS,
            default=DEFAULT_MASK_CLIENT_MACS,
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_MASK_CLIENT_HOSTNAMES,
            default=DEFAULT_MASK_CLIENT_HOSTNAMES,
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_MASK_VLAN_IDS,
            default=DEFAULT_MASK_VLAN_IDS,
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_MASK_AP_NAMES,
            default=DEFAULT_MASK_AP_NAMES,
        ): selector.BooleanSelector(),
    }
)


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate invalid authentication."""


async def async_validate_input(
    hass: HomeAssistant,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Validate the connection and return FortiGate status."""
    client = FortiOSApi(
        async_get_clientsession(hass),
        data[CONF_HOST],
        int(data[CONF_PORT]),
        data[CONF_API_KEY],
        data[CONF_VERIFY_SSL],
    )

    try:
        return await client.async_initialize()
    except ClientResponseError as err:
        if err.status in (401, 403):
            raise InvalidAuth from err
        raise CannotConnect from err
    except (ClientError, TimeoutError, TypeError, ValueError) as err:
        raise CannotConnect from err


class FortiOSKDConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FortiOS-KD."""

    VERSION = 1

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit an existing FortiGate configuration."""
        entry = self._get_reconfigure_entry()
        stored_data = self.hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
        status = stored_data.get("status", {})
        version = status.get("version", "Unavailable")
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip().lower()
            user_input[CONF_HOST] = host
            user_input[CONF_PORT] = int(user_input[CONF_PORT])

            await self.async_set_unique_id(host)
            self._abort_if_unique_id_mismatch()

            try:
                await async_validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    title=f"{host}:{user_input[CONF_PORT]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or entry.data
            ),
            errors=errors,
            description_placeholders={"version": str(version)},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip().lower()
            user_input[CONF_HOST] = host
            user_input[CONF_PORT] = int(user_input[CONF_PORT])

            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            try:
                await async_validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"{host}:{user_input[CONF_PORT]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
