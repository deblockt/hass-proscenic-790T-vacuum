# Home assistant proscenic 790T vacuum integration

[![GitHub release](https://img.shields.io/github/release/deblockt/hass-proscenic-790T-vacuum)](https://github.com/deblockt/hass-proscenic-790T-vacuum/releases/latest)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

The purpose of this integration is to provide an integration of proscenic 790T vacuum.
It allow home assistant to:
- start cleaning
- pause cleaning
- go to dock
- retrieve vacuum informations (battery, state)
- show the cleaning map

![screenshot](./doc/screen.png)

## Installation

### HACS installation

You can use [HACS](https://hacs.xyz/) to install this component. Search for the Integration "proscenic 790T vacuum"

### Manual installation

1. Go to [releases page](https://github.com/deblockt/hass-proscenic-790T-vacuum/releases)
2. download the last release zip
3. unzip it on `custom_components` directory
4. see next chapter for configuration

## Configuration

Add your device via the Integration menu.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=proscenic)

You can choose between two connection mode:
- *local*: the integration will use your local network to contact your vacuum (send command to start/stop). But the cloud will be used to get vacuum status, and the cleaning map.
- *cloud*: All interactions are done using the cloud.

> Note: Some vacuum don't support the local mode.


### Get authentifications data

device id, token, user id and authentication code can be retrieved using the Proscenic robotic application :
1. On your android smartphone (no solution for iphone), install [Packet capture](https://play.google.com/store/apps/details?id=app.greyshirts.sslcapture&hl=fr)
2. Open Packet capture and start a capture ![screenshot](./doc/packet_capture_button.png) select Proscenic  Robotic app
3. Open the proscenic application, and open the vacuum view
4. Reopen  Packet capture
    1. Click on the first line
    2. Click on the line `47.91.67.181:20008`
    3. Get you informations ![screenshot](./doc/packet_with_info.jpg)
5. You can now enter your informations on home assistant
6. You can add your vacuum on lovelace ui entities
    1. You can simply add it as an entity
    2. You can use the [vacuum-card](https://github.com/denysdovhan/vacuum-card)

> **Note**:  YAML configuration is deprecated. This will be removed soon.

## Cleaning map management

![map](./doc/map.png)

The camera entity will be automaticaly added.
The proscenic cloud is used to generate the map.

> ⚠️ 🚨: updating to 0.0.10 you should remove the integration and re-add it using cloud configuration to keep the map generation working

## Available attributes

Theses attributes are available to be displayed on lovelace-ui:
- `clear_area`: number of m2 cleaned
- `clear_duration`: last clean duration in second
- `error_code`: the current error code, if vacuum is on error status
- `error_detail`: the current error message (in english), if vacuum is on error status

## Know issue

- At home assistant startup the vacuum cleaner status is not retrieved. You should perform an action on home assistant to get the vacuum cleaner status.
- If you start the proscenic application, the status of the vacuum cleaner will not be refreshed on home assistant for 60 seconds.
- If you start the proscenic application, you will be disconnected 60 seconds later. You can configure this time using `sleep_duration_on_exit` configuration.

[![buymeacoffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/deblockt)
