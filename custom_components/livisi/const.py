"""Constants for the Livisi Smart Home integration."""

import logging
from typing import Final

LOGGER = logging.getLogger(__package__)
DOMAIN = "livisi"

LIVISI_EVENT = f"{DOMAIN}_event"

CONF_HOST = "host"
CONF_PASSWORD: Final = "password"

CONF_SUBTYPE: Final = "subtype"

DEVICE_POLLING_DELAY: Final = 60
LIVISI_STATE_CHANGE: Final = "livisi_state_change"
LIVISI_REACHABILITY_CHANGE: Final = "livisi_reachability_change"

BUTTON_COUNT: Final = {"BRC8": 8, "ISC2": 2, "ISS2": 2, "WSC2": 2, "ISR2": 2, "ISD2": 2}

BUTTON_DEVICE_TYPES: Final = list(BUTTON_COUNT.keys())
DIMMING_DEVICE_TYPES: Final = ["PSD", "ISD2"]
MOTION_DEVICE_TYPES: Final = ["WMD", "WMDO"]
SHUTTER_DEVICE_TYPES: Final = ["ISR2"]
SIREN_DEVICE_TYPES: Final = ["SIR"]
SMOKE_DETECTOR_DEVICE_TYPES: Final = ["WSD", "WSD2"]
SWITCH_DEVICE_TYPES: Final = ["ISS2", "PSS", "PSSO", "BT-PSS"]
VARIABLE_DEVICE_TYPES: Final = ["VariableActuator"]
VRCC_DEVICE_TYPES: Final = ["VRCC"]
WDS_DEVICE_TYPES: Final = ["WDS", "BT-WDS"]

BATTERY_POWERED_DEVICES = [
    "BRC8",
    "ISC2",
    "RST",
    "RST2",
    "WDS",
    "WMD",
    "WMDO",
    "WSD",
    "WSD2",
    "SIR",
    "WRT",
    "BT-WDS",
    "BT-WS",
]

CAPABILITY_LUMINANCE_SENSOR: Final = "LuminanceSensor"
LUMINANCE: Final = "luminance"

CAPABILITY_TEMPERATURE_SENSOR: Final = "TemperatureSensor"
CAPABILITY_ROOM_TEMPERATURE: Final = "RoomTemperature"
TEMPERATURE: Final = "temperature"

CAPABILITY_HUMIDITY_SENSOR: Final = "HumiditySensor"
CAPABILITY_ROOM_HUMIDITY: Final = "RoomHumidity"
HUMIDITY: Final = "humidity"

CAPABILITY_POWER_SENSOR: Final = "PowerConsumptionSensor"
POWER_CONSUMPTION: Final = "powerConsumptionWatt"

ON_STATE: Final = "onState"
SHUTTER_LEVEL: Final = "shutterLevel"
DIM_LEVEL: Final = "dimLevel"
VALUE: Final = "value"
POINT_TEMPERATURE: Final = "pointTemperature"
SETPOINT_TEMPERATURE: Final = "setpointTemperature"
OPERATION_MODE: Final = "operationMode"
ACTIVE_CHANNEL: Final = "activeChannel"

IS_OPEN: Final = "isOpen"
IS_SMOKE_ALARM: Final = "isSmokeAlarm"

MAX_TEMPERATURE: Final = 30.0
MIN_TEMPERATURE: Final = 6.0

STATE_PROPERTIES = [
    ON_STATE,
    VALUE,
    POINT_TEMPERATURE,
    SETPOINT_TEMPERATURE,
    TEMPERATURE,
    HUMIDITY,
    LUMINANCE,
    IS_OPEN,
    IS_SMOKE_ALARM,
    POWER_CONSUMPTION,
    SHUTTER_LEVEL,
    DIM_LEVEL,
    OPERATION_MODE,
]

EVENT_BUTTON_PRESSED = "button_pressed"
EVENT_BUTTON_LONG_PRESSED = "button_long_pressed"
EVENT_MOTION_DETECTED = "motion_detected"
