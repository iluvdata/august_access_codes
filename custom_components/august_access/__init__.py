"""The August Access integration."""

from dataclasses import asdict
import logging
from typing import cast

from seam.exceptions import SeamHttpApiError
from seam.routes.models import AccessCode

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    Platform,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .api import SeamAPI
from .const import (
    CREATE_SERVICE_SCHEMA,
    DELETE_SERVICE_SCHEMA,
    DOMAIN,
    MODIFY_SERVICE_SCHEMA,
    AugustEntityFeature,
)
from .util import get_august_id

type AugustAccessConfigEntry = ConfigEntry[SeamAPI]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config_type: ConfigType) -> bool:
    """Setup services."""

    def _get_api(call: ServiceCall) -> SeamAPI:
        entry: AugustAccessConfigEntry | None = None
        if ATTR_ENTITY_ID in call.data:
            ent_reg: er.EntityRegistry = er.async_get(hass)
            entity: er.RegistryEntry | None = ent_reg.async_get(
                call.data[ATTR_ENTITY_ID]
            )
            if not entity:
                raise ServiceValidationError(translation_key="device_not_found")
            if entity.config_entry_id is None:
                raise ServiceValidationError(translation_key="entry_not_found")
            entry = hass.config_entries.async_get_known_entry(entity.config_entry_id)
        elif ATTR_DEVICE_ID in call.data:
            dev_reg: dr.DeviceRegistry = dr.async_get(hass)
            device: dr.DeviceEntry | None = dev_reg.async_get(call.data[ATTR_DEVICE_ID])
            if not device:
                raise ServiceValidationError(translation_key="device_not_found")
            for entry_id in device.config_entries:
                entry = hass.config_entries.async_get_known_entry(entry_id)
                if entry.domain == DOMAIN:
                    break
        elif ATTR_CONFIG_ENTRY_ID in call.data:
            entry = hass.config_entries.async_get_known_entry(
                call.data[ATTR_CONFIG_ENTRY_ID]
            )
        if not entry:
            raise ServiceValidationError("entry_not_found")
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("entry_not_loaded")
        return cast(AugustAccessConfigEntry, entry).runtime_data

    async def _create_access_code(call: ServiceCall) -> ServiceResponse:
        """Create access code service."""
        # we need the device id
        _LOGGER.debug("Create access code with: %s", call.data)
        if not (device_id := call.data.get(ATTR_DEVICE_ID)):
            if entity_id := call.data.get(ATTR_ENTITY_ID):
                ent_reg: er.EntityRegistry = er.async_get(hass)
                if not (reg_ent := ent_reg.async_get(entity_id)):
                    raise ServiceValidationError(translation_key="entity_not_found")
                device_id = reg_ent.device_id
            else:
                raise ServiceValidationError("entity_id_missing")
        if not device_id:
            raise ServiceValidationError(translation_key="device_id_missing")
        august_id = get_august_id(hass, device_id)
        if not august_id:
            raise ServiceValidationError(translation_key="device_not_found")
        august_access = _get_api(call)
        if not (seam_id := august_access.get_seam_device_id(august_id)):
            raise ServiceValidationError("seam_device_not_found")
        # Replace with the correct method to create an access code, for example:
        access_code: AccessCode = await august_access.async_create_access_code(
            seam_id,
            name=call.data["name"],
            code=call.data["code"],
            start_time=call.data.get("start_time"),
            end_time=call.data.get("stop_time"),
        )
        return asdict(access_code)

    hass.services.async_register(
        DOMAIN,
        "create_access_code",
        _create_access_code,
        CREATE_SERVICE_SCHEMA,
        SupportsResponse.OPTIONAL,
    )

    async def _modify_access_code(call: ServiceCall) -> None:
        """Modify access code service."""
        _LOGGER.debug("Got data: %s", call.data)
        if not (access_code_id := call.data.get("access_code_id")):
            raise ServiceValidationError("access_code_id_missing")
        august_access = _get_api(call)
        await august_access.async_modify_access_code(
            access_code_id,
            name=call.data.get("name"),
            code=call.data.get("code"),
            start_time=call.data.get("start_time"),
            end_time=call.data.get("stop_time"),
        )

    hass.services.async_register(
        DOMAIN, "modify_access_code", _modify_access_code, MODIFY_SERVICE_SCHEMA
    )

    async def _delete_access_code(call: ServiceCall) -> None:
        """Create access code service."""
        _LOGGER.debug("Got data: %s", call.data)
        # Replace with the correct method to create an access code, for example:
        august_access = _get_api(call)
        try:
            await august_access.async_delete_access_code(
                access_code_id=call.data["access_code_id"]
            )
        except SeamHttpApiError as ex:
            raise ServiceValidationError(
                translation_key="seam_exception",
                translation_placeholders={"msg": str(ex)},
            ) from ex

    hass.services.async_register(
        DOMAIN, "delete_access_code", _delete_access_code, DELETE_SERVICE_SCHEMA
    )

    _LOGGER.debug("Setup services: %s", hass.services.async_services_for_domain(DOMAIN))

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: AugustAccessConfigEntry
) -> bool:
    """Set up August Access from a config entry."""

    seam_api: SeamAPI = await SeamAPI.auth(hass=hass, entry=entry)

    entry.runtime_data = seam_api

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AugustAccessConfigEntry
) -> bool:
    """Unload a config entry."""
    return await entry.runtime_data.unload()


__all__ = ["AugustEntityFeature"]
