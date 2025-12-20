"""August Access Lock Codes Sensor."""

from collections.abc import Callable, Iterable
from datetime import datetime
from enum import StrEnum
import logging
from uuid import UUID

from seam.routes.models import (
    AccessCode as SeamAccessCode,
    SeamEvent,
    UnmanagedAccessCode,
)

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AugustAccessConfigEntry
from .api import EventHandler, SeamAPI
from .const import ACCESS_CODE_STATUS, AUGUST_DOMAIN, EventType
from .models import AccessCode
from .util import get_august_device_id

_LOGGER = logging.getLogger(__name__)


class SensorType(StrEnum):
    """Hold sensor type for base class."""

    MANAGED = "managed"
    UNMANAGED = "unmanaged"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AugustAccessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup the sensors for the mapped entities."""
    api: SeamAPI = config_entry.runtime_data
    dev_reg: dr.DeviceRegistry = dr.async_get(hass)
    for device_id in api.device_map:
        if device := dev_reg.async_get_device(identifiers={(AUGUST_DOMAIN, device_id)}):
            if api.get_seam_device(api.get_seam_device_id(device_id)):
                async_add_entities(
                    [AccessCodeSensor(hass, api, device)],
                    update_before_add=True,
                )


class AccessCodeSensor(SensorEntity):
    """Representation of an August Access Lock Codes Sensor."""

    _listener_handle_unload: Callable | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        api: SeamAPI,
        august_device: DeviceEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__()
        seam_id = api.get_seam_device_id(
            august_device_id=get_august_device_id(august_device)
        )
        if seam_id is None:
            raise HomeAssistantError(
                f"Unable to find seam device id for august device_id {get_august_device_id(august_device)}"
            )
        self._seam_id: str = seam_id
        self.should_poll = False
        self._api: SeamAPI = api
        self._attr_unique_id = f"august_access_{self._seam_id}"
        self._attr_icon = "mdi:numeric"
        self._attr_device_info = {"identifiers": august_device.identifiers}
        self._attr_name = f"{august_device.name} Access Codes"
        self._attr_state_class = SensorStateClass.TOTAL
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, self._attr_name, hass=hass
        )
        event_handler: EventHandler = EventHandler(
            self._seam_id, EventType.ACCESS_CODE_EVENT(), self._update
        )
        self._api.add_listener_handler(event_handler)

    async def async_update(self) -> None:
        """To be called by the intital open."""
        return await self._update()

    async def _update(self, event: SeamEvent | None = None) -> None:
        if event and self._seam_id != event.device_id:
            raise HomeAssistantError(
                f"Received event with id {event.device_id} for {self._seam_id}"
            )
        self._attr_available = event is None or (
            event.event_type not in EventType.DEVICE_NOT_AVAILIBILE_EVENTS()
            and event.event_type in EventType.DEVICE_AVAILIBILE_EVENTS()
        )

        if event is None or event in EventType.ACCESS_CODE_MANAGED_EVENT():
            managed_ac: list[SeamAccessCode] = await self._api.managed_access_codes(
                self._seam_id
            )

            if not hasattr(self, "_attr_extra_state_attributes"):
                self._attr_extra_state_attributes = {}

            self._attr_extra_state_attributes["managed_access_codes"] = (
                _map_access_codes(managed_ac)
            )

        if event is None or event in EventType.ACCESS_CODE_UNMANAGED_EVENT():
            unmanaged_ac: list[
                UnmanagedAccessCode
            ] = await self._api.unmanaged_access_codes(self._seam_id)
            if not hasattr(self, "_attr_extra_state_attributes"):
                self._attr_extra_state_attributes = {}

            self._attr_extra_state_attributes["unmanaged_access_codes"] = (
                _map_access_codes(unmanaged_ac)
            )

        self._attr_native_value = len(
            self._attr_extra_state_attributes["managed_access_codes"]
        ) + len(self._attr_extra_state_attributes["unmanaged_access_codes"])
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Unload the sensor."""
        if self._listener_handle_unload:
            self._listener_handle_unload()


def _map_access_codes(
    access_codes: Iterable[UnmanagedAccessCode | SeamAccessCode],
) -> list[AccessCode]:
    def covert(code: UnmanagedAccessCode | SeamAccessCode) -> AccessCode:
        new_code: AccessCode = AccessCode(
            access_code_id=UUID(code.access_code_id),
            user_name=code.name,
            status=ACCESS_CODE_STATUS(code.status),
            access_code=code.code,
            errors=code.errors,
            warnings=code.warnings,
        )
        if code.type == "time_bound":
            new_code.starts_at = datetime.fromisoformat(code.starts_at)
            new_code.ends_at = datetime.fromisoformat(code.ends_at)
        new_code.is_managed = isinstance(code, SeamAccessCode)
        return new_code

    return [covert(code) for code in access_codes]
