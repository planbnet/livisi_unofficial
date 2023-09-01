"""Constants for the Livisi Smart Home integration."""
import logging
from typing import Final

LOGGER = logging.getLogger(__package__)

V2_NAME = "Avatar"
V2_WEBSOCKET_PORT: Final = 9090
CLASSIC_WEBSOCKET_PORT: Final = 8080
WEBSERVICE_PORT: Final = 8080
REQUEST_TIMEOUT: Final = 2000

CAPABILITY_MAP: Final = "capabilityMap"
CAPABILITY_CONFIG: Final = "capabilityConfig"
BATTERY_LOW: Final = "batteryLow"
UPDATE_AVAILABLE: Final = "DeviceUpdateAvailable"

LIVISI_EVENT_STATE_CHANGED = "StateChanged"
LIVISI_EVENT_BUTTON_PRESSED = "ButtonPressed"
LIVISI_EVENT_MOTION_DETECTED = "MotionDetected"

IS_REACHABLE: Final = "isReachable"
LOCATION: Final = "location"

EVENT_BUTTON_PRESSED = "button_pressed"
EVENT_BUTTON_LONG_PRESSED = "button_long_pressed"
EVENT_MOTION_DETECTED = "motion_detected"
