"""Constants for august_access integration."""

from datetime import datetime
from enum import IntFlag, StrEnum
from typing import Any

import voluptuous as vol

from homeassistant.components.august import DOMAIN as AUGUST_DOMAIN

# pylint: disable-next=hass-component-root-import
from homeassistant.components.yalexs_ble.const import DOMAIN as YALE_BLE_DOMAIN
from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_API_KEY,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import TextSelector

DOMAIN = "august_access_codes"

SEAM_URL = "https://console.seam.co/"
AUGUST_LOCK_TYPE = "august_lock"
AUGUST_PROVIDER = "august"
CONF_ACCOUNT_ID = "account_id"
CONF_ACCESS_CODE_ID = "access_code_id"

WEBVIEW_CALLBACK_PATH = "/auth/august_access/callback"
WEBVIEW_CALLBACK_NAME = "auth:august_access:callback"

ERROR_INVALID_API_KEY = "seam_api_key_invalid"
ERROR_AUGUST_ACCOUNT_MISSING = "august_account_missing"
ERROR_ACCOUNT_NOT_CONNECTED = "account_not_connected"
ERROR_AUGUST_INTEGRATION_MISSING = "august_integration_missing"

REPO_CONF_URL = (
    "https://github.com/iluvdata/august_access_codes?tab=readme-ov-file#configuration"
)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): TextSelector()})


class ACCESS_CODE_STATUS(StrEnum):
    """Access Code Status Enum."""

    SETTING = "setting"
    SET = "set"
    UNSET = "unset"
    REMOVING = "removing"
    UNKNOWN = "unknown"


def _verify_datetimes(data: dict[str, Any]) -> dict[str, Any]:
    start = data.get("start_time")
    end = data.get("stop_time")
    if (start is not None and end is None) or (end is not None and start is None):
        raise vol.Invalid("If specifying times both entries are required.")
    if start is not None:
        if data["stop_time"] < datetime.now():
            raise vol.Invalid("End time must be in the future.")
        if data["start_time"] > data["stop_time"]:
            raise vol.Invalid("Start time must be before end time.")
    return data


def _verify_target(data: dict[str, Any]) -> dict[str, Any]:
    if ATTR_DEVICE_ID not in data and ATTR_ENTITY_ID not in data:
        raise vol.Invalid("No targets were specified")
    if entity := data.get(ATTR_ENTITY_ID):
        if len(entity) > 1:
            raise vol.Invalid("Only on entity or device can be specified.")
        data[ATTR_ENTITY_ID] = data[ATTR_ENTITY_ID].pop()
        return data
    device = data[ATTR_DEVICE_ID]
    if len(device) > 1:
        raise vol.Invalid("Only on entity or device can be specified.")
    data[ATTR_DEVICE_ID] = data[ATTR_DEVICE_ID].pop()
    return data


MODIFY_SERVICE_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required("access_code_id"): cv.string,
            vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
            vol.Optional("name"): cv.string,
            vol.Optional("code"): vol.All(int, vol.Range(0, 99999999)),
            vol.Optional("start_time"): cv.datetime,
            vol.Optional("stop_time"): cv.datetime,
        },
        _verify_datetimes,
    )
)

CREATE_SERVICE_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Optional(ATTR_ENTITY_ID): cv.ensure_list,
            vol.Optional(ATTR_DEVICE_ID): cv.ensure_list,
            vol.Required("name"): cv.string,
            vol.Required("code"): vol.Msg(
                cv.matches_regex(r"^\d{4,8}$"), "should be 4 to 8 digits"
            ),
            vol.Optional("start_time"): cv.datetime,
            vol.Optional("stop_time"): cv.datetime,
        },
        _verify_datetimes,
        _verify_target,
    )
)

DELETE_SERVICE_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required("access_code_id"): cv.string,
            vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        }
    )
)


class EventType(StrEnum):
    """Seam Event Type Enum."""

    DEVICE_REMOVED = "device.removed"
    DEVICE_DELETED = "device.deleted"
    DEVICE_CONNECTION = "device.connected"
    DEVICE_CONNECTION_STABILIZED = "device.connection_stabilized"
    DEVICE_DISCONNECTED = "device.disconnected"
    DEVICE_CONNECTION_FLAKY = "device.connection_became_flaky"
    DEVICE_ADDED = "device.added"
    ACCESS_CODE_CREATED = "access_code.created"
    ACCESS_CODE_CHANGED = "access_code.changed"
    ACCESS_CODE_SCHEDULED_ON_DEVICE = "access_code.scheduled_on_device"
    ACCESS_CODE_SET_ON_DEVUCE = "access_code.set_on_device"
    ACCESS_CODE_REMOVED_FROM_DEVICE = "access_code.removed_from_device"
    ACCESS_CODE_DELAY_IN_SETTING_ON_DEVICE = "access_code.delay_in_setting_on_device"
    ACCESS_CODE_FAILED_TO_SET_ON_DEVICE = "access_code.failed_to_set_on_device"
    ACCESS_CODE_DELETE = "access_code.deleted"
    ACCESS_CODE_DELAY_IN_REMOVING_FROM_DEVICE = (
        "access_code.delay_in_removing_from_device"
    )
    ACCESS_CODE_FAILED_TO_REMOVE_FROM_DEVICE = (
        "access_code.failed_to_remove_from_device"
    )
    ACCESS_CODE_MODFIED_EXTERNAL_TO_SEAM = "access_code.modified_external_to_seam"
    ACCESS_CODE_DELETED_EXTERNAL_TO_SEAM = "access_code.deleted_external_to_seam"
    ACCESS_CODE_UMANANAGED_CONVERTED_TO_MANAGED = (
        "access_code.unmanaged.converted_to_managed"
    )
    ACCESS_CODE_UNMANAGED_FAILED_TO_CONVERT_TO_MANAGED = (
        "access_code.unmanaged.failed_to_convert_to_managed"
    )
    ACCESS_CODE_UNMANAGED_CREATED = "access_code.unmanaged.created"
    ACCESS_CODE_UNMANAGED_REMOVED = "access_code.unmanaged.removed"

    def __or__(self, other):
        """Allow | use."""
        if isinstance(other, set):
            return {self} | other
        if isinstance(other, EventType):
            return {self, other}
        raise TypeError

    def __ror__(self, other):
        """Allow | use."""
        if isinstance(other, set):
            return other | {self}
        if isinstance(other, EventType):
            return {other, self}
        raise TypeError

    @classmethod
    def ALL(cls) -> list["EventType"]:
        """Get all events."""
        return list(cls)

    @classmethod
    def DEVICE_REMOVE_EVENTS(cls) -> set["EventType"]:
        """Device removal events."""
        return cls.DEVICE_DELETED | cls.DEVICE_REMOVED

    @classmethod
    def DEVICE_AVAILIBILE_EVENTS(cls) -> set["EventType"]:
        """Device available events."""
        return cls.DEVICE_CONNECTION | cls.DEVICE_CONNECTION_STABILIZED

    @classmethod
    def DEVICE_NOT_AVAILIBILE_EVENTS(cls) -> set["EventType"]:
        """Device not available events."""
        return cls.DEVICE_CONNECTION_FLAKY | cls.DEVICE_DISCONNECTED

    @classmethod
    def DEVICE_AVAILIBILITY_EVENTS(cls) -> set["EventType"]:
        """All device availibility events."""
        return cls.DEVICE_AVAILIBILE_EVENTS() | cls.DEVICE_NOT_AVAILIBILE_EVENTS()

    @classmethod
    def ACCESS_CODE_NEW_EVENT(cls) -> set["EventType"]:
        """New access code."""
        return cls.ACCESS_CODE_CREATED | cls.ACCESS_CODE_UNMANAGED_CREATED

    @classmethod
    def ACCESS_CODE_REMOVED_EVENT(cls) -> set["EventType"]:
        """Access code removed."""
        return cls.ACCESS_CODE_DELETE | cls.ACCESS_CODE_DELETED_EXTERNAL_TO_SEAM

    @classmethod
    def ACCESS_CODE_MODIFIED_EVENT(cls) -> set["EventType"]:
        """Access code modified."""
        return cls.ACCESS_CODE_CHANGED | cls.ACCESS_CODE_MODFIED_EXTERNAL_TO_SEAM

    @classmethod
    def ACCESS_CODE_DEVICE_EVENT(cls) -> set["EventType"]:
        """Access code on device events."""
        return (
            cls.ACCESS_CODE_SCHEDULED_ON_DEVICE
            | cls.ACCESS_CODE_SET_ON_DEVUCE
            | cls.ACCESS_CODE_REMOVED_FROM_DEVICE
            | cls.ACCESS_CODE_DELAY_IN_SETTING_ON_DEVICE
            | cls.ACCESS_CODE_FAILED_TO_SET_ON_DEVICE
            | cls.ACCESS_CODE_DELAY_IN_REMOVING_FROM_DEVICE
            | cls.ACCESS_CODE_FAILED_TO_REMOVE_FROM_DEVICE
        )

    @classmethod
    def ACCESS_CODE_MANAGED_EVENT(cls) -> set["EventType"]:
        """Managed access code Events."""
        return (
            cls.ACCESS_CODE_CREATED
            | cls.ACCESS_CODE_MODIFIED_EVENT()
            | cls.ACCESS_CODE_REMOVED_EVENT()
            | cls.ACCESS_CODE_DEVICE_EVENT()
        )

    @classmethod
    def ACCESS_CODE_UNMANAGED_EVENT(cls) -> set["EventType"]:
        """Unmanaged access code events."""
        return (
            cls.ACCESS_CODE_UMANANAGED_CONVERTED_TO_MANAGED
            | cls.ACCESS_CODE_UNMANAGED_FAILED_TO_CONVERT_TO_MANAGED
            | cls.ACCESS_CODE_UNMANAGED_CREATED
            | cls.ACCESS_CODE_UNMANAGED_REMOVED
        )

    @classmethod
    def ACCESS_CODE_EVENT(cls) -> list["EventType"]:
        """Get a list of all access code events."""
        access_codes_filter = filter(lambda x: x.startswith("acceess_code"), cls.ALL())
        return list(access_codes_filter)


class AugustEntityFeature(IntFlag):
    """Feature codes for august access."""

    ACCESS_CODES = 1
    PROGRAM_CODES = 2


__all__ = ["AUGUST_DOMAIN", "YALE_BLE_DOMAIN"]
