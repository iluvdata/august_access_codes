# August Access:  Program Lock Codes

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square&logo=homeassistantcommunitystore)](https://hacs.xyz/)
![GitHub Release](https://img.shields.io/github/v/release/iluvdata/august_access_codes)
![Dynamic JSON Badge](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Filuvdata%2Faugust_access_codes%2Frefs%2Fheads%2Fmain%2Fcustom_components%2Faugust_access_codes%2Fmanifest.json&query=%24.version&prefix=v&label=dev-version&labelColor=orange)

A service/helper integration that allows one set codes on locks using the [August Integration](https://www.home-assistant.io/integrations/august/) via the [Seam](https://www.seam.co/) platform.

Seam (currently) allows users to associate a few accounts/devices for free.  This integration is not supported by August, Seam, or Yale.

## Features
- Creates a sensor in the August device with a count of the access codes set on the current lock.
- Exposes services to create, modify, and delete access codes.

## Requirements

A secure and publically available Home Assistant either by your own means or via Home Assistant Cloud (Nabu Casa) as this integration requires "Cloud Push" update leveraging webhooks.

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&owner=iluvdata&repository=august_access_codes)

### Manual Installation
1. Download the latest release from the [GitHub Releases page](https://github.com/iluvdata/august_access_codes/releases).
2. Extract the downloaded archive.
3. Copy the `custom_components/august_access_codes` folder to your Home Assistant `custom_components` directory.
   - Example: `/config/custom_components/august_access_codes`
4. Restart Home Assistant.

## Configuration


1. Create a Seam account and API key
   1. Go to https://console.seam.co and create an account.
   2. Create a new Seam workspace following these [instructions](https://docs.seam.co/latest/core-concepts/workspaces#create-a-production-workspace). The name is not important.
   3. Associate your Yale Home or August account by navigating to the "Devices" tab and clicking "Add Device" and following the onscreen instructions to complete the OAuth process to give Seam access to your locks.
   4. Create an API Key following these [instructions](https://docs.seam.co/latest/core-concepts/authentication/api-keys#create-an-api-key).  Copy this as you are only allowed to see it once!
2. Configure the integration in Home Assistant
   
    [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=august_access_codes) 
    
    **OR**
   1. In Home Assistant, navigate to **Settings** > **Devices & Services**.
   2. Click **Add Integration**.
   3. Search for "August Access Codes" and select it.
3. Enter your Seam API key and the setup process will complete.

> [!NOTE] 
> In order for this integration to work please ensure:
>
> 1. The base August Access Integration is already configured.
> 2. The devices can be seen in the Seam Console > Devices.
>
> This has only been tested with a single Yale lock.  Please create an issue if you encounter any issues. 
>
> If you aren't receiving updates, enable debugging on this integration and make sure that you are receiving webhook updates from Seam.
>
> Note that it can take several minutes for Seam to push the code changes to your lock.

## Usage

### Sensors
The integration will add a sensor with a count of the number of access codes active on the configured devices.  The sensor will be nested under the August device.

#### Attributes

The sensor attributes will contain two `json` keyed lists: 

* `managed_access_codes` - the json representations of the managed access codes (the codes configured/manipulated by Seam/this integration)
* `unmanaged_access_codes` - similar to the `managed_access_codes` but these cannot be modified by Seam or this integration (see Warning below).

>[!Warning] 
> This integration does not support manipulating "unmanaged" access codes (i.e. codes set directly on the device or using the native app).  Seam claims exposes endpoints to manipulate these codes or to convert unmanaged these to managed codes. However, each time these endpoints were tested the device would disassociate with the Yale/Augsut account and not longer be accesible 

### Services

#### Create Access Code

`august_access_codes.create_access_code` - Add a managed access code to a lock.

| Parameter | Required | Description/Notes |
|-----------|----------|-------------------|
| `target` | **required** | Entity or Device of target lock |
| `code` | **requided** | Numeric access code 4 to 8 digits |
| `name` | **required** | Name of code (user's name) |
| `start_time` | optional | Date/Time code becomes valid (local time zone) |
| `stop_time` | optional |  Date/Time code will become invalid |

> [!NOTE]
> Both `start_time` and `stop_time` are required when creating time-based codes.

#### Modify Access Code

`august_access_codes.modify_access_code` - Modify a managed access code on a lock.

| Parameter | Required | Description/Notes |
|-----------|----------|-------------------|
| `config_entry_id` | **required** | ID of the config entry of the Seam API where the managed access code exists |
| `access_code_id` | **required** | The ID assigned to the access code by Seam.  This can be found in the [sensor attributes](#attributes) for the lock
| `code` | **requided** | Numeric access code 4 to 8 digits |
| `name` | **required** | Name of code (user's name) |
| `start_time` | optional | Date/Time code becomes valid (local time zone) |
| `stop_time` | optional |  Date/Time code will become invalid |

> [!NOTE]
> Both `start_time` and `stop_time` are required when creating time-based codes.

#### Delete Access Code

`august_access_codes.delete_access_code` - Delete a managed access code on a lock.

| Parameter | Required | Description/Notes |
|-----------|----------|-------------------|
| `config_entry_id` | **required** | ID of the config entry of the Seam API where the managed access code exists |
| `access_code_id` | **required** | The ID assigned to the access code by Seam.  This can be found in the [sensor attributes](#attributes) for the lock

## Support
If you encounter any issues or have feature requests, please open an issue on the [GitHub Issues page](https://github.com/iluvdata/liebherr/issues).

## Contributions
Contributions are welcome! Feel free to submit pull requests to improve this integration.

## License
This project is licensed under the MIT License. See the [LICENSE](https://github.com/iluvdata/liebherr/blob/main/LICENSE) file for details.
