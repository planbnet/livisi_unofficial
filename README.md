# Livisi Unofficial Fork

This project is in "works for me" state, but it's in use by multiple people and probably more robust than the official implementation.
It can be added as a custom repo to HACS and then installed as an integration. This will override the existing livisi integration and add the following features:

* Support VariableActuators (boolean vars in livisi) as switches
* Support switching between auto and manual mode
* Support light switches as lights (be sure to categorize them correctly in the livisi controller)
* Support motion detectors (brightness sensor and events)
* Support smoke detectors
* Support temperature sensors for both the room climate devices and the individual thermostats
* Support dimmers (thx @acidburn78)
* Support covers
* Battery level indicators
* Devices with buttons are supported as basic event entities and device triggers
* Fixed availability state
* Dropped the dependencies on the aiolivisi lib, which seems to be abandoned. The neccessary connection code is simply included in this integration (see note below)
* Dropped the pydantic dependency
* Rewritten rest/webservice communication code
* Many, many more bug fixes

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

* Home Assistant requires all communication to the service backend to be handled by a library (as it was done with the original, unmaintained aiolivisi lib). This prevents the merge of this library to the official core code base currently. However, I don't feel it makes sense to move the code to a seperately maintained library as it is only used here and additions often need to happen along the whole code path. Semantically such a split makes sense though, so to make a later separation possible, I added the `livisi_` prefix to all the "library" code.


## Development

1. Clone this repository and open it in a devcontainer.
2. `cd scripts`
3. Only run the first time or on updates: `./setup`
4. `./develop`

You can also use the VSCode launch configuration `Home Assistant`.

