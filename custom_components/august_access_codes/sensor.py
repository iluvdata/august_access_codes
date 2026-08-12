"""August Access Lock Codes Sensor."""

from collections.abc import Callable

from homeassistant.components.sensor import SensorEntity, SensorStateClass
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
            AccessCodeSensor(hass, coordinator)
            for coordinator in config_entry.runtime_data.values()
        ]
    )


class AccessCodeSensor(CoordinatorEntity[AccessCodeCoordinator], SensorEntity):
    """Representation of an August Access Lock Codes Sensor."""

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
        self._attr_icon = "mdi:numeric"
        self.device_entry = get_device_entry(
            hass, coordinator.august_lock_id, coordinator.serial_number
        )
        self._attr_translation_key = "access_codes"
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> int | None:  # noqa: D102
        return len(self.coordinator.data.managed_access_codes) + len(
            self.coordinator.data.unmanaged_access_codes
        )

    @property
    def extra_state_attributes(self):  # noqa: D102
        return self.coordinator.data.todict()
