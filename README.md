# Livisi Unofficial Fork

This project is in "works for me" state and I do not advise anyone to use it nor can or will I provide support on how to install it.
It can be added as a custom repo to HACS and then installed as an integration. This will override the existing livisi integration and add the following features:

* Support VariableActuators (Boolean vars in livisi)
* Support motion detectors (brightness sensor and events)
* Devices with buttons are supported as basic event entities and device triggers
* Support Smoke Detectors and Sirens
* Support temperature sensors for both the room climate devices and the individual thermostats
* Battery level indicators
* Dropped the dependencies on the aiolivisi lib, which seems to be abandoned. The neccessary connection code is simply included in this integration (which was opposed by the home assistant team for the official integration, but is the only logical way forward)

_Note: As I don't have any shutter contol devices (nor do I have window shutters at all), I cannot add them to this lib. If you are willing to add support from them (in the same style as the other devices are implemented), feel free to submit a PR_

## Caution

This is not a drop-in replacement anymore. As entities in the original implementation were uniquely identified by the device id, only one entity per device was supported. This does not scale, so this integration migrates the old entities and changes the unique id to the capability id (which should be unique for every functionality of a device in the livisi controller). So once you install this integration via HACS, you cannot go back to the official implementation without recreating your Livisi devices.

## Installation

### Using HACS (preferred)

Add this repository in [HACS](https://hacs.xyz/) as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories/) and install it from there

This way you will get automatic updates

### Manual

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
1. If you do not have a `custom_components` directory (folder) there, you need to create it.
1. In the `custom_components` directory (folder) create a new folder called `livisi`.
1. Download _all_ the files from the `custom_components/livisi/` directory (folder) in this repository.
1. Place the files you downloaded in the new directory (folder) you created.
1. Restart Home Assistant
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "livisi"

## Configuration

All configuration in done in the UI. See the [official documentation](https://www.home-assistant.io/integrations/livisi/)

## Notes

* Luminance is provided in percent by Livisi. Currently we get a warning: `<LivisiSensor> is using native unit of measurement '%' which is not a valid unit for the device class ('illuminance') it is using; expected one of ['lx']` but as percent is the correct unit here, I don't think we should change it (at least until it causes problems in HA)

## TODO

* Integrate light switches as lights, not as switches
* Rewrite sensors so that they are derived from just the available capabilities, not the hardcoded device names
* Find someone to implement the window shutters (as I don't have any)
* Find someone to implement dimmers (as I don't have any), this should wait until I have implemented the lights entity


