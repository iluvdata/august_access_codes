"""Utilities for the August Access Codes Integration."""

from homeassistant.components.august import DOMAIN as AUGUST_DOMAIN
from homeassistant.components.yalexs_ble import DOMAIN as YALEXS_BLE_DOMAIN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr


def get_device_entry(
    hass: HomeAssistant,
    august_device_id: str | None = None,
    serial_num: str | None = None,
) -> str | None:
    """Get a dev reg device_id."""
    dev_reg = dr.async_get(hass)
    if august_device_id:
        for config_entry in hass.config_entries.async_entries(AUGUST_DOMAIN):
            if device_entry := dev_reg.async_get_device_by_identifier(
                (AUGUST_DOMAIN, august_device_id), config_entry.entry_id
            ):
                return device_entry
    if serial_num:
        for config_entry in hass.config_entries.async_entries(YALEXS_BLE_DOMAIN):
            if device_entry := dev_reg.async_get_device_by_identifier(
                (YALEXS_BLE_DOMAIN, serial_num), config_entry.entry_id
            ):
                return device_entry
    return None
