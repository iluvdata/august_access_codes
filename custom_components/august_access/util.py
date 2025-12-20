"""Util functions for August Access integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import AUGUST_DOMAIN


def get_august_lock_devices(hass: HomeAssistant) -> list[dr.DeviceEntry]:
    """Get all August locks."""
    august_entries: list[ConfigEntry] = hass.config_entries.async_entries(
        AUGUST_DOMAIN, include_ignore=True, include_disabled=True
    )
    if not august_entries:
        return []
    device_registry: dr.DeviceRegistry = dr.async_get(hass)
    devices: list[dr.DeviceEntry] = []
    for august_entry in august_entries:
        devices.extend(
            [
                device_entry
                for device_entry in dr.async_entries_for_config_entry(
                    device_registry, august_entry.entry_id
                )
                if not device_entry.disabled
            ]
        )
    return devices


def get_august_device_id(device: dr.DeviceEntry) -> str:
    """Get the august device id from a Device Regisry Entry."""

    return list(device.identifiers)[0][1]


# class AugustAccessWebviewCallbackView(HomeAssistantView):
#     """Handle callback from external auth."""

#     url = WEBVIEW_CALLBACK_PATH
#     name = WEBVIEW_CALLBACK_NAME
#     requires_auth = False

#     def __init__(self, async_configure: Callable) -> None:
#         """Initiate August Access Webview Callback."""
#         self.async_configure: Callable = async_configure

#     async def get(self, request: Request):
#         """Receive authorization confirmation."""

#         # homeassistant.components.repairs.issue_handler.RepairsFlowManager
#         result = await self.async_configure(
#             flow_id=request.query["flow_id"],
#             user_input={
#                 "success": "failed" not in request.query,
#                 "webview_id": request.query["connect_webview_id"],
#             },
#         )

#         if (
#             "type" in result
#             and result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP_DONE
#         ):
#             return web_response.Response(
#                 headers={"content-type": "text/html"},
#                 text="<script>window.close()</script>Success! This window can be closed",
#             )
#         return web_response.Response(
#             headers={"content-type": "text/plain"},
#             text="Invalid flow specified.",
#             status=400,
#         )
