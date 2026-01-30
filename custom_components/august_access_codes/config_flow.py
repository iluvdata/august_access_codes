"""Config flow for Seam API."""

from functools import partial
import logging
from typing import Any

from seam import Seam
from seam.auth import SeamInvalidTokenError
from seam.exceptions import SeamHttpUnauthorizedError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_USER,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.selector import TextSelector

from . import AugustAccessConfigEntry
from .const import (
    AUGUST_DOMAIN,
    DOMAIN,
    ERROR_AUGUST_INTEGRATION_MISSING,
    ERROR_INVALID_API_KEY,
    REPO_CONF_URL,
    SEAM_URL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): TextSelector()})


class AugustAccessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for August Access."""

    VERSION = 1
    MINOR_VERSION = 1
    seam: Seam

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # check if the core august integration is loaded
        entries: list = self.hass.config_entries.async_loaded_entries(AUGUST_DOMAIN)
        if not entries:
            return self.async_abort(reason=ERROR_AUGUST_INTEGRATION_MISSING)

        errors: dict[str, str] = {}
        if user_input:
            try:
                self.seam = await self.hass.async_add_executor_job(
                    partial(Seam.from_api_key, api_key=user_input[CONF_API_KEY])
                )
                if workspace := await self.hass.async_add_executor_job(
                    self.seam.workspaces.get
                ):
                    if self.source == SOURCE_USER:
                        await self.async_set_unique_id(workspace.workspace_id)
                        self._abort_if_unique_id_configured()
                        return self.async_create_entry(
                            title=f"Seam Workspace: {workspace.name}", data=user_input
                        )
                    if self.source == SOURCE_REAUTH:
                        entry: AugustAccessConfigEntry = self._get_reauth_entry()
                        if entry.unique_id != workspace.workspace_id:
                            return self.async_abort(reason="workspace_mismatch")
                        return self.async_update_reload_and_abort(
                            entry,
                            title=f"Seam Workspace: {workspace.name}",
                            data=user_input,
                        )
                else:
                    errors[CONF_API_KEY] = ERROR_INVALID_API_KEY

            except (SeamHttpUnauthorizedError, SeamInvalidTokenError) as ex:
                _LOGGER.error("The Seam API key was not valid: %s", ex)
                errors[CONF_API_KEY] = ERROR_INVALID_API_KEY

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"url": SEAM_URL, "repo_conf_url": REPO_CONF_URL},
        )

    async def async_step_reauth(self, entry_data: dict[str, str]) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()
