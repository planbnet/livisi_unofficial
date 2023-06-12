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

SWITCH_DEVICE_TYPES: Final = ["ISS", "ISS2", "PSS", "PSSO"]
SIREN_DEVICE_TYPES: Final = ["WSD", "WSD2"]
VARIABLE_DEVICE_TYPE: Final = "VariableActuator"
BUTTON_DEVICE_TYPES: Final = ["ISS2", "WSS2", "BRM8"]
MOTION_DEVICE_TYPES: Final = ["WMD", "WMDO"]
VRCC_DEVICE_TYPE: Final = "VRCC"
WDS_DEVICE_TYPE: Final = "WDS"

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
]

EVENT_BUTTON_PRESSED = "button_pressed"
EVENT_MOTION_DETECTED = "motion_detected"

BUTTON_COUNT = {"BRC8": 8, "ISC2": 2, "ISS2": 2}

MAX_TEMPERATURE: Final = 30.0
MIN_TEMPERATURE: Final = 6.0
