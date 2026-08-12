"""August Access Lock Codes Binary Sensor."""

from collections.abc import Callable

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AugustAccessConfigEntry
from .coordinator import AccessCodeCoordinator
from .util import get_device_entry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AugustAccessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup the sensors for the mapped entities."""

    async_add_entities(
        [
            AccessCodeStatusSensor(hass, coordinator)
            for coordinator in config_entry.runtime_data.values()
        ]
    )


class AccessCodeStatusSensor(
    CoordinatorEntity[AccessCodeCoordinator], BinarySensorEntity
):
    """Representation of an August Access Lock Codes Status Sensor."""

    _listener_handle_unload: Callable | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: AccessCodeCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_has_entity_name = True
        self.should_poll = False
        self._attr_unique_id = f"august_access_{self.coordinator.seam_id}"
        self._attr_icon = "mdi:progress-check"
        self._attr_translation_key = "progamming_status"
        self.device_entry = get_device_entry(
            hass, coordinator.august_lock_id, coordinator.serial_number
        )

    @property
    def is_on(self) -> bool | None:
        """Return if a code is in a status other than set."""
        for code in list(self.coordinator.data.managed_access_codes.values()):
            if code.status != "set":
                return True
        return False
