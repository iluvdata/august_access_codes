"""Access Codes Coordinator."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
import logging

from seam.exceptions import SeamHttpApiError
from seam.routes.models import (
    AccessCode as SeamAccessCode,
    Device as SeamDevice,
    SeamEvent,
    UnmanagedAccessCode,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import EventHandler, SeamAPI
from .const import SCAN_INTERVAL, EventType
from .models import AccessCode

_LOGGER = logging.getLogger(__name__)


@dataclass
class AccessCodeData:
    """Dataclass to hold the access codes."""

    managed_access_codes: dict[str, AccessCode]
    unmanaged_access_codes: dict[str, AccessCode]

    def todict(self) -> dict[str, list[AccessCode]]:
        """Json compatible view."""
        return {
            "managed_access_codes": list(self.managed_access_codes.values()),
            "unmanaged_access_codes": list(self.unmanaged_access_codes.values()),
        }


class AccessCodeCoordinator(DataUpdateCoordinator[AccessCodeData]):
    """Access Code Coordinator."""

    _remove_event_listener: Callable

    def __init__(
        self, hass: HomeAssistant, api: SeamAPI, seam_device: SeamDevice
    ) -> None:
        """Initialize a coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"aac_coordinator_{seam_device.device_id}",
            update_interval=SCAN_INTERVAL,
        )
        self.api: SeamAPI = api
        self.seam_id = seam_device.device_id
        self.serial_number = seam_device.properties.serial_number
        self.august_lock_id = seam_device.properties.august_metadata.lock_id

    async def _async_setup(self) -> None:
        event_handler: EventHandler = EventHandler(
            self.seam_id, EventType.ACCESS_CODE_EVENT(), self._process_event
        )
        self._remove_event_listener = self.api.add_listener_handler(event_handler)

    async def async_shutdown(self):
        """Added to remove listener."""
        if hasattr(self, "_remove_event_listener"):
            self._remove_event_listener()
        await super().async_shutdown()

    async def _async_update_data(self) -> AccessCodeData:
        managed_ac: list[SeamAccessCode] = await self.api.managed_access_codes(
            self.seam_id
        )
        unmanaged_ac: list[UnmanagedAccessCode] = await self.api.unmanaged_access_codes(
            self.seam_id
        )
        return AccessCodeData(
            _map_access_codes(managed_ac), _map_access_codes(unmanaged_ac)
        )

    async def _process_event(
        self,
        event: SeamEvent | None = None,
    ) -> None:
        if event and self.seam_id != event.device_id:
            raise HomeAssistantError(
                f"Received event with id {event.device_id} for {self.seam_id}"
            )
        if event.event_type in EventType.ACCESS_CODE_MANAGED_EVENT():
            try:
                updated_code: SeamAccessCode = await self.api.get_managed_code(
                    event.access_code_id
                )
                self.data.managed_access_codes[updated_code.access_code_id] = (
                    _covert_code(updated_code)
                )
            except SeamHttpApiError:
                if event.event_type == EventType.ACCESS_CODE_REMOVED_EVENT:
                    del self.data.managed_access_codes[event.access_code_id]
            self.async_set_updated_data(self.data)

        if event.event_type in EventType.ACCESS_CODE_UNMANAGED_EVENT():
            try:
                updated_code: UnmanagedAccessCode = await self.api.get_unmanaged_code(
                    event.access_code_id
                )
                self.data.unmanaged_access_codes[updated_code.access_code_id] = (
                    _covert_code(updated_code)
                )
            except SeamHttpApiError:
                if event.event_type == EventType.ACCESS_CODE_UNMANAGED_REMOVED:
                    del self.data.unmanaged_access_codes[event.access_code_id]
            self.async_set_updated_data(self.data)


def _covert_code(code: UnmanagedAccessCode | SeamAccessCode) -> AccessCode:
    new_code: AccessCode = AccessCode(
        access_code_id=code.access_code_id,
        user_name=code.name,
        status=code.status,
        access_code=code.code,
        errors=code.errors,
        warnings=code.warnings,
    )
    if code.type == "time_bound":
        new_code.starts_at = datetime.fromisoformat(code.starts_at)
        new_code.ends_at = datetime.fromisoformat(code.ends_at)
    new_code.is_managed = isinstance(code, SeamAccessCode)
    return new_code


def _map_access_codes(
    access_codes: Iterable[UnmanagedAccessCode | SeamAccessCode],
) -> dict[str, AccessCode]:

    return {code.access_code_id: _covert_code(code) for code in access_codes}
