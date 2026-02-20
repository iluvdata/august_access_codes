"""August Access Lock Codes Binary Sensor."""

from collections.abc import Callable
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AugustAccessConfigEntry
from .const import AUGUST_DOMAIN, DOMAIN, YALE_BLE_DOMAIN
from .coordinator import AccessCodeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AugustAccessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup the sensors for the mapped entities."""
    dev_reg: dr.DeviceRegistry = dr.async_get(hass)
    entities: list[AccessCodeStatusSensor] = []
    for coordinator in config_entry.runtime_data.values():
        device: DeviceEntry = dev_reg.async_get_device(
            identifiers={(YALE_BLE_DOMAIN, coordinator.serial_number)}
        )
        if device is None:
            if not (
                device := dev_reg.async_get_device(
                    identifiers={
                        (
                            AUGUST_DOMAIN,
                            coordinator.august_lock_id,
                        )
                    }
                )
            ):
                continue
        entities.append(AccessCodeStatusSensor(coordinator, device))

    if entities:
        async_add_entities(entities)


class AccessCodeStatusSensor(
    CoordinatorEntity[AccessCodeCoordinator], BinarySensorEntity
):
    """Representation of an August Access Lock Codes Status Sensor."""

    _listener_handle_unload: Callable | None = None

    def __init__(
        self,
        coordinator: AccessCodeCoordinator,
        august_device: DeviceEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_has_entity_name = True
        self.should_poll = False
        self._attr_unique_id = f"august_access_{self.coordinator.seam_id}"
        self._attr_icon = "mdi:progress-check"
        self._attr_translation_key = "progamming_status"
        identifiers: set[tuple[str, str]] = august_device.identifiers.copy()
        identifiers.add((DOMAIN, self.coordinator.seam_id))
        self._attr_device_info = {"identifiers": identifiers}

    @property
    def is_on(self) -> bool | None:
        """Return if a code is in a status other than set."""
        for code in list(self.coordinator.data.managed_access_codes.values()) + list(
            self.coordinator.data.unmanaged_access_codes.values()
        ):
            if code.status != "set":
                return True
        return False
