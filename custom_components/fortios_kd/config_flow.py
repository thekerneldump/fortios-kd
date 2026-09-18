"""Config flow for FortiOS-KD."""

from typing import Any

from aiohttp import ClientError, ClientResponseError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, label_registry as lr, selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FortiOSApi
from .const import (
    CONF_CLIENTS_FOLLOW_AP_AREA,
    CONF_CLIENTS_FOLLOW_AP_LABELS,
    CONF_DEVICES_FOLLOW_HUB_LABELS,
    CONF_HUB_AREA_ID,
    CONF_HUB_LABEL,
    CONF_HUB_LABEL_COLOR,
    CONF_HUB_LABEL_ID,
    CONF_INCLUDE_UNASSIGNED_SSIDS,
    CONF_INHERIT_HUB_AREA,
    CONF_MASK_AP_NAMES,
    CONF_MASK_CLIENT_HOSTNAMES,
    CONF_MASK_CLIENT_MACS,
    CONF_MASK_SERIAL_NUMBERS,
    CONF_MASK_SSIDS,
    CONF_MASK_VLAN_IDS,
    CONF_MATCH_ARP_WIFI_CLIENTS,
    CONF_MOVE_DEVICES_WITH_HUB,
    CONF_NEW_HUB_AREA_NAME,
    CONF_NEW_HUB_LABEL_NAME,
    CONF_ORGANIZATION_MODE,
    CONF_REQUEST_TIMEOUT,
    CONF_SYNC_ARP_TABLE,
    DEFAULT_CLIENTS_FOLLOW_AP_AREA,
    DEFAULT_CLIENTS_FOLLOW_AP_LABELS,
    DEFAULT_DEVICES_FOLLOW_HUB_LABELS,
    DEFAULT_HUB_LABEL_COLOR,
    DEFAULT_INCLUDE_UNASSIGNED_SSIDS,
    DEFAULT_INHERIT_HUB_AREA,
    DEFAULT_MASK_AP_NAMES,
    DEFAULT_MASK_CLIENT_HOSTNAMES,
    DEFAULT_MASK_CLIENT_MACS,
    DEFAULT_MASK_SERIAL_NUMBERS,
    DEFAULT_MASK_SSIDS,
    DEFAULT_MASK_VLAN_IDS,
    DEFAULT_MATCH_ARP_WIFI_CLIENTS,
    DEFAULT_MOVE_DEVICES_WITH_HUB,
    DEFAULT_ORGANIZATION_MODE,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_SYNC_ARP_TABLE,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    ORGANIZATION_MODE_AREA,
    ORGANIZATION_MODE_BOTH,
    ORGANIZATION_MODE_LABEL,
    ORGANIZATION_MODE_NONE,
)
from .organization import FortiOSKDOrganizationManager

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
            CONF_REQUEST_TIMEOUT,
            default=DEFAULT_REQUEST_TIMEOUT,
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=5,
                max=300,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="seconds",
            )
        ),
        vol.Optional(
            CONF_INCLUDE_UNASSIGNED_SSIDS,
            default=DEFAULT_INCLUDE_UNASSIGNED_SSIDS,
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_SYNC_ARP_TABLE,
            default=DEFAULT_SYNC_ARP_TABLE,
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_MATCH_ARP_WIFI_CLIENTS,
            default=DEFAULT_MATCH_ARP_WIFI_CLIENTS,
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_ORGANIZATION_MODE,
            default=DEFAULT_ORGANIZATION_MODE,
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(
                        value=ORGANIZATION_MODE_NONE,
                        label="Do not organize devices",
                    ),
                    selector.SelectOptionDict(
                        value=ORGANIZATION_MODE_AREA,
                        label="Use an area",
                    ),
                    selector.SelectOptionDict(
                        value=ORGANIZATION_MODE_LABEL,
                        label="Use a label",
                    ),
                    selector.SelectOptionDict(
                        value=ORGANIZATION_MODE_BOTH,
                        label="Use an area and a label",
                    ),
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
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

AREA_ORGANIZATION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HUB_AREA_ID): selector.AreaSelector(),
        vol.Optional(CONF_NEW_HUB_AREA_NAME): selector.TextSelector(),
        vol.Optional(
            CONF_INHERIT_HUB_AREA,
            default=DEFAULT_INHERIT_HUB_AREA,
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_MOVE_DEVICES_WITH_HUB,
            default=DEFAULT_MOVE_DEVICES_WITH_HUB,
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_CLIENTS_FOLLOW_AP_AREA,
            default=DEFAULT_CLIENTS_FOLLOW_AP_AREA,
        ): selector.BooleanSelector(),
    }
)

LABEL_ORGANIZATION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HUB_LABEL_ID): selector.LabelSelector(),
        vol.Optional(CONF_NEW_HUB_LABEL_NAME): selector.TextSelector(),
        vol.Optional(
            CONF_HUB_LABEL_COLOR,
            default=DEFAULT_HUB_LABEL_COLOR,
        ): selector.ColorRGBSelector(),
        vol.Optional(
            CONF_CLIENTS_FOLLOW_AP_LABELS,
            default=DEFAULT_CLIENTS_FOLLOW_AP_LABELS,
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_DEVICES_FOLLOW_HUB_LABELS,
            default=DEFAULT_DEVICES_FOLLOW_HUB_LABELS,
        ): selector.BooleanSelector(),
    }
)

AREA_ORGANIZATION_KEYS = {
    CONF_HUB_AREA_ID,
    CONF_NEW_HUB_AREA_NAME,
    CONF_INHERIT_HUB_AREA,
    CONF_MOVE_DEVICES_WITH_HUB,
    CONF_CLIENTS_FOLLOW_AP_AREA,
}
LABEL_ORGANIZATION_KEYS = {
    CONF_HUB_LABEL,
    CONF_HUB_LABEL_ID,
    CONF_NEW_HUB_LABEL_NAME,
    CONF_HUB_LABEL_COLOR,
    CONF_CLIENTS_FOLLOW_AP_LABELS,
    CONF_DEVICES_FOLLOW_HUB_LABELS,
}


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate invalid authentication."""


def _rgb_to_hex(value: Any) -> str | None:
    """Convert a selector RGB list to a label-registry hex color."""
    if not isinstance(value, list) or len(value) != 3:
        return None
    if not all(isinstance(channel, int) and 0 <= channel <= 255 for channel in value):
        return None
    return "#{:02X}{:02X}{:02X}".format(*value)


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
        int(data[CONF_REQUEST_TIMEOUT]),
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

    _pending_data: dict[str, Any]

    def _validate_area(
        self,
        user_input: dict[str, Any],
        errors: dict[str, str],
    ) -> None:
        """Validate and normalize area organization settings."""
        area_id = user_input.get(CONF_HUB_AREA_ID)
        new_area_name = str(user_input.get(CONF_NEW_HUB_AREA_NAME, "")).strip()
        user_input[CONF_NEW_HUB_AREA_NAME] = new_area_name
        if not area_id and not new_area_name:
            errors[CONF_HUB_AREA_ID] = "area_required"
        elif (
            area_id
            and not new_area_name
            and ar.async_get(self.hass).async_get_area(area_id) is None
        ):
            errors[CONF_HUB_AREA_ID] = "invalid_area"

    def _validate_label(
        self,
        user_input: dict[str, Any],
        errors: dict[str, str],
    ) -> None:
        """Validate and normalize label organization settings."""
        label_id = user_input.get(CONF_HUB_LABEL_ID)
        new_label_name = str(user_input.get(CONF_NEW_HUB_LABEL_NAME, "")).strip()
        user_input[CONF_NEW_HUB_LABEL_NAME] = new_label_name
        if not label_id and not new_label_name:
            errors[CONF_HUB_LABEL_ID] = "label_required"
        elif (
            label_id
            and not new_label_name
            and lr.async_get(self.hass).async_get_label(label_id) is None
        ):
            errors[CONF_HUB_LABEL_ID] = "invalid_label"

    def _resolve_new_area(self, user_input: dict[str, Any]) -> None:
        """Create or reuse a typed area name and store its area ID."""
        new_area_name = user_input.pop(CONF_NEW_HUB_AREA_NAME, "")
        if new_area_name:
            area = ar.async_get(self.hass).async_get_or_create(new_area_name)
            user_input[CONF_HUB_AREA_ID] = area.id

    def _resolve_new_label(self, user_input: dict[str, Any]) -> None:
        """Create or reuse a typed label name and store its label ID."""
        new_label_name = user_input.pop(CONF_NEW_HUB_LABEL_NAME, "")
        if new_label_name:
            label_registry = lr.async_get(self.hass)
            label = label_registry.async_get_label_by_name(new_label_name)
            if label is None:
                label = label_registry.async_create(
                    new_label_name,
                    color=_rgb_to_hex(user_input.get(CONF_HUB_LABEL_COLOR)),
                )
            user_input[CONF_HUB_LABEL_ID] = label.label_id
        user_input.pop(CONF_HUB_LABEL, None)

    def _organization_suggested_values(self, data: dict[str, Any]) -> dict[str, Any]:
        """Return settings with legacy label names represented by label IDs."""
        suggested = dict(data)
        if CONF_HUB_LABEL_ID not in suggested:
            label_name = suggested.get(CONF_HUB_LABEL)
            if isinstance(label_name, str):
                label = lr.async_get(self.hass).async_get_label_by_name(label_name)
                if label is not None:
                    suggested[CONF_HUB_LABEL_ID] = label.label_id
        return suggested

    def _clean_organization_data(self, data: dict[str, Any]) -> None:
        """Remove settings that do not apply to the selected organization mode."""
        mode = data[CONF_ORGANIZATION_MODE]
        if mode not in (ORGANIZATION_MODE_AREA, ORGANIZATION_MODE_BOTH):
            for key in AREA_ORGANIZATION_KEYS:
                data.pop(key, None)
        if mode not in (ORGANIZATION_MODE_LABEL, ORGANIZATION_MODE_BOTH):
            for key in LABEL_ORGANIZATION_KEYS:
                data.pop(key, None)

    async def _async_finish_configuration(self) -> ConfigFlowResult:
        """Create or update the config entry after organization choices."""
        self._clean_organization_data(self._pending_data)
        host = self._pending_data[CONF_HOST]
        port = self._pending_data[CONF_PORT]

        if self.context["source"] != config_entries.SOURCE_RECONFIGURE:
            return self.async_create_entry(
                title=f"{host}:{port}",
                data=self._pending_data,
            )

        entry = self._get_reconfigure_entry()
        stored_data = self.hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
        organization_manager = stored_data.get("organization_manager")
        if isinstance(organization_manager, FortiOSKDOrganizationManager):
            organization_manager.reconfigure(self._pending_data)
        return self.async_update_reload_and_abort(
            entry,
            title=f"{host}:{port}",
            data=self._pending_data,
        )

    async def _async_continue_organization(self) -> ConfigFlowResult:
        """Open the relevant organization step or finish the flow."""
        mode = self._pending_data[CONF_ORGANIZATION_MODE]
        if mode in (ORGANIZATION_MODE_AREA, ORGANIZATION_MODE_BOTH):
            return await self.async_step_area_organization()
        if mode == ORGANIZATION_MODE_LABEL:
            return await self.async_step_label_organization()
        return await self._async_finish_configuration()

    async def async_step_area_organization(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure optional area-based organization."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._validate_area(user_input, errors)
            if not errors:
                self._pending_data.update(user_input)
                self._resolve_new_area(self._pending_data)
                if self._pending_data[CONF_ORGANIZATION_MODE] == ORGANIZATION_MODE_BOTH:
                    return await self.async_step_label_organization()
                return await self._async_finish_configuration()

        suggested = dict(self._pending_data)
        if user_input is not None:
            suggested.update(user_input)
        return self.async_show_form(
            step_id="area_organization",
            data_schema=self.add_suggested_values_to_schema(
                AREA_ORGANIZATION_SCHEMA,
                suggested,
            ),
            errors=errors,
        )

    async def async_step_label_organization(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure optional label-based organization."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._validate_label(user_input, errors)
            if not errors:
                self._pending_data.update(user_input)
                self._resolve_new_label(self._pending_data)
                return await self._async_finish_configuration()

        suggested = self._organization_suggested_values(self._pending_data)
        if user_input is not None:
            suggested.update(user_input)
        return self.async_show_form(
            step_id="label_organization",
            data_schema=self.add_suggested_values_to_schema(
                LABEL_ORGANIZATION_SCHEMA,
                suggested,
            ),
            errors=errors,
        )

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
            user_input[CONF_REQUEST_TIMEOUT] = int(user_input[CONF_REQUEST_TIMEOUT])
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_mismatch()

            try:
                await async_validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                self._pending_data = dict(entry.data)
                self._pending_data.update(user_input)
                return await self._async_continue_organization()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                self._organization_suggested_values(user_input or dict(entry.data)),
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
            user_input[CONF_REQUEST_TIMEOUT] = int(user_input[CONF_REQUEST_TIMEOUT])
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            try:
                await async_validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                self._pending_data = user_input
                return await self._async_continue_organization()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
