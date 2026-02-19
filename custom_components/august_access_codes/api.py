"""Api for August Access integration."""

from asyncio import gather
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from functools import partial
import logging

from aiohttp.web_request import Request
from aiohttp.web_response import Response
from seam import Seam, SeamWebhook
from seam.exceptions import SeamHttpApiError, SeamHttpUnauthorizedError
from seam.routes.models import (
    AccessCode,
    ConnectedAccount,
    Device as SeamDevice,
    SeamEvent,
    UnmanagedAccessCode,
    Webhook,
)
from svix import WebhookVerificationError

from homeassistant.components.webhook import (
    async_generate_url,
    async_register,
    async_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryError, IntegrationError
from homeassistant.util.dt import as_utc

from .const import (
    AUGUST_DOMAIN,
    AUGUST_LOCK_TYPE,
    AUGUST_PROVIDER,
    DOMAIN,
    ERROR_AUGUST_ACCOUNT_MISSING,
    YALE_BLE_DOMAIN,
    AugustEntityFeature,
    EventType,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class EventHandler:
    """Event Handler Data Class."""

    seam_device_id: str | None
    event_types: list[EventType] | set[EventType]
    handler: Callable[[SeamEvent | None], Awaitable[None]]


type SeamDeviceID = str


class MapType(StrEnum):
    """Types for the submapping."""

    AUGUST_DEVICE_ID = "device_id"
    AUGUST_SERIAL_NUM = "serial_number"
    SEAM_DEVICE = "device"


class SeamDeviceMap:
    """Map a Seam Device to August Device IDs or Serial Numbers."""

    def __init__(self) -> None:
        """Initialize the device map."""
        self._devices: Mapping[SeamDeviceID, Mapping[MapType, SeamDevice]] = {}

    def async_add(self, device: SeamDevice) -> None:
        """Add a device to the map."""
        self._devices[device.device_id] = {
            MapType.AUGUST_DEVICE_ID: device.properties.august_metadata.lock_id,
            MapType.AUGUST_SERIAL_NUM: device.properties.serial_number,
            MapType.SEAM_DEVICE: device,
        }

    def async_add_all(
        self, devices: Iterable[SeamDevice], clear_devices: bool = False
    ) -> None:
        """Add all devices to the map."""
        if clear_devices:
            self._devices = {}
        for device in devices:
            self.async_add(device)

    def async_get(self, device_id: SeamDeviceID) -> SeamDevice | None:
        """Get a device by Seam Device ID."""
        if device_map := self._devices.get(device_id):
            return device_map[MapType.SEAM_DEVICE]
        return None

    def async_get_all(self) -> Iterable[SeamDevice]:
        """Return all devices."""
        return [
            device_map[MapType.SEAM_DEVICE] for device_map in self._devices.values()
        ]

    def async_get_by_id(self, id_value: str, id_type: MapType) -> SeamDevice | None:
        """Get a device by august device id or serial number."""
        if id_type not in {MapType.AUGUST_DEVICE_ID, MapType.AUGUST_SERIAL_NUM}:
            return None
        for device_map in self._devices.values():
            if id_type in device_map and id_value == device_map[id_type]:
                return device_map[MapType.SEAM_DEVICE]
        return None

    def async_remove(self, device_id: SeamDeviceID) -> None:
        """Remove a device."""
        del self._devices[device_id]

    def async_remove_by_id(self, id_value: str, id_type: MapType) -> None:
        """Remove a device by august device id or serial number."""
        if id_type not in {MapType.AUGUST_DEVICE_ID, MapType.AUGUST_SERIAL_NUM}:
            return
        for device_id, device_map in self._devices:
            if id_type in device_map and id_value == device_map[id_type]:
                self.async_remove(device_id)
                return


class SeamAPI:
    """Handle all communication with the Seam service."""

    _hass: HomeAssistant
    _seam: Seam
    _entry: ConfigEntry
    _webhook: Webhook
    _webhook_listeners: list[EventHandler] = []
    _devices: SeamDeviceMap = SeamDeviceMap()
    entry_update_listener_unload: CALLBACK_TYPE

    @classmethod
    async def auth(cls, *, hass: HomeAssistant, entry: ConfigEntry) -> "SeamAPI":  # noqa: UP037
        """Authenticate and return an AugustAccess instance."""
        if not hass.config_entries.async_has_entries(
            AUGUST_DOMAIN, include_ignore=False, include_disabled=False
        ) or not hass.config_entries.async_has_entries(
            YALE_BLE_DOMAIN, include_ignore=False, include_disabled=False
        ):
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key=ERROR_AUGUST_ACCOUNT_MISSING
            )
        self = cls()
        self._hass = hass
        self._entry = entry
        self._seam = await hass.async_add_executor_job(
            Seam.from_api_key, self._entry.data[CONF_API_KEY]
        )
        await self._async_refresh_devices()
        # create webhook locally first
        webhook_id = f"{DOMAIN}_{self._entry.unique_id}"
        async_unregister(hass, webhook_id)
        async_register(
            self._hass,
            DOMAIN,
            f"{DOMAIN} webhook",
            webhook_id,
            self.get_webhook_handler(),
        )
        url: str = async_generate_url(hass, webhook_id)

        # Create the webhook, but first check if there are any dangling hooks.
        webhooks: list[Webhook] = await hass.async_add_executor_job(
            self._seam.webhooks.list
        )
        if len(webhooks) > 0:
            _LOGGER.warning(
                "More than one Seam webhook exists. Removing dangling webhooks"
            )
            await gather(
                *[
                    self._hass.async_add_executor_job(
                        partial(
                            self._seam.webhooks.delete, webhook_id=webhook.webhook_id
                        )
                    )
                    for webhook in webhooks
                ]
            )

        _LOGGER.debug("Creating seam webhook with url: %s", url)
        self._webhook = await hass.async_add_executor_job(
            partial(
                self._seam.webhooks.create,
                url=url,
                event_types=[event.value for event in EventType],
            ),
        )
        _LOGGER.debug("Created Seam webhook with id: %s", self._webhook.webhook_id)

        return self

    async def _get_seam_accounts(self) -> list[ConnectedAccount]:
        accounts: list[ConnectedAccount] = []
        try:
            accounts = await self._hass.async_add_executor_job(
                partial(self._seam.connected_accounts.list, search="august")
            )
            for account in accounts:
                if account.account_type != AUGUST_PROVIDER:
                    accounts.remove(account)
            if not accounts:
                raise AccountNotConnected
        except SeamHttpUnauthorizedError as ex:
            raise AugustAccessUnauthorizedError from ex
        return accounts

    async def async_create_access_code(
        self,
        seam_device_id: str,
        name: str,
        code: int,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> AccessCode:
        """Create an access code."""
        if start_time:
            start_time = as_utc(start_time)
        if end_time:
            end_time = as_utc(end_time)
        access_code: AccessCode = await self._hass.async_add_executor_job(
            partial(
                self._seam.access_codes.create,
                device_id=seam_device_id,
                name=name,
                code=str(code),
                starts_at=str(start_time) if start_time else None,
                ends_at=str(end_time) if end_time else None,
                allow_external_modification=True,
            )
        )
        await self._async_notify_listeners(seam_device_id)
        return access_code

    async def async_modify_access_code(
        self,
        access_code_id: str,
        name: str | None,
        code: int | None,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> None:
        """Modify an access code."""
        if start_time:
            start_time = as_utc(start_time)
        if end_time:
            end_time = as_utc(end_time)
        access_code: AccessCode = await self._hass.async_add_executor_job(
            partial(self._seam.access_codes.get, access_code_id=access_code_id)
        )
        await self._hass.async_add_executor_job(
            partial(
                self._seam.access_codes.update,
                access_code_id=access_code_id,
                name=name,
                code=str(code) if code else None,
                starts_at=str(start_time) if start_time else None,
                ends_at=str(end_time) if end_time else None,
            )
        )
        await self._async_notify_listeners(access_code.device_id)

    async def _raise_if_not_valid_code(self, acccess_code_id: str) -> None:
        try:
            access_code: AccessCode = await self._hass.async_add_executor_job(
                partial(self._seam.access_codes.get, access_code_id=acccess_code_id)
            )
            if not access_code.is_managed:
                raise AugustAccessError("Unable to manipulate unmanaged codes")
        except SeamHttpApiError as ex:
            raise AugustAccessError(str(ex)) from ex

    async def async_delete_access_code(self, access_code_id: str) -> None:
        """Delete an access code."""
        await self._raise_if_not_valid_code(access_code_id)
        access_code: AccessCode = await self._hass.async_add_executor_job(
            partial(self._seam.access_codes.get, access_code_id=access_code_id)
        )
        await self._hass.async_add_executor_job(
            partial(self._seam.access_codes.delete, access_code_id=access_code_id)
        )
        await self._async_notify_listeners(access_code.device_id)

    async def _async_notify_listeners(self, seam_device_id: SeamDeviceID) -> None:
        handlers = [
            handler.handler
            for handler in self._webhook_listeners
            if handler.seam_device_id == seam_device_id
        ]
        await gather(*[handler(None) for handler in handlers])

    async def managed_access_codes(self, seam_device_id: str) -> list[AccessCode]:
        """Get managed codes from the device."""
        return await self._hass.async_add_executor_job(
            partial(self._seam.access_codes.list, device_id=seam_device_id)
        )

    async def unmanaged_access_codes(
        self, seam_device_id: str
    ) -> list[UnmanagedAccessCode]:
        """Get unmanaged access codes from device."""
        return await self._hass.async_add_executor_job(
            partial(self._seam.access_codes.unmanaged.list, device_id=seam_device_id)
        )

    async def _async_refresh_devices(self) -> None:
        devices: list[SeamDevice] = await self._hass.async_add_executor_job(
            partial(
                self._seam.devices.list,
                device_type=AUGUST_LOCK_TYPE,
            )
        )
        self._devices.async_add_all(devices, True)

    def get_seam_device_features(self, seam_device_id: str) -> set[AugustEntityFeature]:
        """Get the features for a device."""
        device: SeamDevice | None = self.get_seam_device(seam_device_id)
        if device:
            features: set[AugustEntityFeature] = set()
            if "access_code" in device.capabilities_supported:
                features = features | {AugustEntityFeature.ACCESS_CODES}
                if device.can_program_online_access_codes:
                    features = features | {AugustEntityFeature.PROGRAM_CODES}
            return features
        return set()

    def get_seam_device(self, seam_device_id: SeamDeviceID) -> SeamDevice | None:
        """Get a Seam device."""
        return self._devices.async_get(seam_device_id)

    def get_seam_device_by_lock_id(self, lock_id: str) -> SeamDevice | None:
        """Get a Seam device by august device id."""
        return self._devices.async_get_by_id(lock_id, MapType.AUGUST_DEVICE_ID)

    def get_seam_device_by_serial_num(self, serial_num: str) -> SeamDevice | None:
        """Get a Seam device by august device id."""
        return self._devices.async_get_by_id(serial_num, MapType.AUGUST_SERIAL_NUM)

    @property
    def get_seam_devices(self) -> Iterable[SeamDevice]:
        """Get iterator of devices."""
        return self._devices.async_get_all()

    async def unload(self) -> bool:
        """Unload the August Access API."""
        # unregister webhook
        async_unregister(self._hass, f"{DOMAIN}_{self._entry.unique_id}")
        if hasattr(self, "_webhook"):
            try:
                await self._hass.async_add_executor_job(
                    partial(
                        self._seam.webhooks.delete, webhook_id=self._webhook.webhook_id
                    )
                )
                _LOGGER.debug(
                    "Deleted seam webhook with ID: %s", self._webhook.webhook_id
                )
            except SeamHttpApiError as ex:
                _LOGGER.warning("Failed to delete Seam webhook: %s", ex)
        return True

    def add_listener_handler(self, event_handler: EventHandler) -> Callable:
        """Add a listener to handle events."""
        self._webhook_listeners.append(event_handler)

        def async_remove_listener() -> None:
            self._webhook_listeners.remove(event_handler)

        return async_remove_listener

    def get_webhook_handler(
        self,
    ) -> Callable[[HomeAssistant, str, Request], Awaitable[Response | None]]:
        """Return the webhook handler."""

        async def handle_webhook(
            hass: HomeAssistant, webhook_id: str, request: Request
        ) -> Response | None:
            """Handle incoming webhook calls."""
            payload: str = await request.text()
            headers: dict[str, str] = dict(request.headers.items())
            try:
                webhook: SeamWebhook = SeamWebhook(self._webhook.secret)
                event: SeamEvent = webhook.verify(payload, headers)
                _LOGGER.debug("Received webhook event: %s", event)
                if event.event_type in [
                    EventType.DEVICE_ADDED,
                    EventType.DEVICE_REMOVED,
                ]:
                    # reload config entry to update devices
                    await hass.config_entries.async_reload(self._entry.entry_id)
                    return Response(status=200)
                if event.event_type == EventType.ACCESS_CODE_DELETED_EXTERNAL_TO_SEAM:
                    # Remove the access code from seam
                    await hass.async_add_executor_job(
                        partial(
                            self._seam.access_codes.delete,
                            access_code_id=event.access_code_id,
                        )
                    )
                handlers = [
                    handler.handler
                    for handler in self._webhook_listeners
                    if handler.seam_device_id == event.device_id
                    and event.event_type in handler.event_types
                ]
                await gather(*[handler(event) for handler in handlers])
            except WebhookVerificationError as ex:
                _LOGGER.error("Webhook verification failed: %s", ex)
                return Response(status=400, reason="Invalid webhook signature")
            return Response(status=200)

        return handle_webhook


class AugustAccessError(IntegrationError):
    """General exception for August Access errors."""


class WebviewNotConnected(AugustAccessError):
    """Exception for when no webview is connected."""


class AccountNotConnected(AugustAccessError):
    """Exception for when AugustAccess is not connected."""


class AugustAccessUnauthorizedError(AugustAccessError):
    """Exception for when August Access API key is invalid."""
