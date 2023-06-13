"""Constants for aiolivisi communication."""

from typing import Final

CLASSIC_PORT: Final = 8080
AVATAR_PORT: Final = 9090
USERNAME: Final = "admin"
AUTH_USERNAME: Final = "username"
AUTH_PASSWORD: Final = "password"
AUTH_GRANT_TYPE: Final = "grant_type"
REQUEST_TIMEOUT: Final = 2000

ON_STATE: Final = "onState"
VALUE: Final = "value"
POINT_TEMPERATURE: Final = "pointTemperature"
SET_POINT_TEMPERATURE: Final = "setpointTemperature"
TEMPERATURE: Final = "temperature"
HUMIDITY: Final = "humidity"
LUMINANCE: Final = "luminance"
IS_REACHABLE: Final = "isReachable"
IS_OPEN: Final = "isOpen"
LOCATION: Final = "location"

KEY_INDEX: Final = "index"
KEY_PRESS_TYPE: Final = "type"
KEY_PRESS_SHORT: Final = "ShortPress"
KEY_PRESS_LONG: Final = "LongPress"


CAPABILITY_MAP: Final = "capabilityMap"
CAPABILITY_CONFIG: Final = "capabilityConfig"
BATTERY_LOW: Final = "batteryLow"

EVENT_STATE_CHANGED = "StateChanged"
EVENT_BUTTON_PRESSED = "ButtonPressed"
EVENT_MOTION_DETECTED = "MotionDetected"

AUTHENTICATION_HEADERS: Final = {
    "Authorization": "Basic Y2xpZW50SWQ6Y2xpZW50UGFzcw==",
    "Content-type": "application/json",
    "Accept": "application/json",
}
