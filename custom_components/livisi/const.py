"""Constants for the Livisi Smart Home integration."""
import logging
from typing import Final

LOGGER = logging.getLogger(__package__)
DOMAIN = "livisi"

LIVISI_EVENT = f"{DOMAIN}_event"

CONF_HOST = "host"
CONF_PASSWORD: Final = "password"

CONF_SUBTYPE: Final = "subtype"

AVATAR = "Avatar"
AVATAR_PORT: Final = 9090
CLASSIC_PORT: Final = 8080
DEVICE_POLLING_DELAY: Final = 60
LIVISI_STATE_CHANGE: Final = "livisi_state_change"
LIVISI_REACHABILITY_CHANGE: Final = "livisi_reachability_change"

SWITCH_DEVICE_TYPES: Final = ["ISS2", "PSS", "PSSO"]
SIREN_DEVICE_TYPES: Final = ["WSD", "WSD2", "SIR"]
SMOKE_DETECTOR_DEVICE_TYPES: Final = ["WSD", "WSD2"]
VARIABLE_DEVICE_TYPE: Final = "VariableActuator"
BUTTON_DEVICE_TYPES: Final = ["ISS2", "WSC2", "ISC2", "BRC8"]
MOTION_DEVICE_TYPES: Final = ["WMD", "WMDO"]
VRCC_DEVICE_TYPE: Final = "VRCC"
WDS_DEVICE_TYPE: Final = "WDS"
TEMPERATURE_DEVICE_TYPES = ["RST", "RST2", "WRT", VRCC_DEVICE_TYPE]
HUMIDITY_DEVICE_TYPES = ["RST", "RST2", "WRT", VRCC_DEVICE_TYPE]

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
    "WRT",
]

BUTTON_COUNT = {"BRC8": 8, "ISC2": 2, "ISS2": 2}

MAX_TEMPERATURE: Final = 30.0
MIN_TEMPERATURE: Final = 6.0

USERNAME: Final = "admin"
AUTH_USERNAME: Final = "username"
AUTH_PASSWORD: Final = "password"
AUTH_GRANT_TYPE: Final = "grant_type"
REQUEST_TIMEOUT: Final = 2000

CAPABILITY_MAP: Final = "capabilityMap"
CAPABILITY_CONFIG: Final = "capabilityConfig"
BATTERY_LOW: Final = "batteryLow"
UPDATE_AVAILABLE: Final = "DeviceUpdateAvailable"

AUTHENTICATION_HEADERS: Final = {
    "Authorization": "Basic Y2xpZW50SWQ6Y2xpZW50UGFzcw==",
    "Content-type": "application/json",
    "Accept": "application/json",
}

LIVISI_EVENT_STATE_CHANGED = "StateChanged"
LIVISI_EVENT_BUTTON_PRESSED = "ButtonPressed"
LIVISI_EVENT_MOTION_DETECTED = "MotionDetected"

ON_STATE: Final = "onState"
VALUE: Final = "value"
POINT_TEMPERATURE: Final = "pointTemperature"
SET_POINT_TEMPERATURE: Final = "setpointTemperature"
TEMPERATURE: Final = "temperature"
HUMIDITY: Final = "humidity"
LUMINANCE: Final = "luminance"
IS_OPEN: Final = "isOpen"
IS_SMOKE_ALARM: Final = "isSmokeAlarm"

STATE_PROPERTIES = [
    ON_STATE,
    VALUE,
    POINT_TEMPERATURE,
    SET_POINT_TEMPERATURE,
    TEMPERATURE,
    HUMIDITY,
    LUMINANCE,
    IS_OPEN,
    IS_SMOKE_ALARM,
]

IS_REACHABLE: Final = "isReachable"
LOCATION: Final = "location"

EVENT_BUTTON_PRESSED = "button_pressed"
EVENT_BUTTON_LONG_PRESSED = "button_long_pressed"
EVENT_MOTION_DETECTED = "motion_detected"
