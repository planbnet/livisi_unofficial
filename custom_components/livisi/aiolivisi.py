"""Code to handle the communication with Livisi Smart home controllers."""
from __future__ import annotations
import asyncio
from typing import Any
import uuid

from dateutil.parser import parse as parseTimestamp
from aiohttp.client import ClientSession, ClientError

from .livisi_errors import (
    IncorrectIpAddressException,
    ShcUnreachableException,
    WrongCredentialException,
    ErrorCodeException,
)

from .const import (
    AUTH_GRANT_TYPE,
    AUTH_PASSWORD,
    AUTH_USERNAME,
    AUTHENTICATION_HEADERS,
    BATTERY_LOW,
    CLASSIC_PORT,
    LOCATION,
    LOGGER,
    CAPABILITY_MAP,
    CAPABILITY_CONFIG,
    REQUEST_TIMEOUT,
    USERNAME,
    UPDATE_AVAILABLE,
)

ERRORS = {1: Exception}


class AioLivisi:
    """Handles the communication with the Livisi Smart Home controller."""

    instance = None

    def __init__(
        self, web_session: ClientSession = None, auth_headers: dict[str, Any] = None
    ) -> None:
        """Initialize aiolivisi lib."""
        self._web_session: ClientSession = web_session
        self._auth_headers: dict[str, Any] = auth_headers
        self._token: str = ""
        self._livisi_connection_data: dict[str, str] = None
        self._lastest_message = None

    async def async_retrieve_token(
        self, livisi_connection_data: dict[str, str] = None
    ) -> None:
        """Set the JWT from the LIVISI Smart Home Controller."""
        access_data: dict = {}
        try:
            if livisi_connection_data is not None:
                self._livisi_connection_data = livisi_connection_data
            access_data = await self.async_get_jwt_token(self._livisi_connection_data)
            self.token = access_data["access_token"]
            self._auth_headers = {
                "authorization": f"Bearer {self.token}",
                "Content-type": "application/json",
                "Accept": "*/*",
            }
        except TimeoutError as error:
            raise ShcUnreachableException from error
        except ClientError as error:
            if len(access_data) == 0:
                raise IncorrectIpAddressException from error
            if access_data["errorcode"] == 2009:
                raise WrongCredentialException from error
            raise ShcUnreachableException from error

    async def async_send_authorized_request(
        self,
        method,
        path: str,
        payload=None,
    ) -> dict:
        """Make a request to the Livisi Smart Home controller."""
        ip_address = self._livisi_connection_data["ip_address"]
        url = f"http://{ip_address}:{CLASSIC_PORT}/{path}"
        return await self.async_send_request(method, url, payload, self._auth_headers)

    async def async_send_unauthorized_request(
        self,
        method,
        url: str,
        headers,
        payload=None,
    ) -> dict:
        """Send a request without JWT token."""
        return await self.async_send_request(method, url, payload, headers)

    async def async_get_jwt_token(self, livisi_connection_data: dict[str, str]):
        """Send a request for getting the JWT token."""
        login_credentials = {
            AUTH_USERNAME: USERNAME,
            AUTH_PASSWORD: livisi_connection_data["password"],
            AUTH_GRANT_TYPE: "password",
        }
        headers = AUTHENTICATION_HEADERS
        self._livisi_connection_data = livisi_connection_data
        ip_address = self._livisi_connection_data["ip_address"]
        return await self.async_send_request(
            "post",
            url=f"http://{ip_address}:{CLASSIC_PORT}/auth/token",
            payload=login_credentials,
            headers=headers,
        )

    async def async_send_request(
        self, method, url: str, payload=None, headers=None
    ) -> dict:
        """Send a request to the Livisi Smart Home controller and handle requesting new token."""

        # The try...catch statement is needed as a workaround for random request failures on V1 SHC
        try:
            response = await self._async_send_request(method, url, payload, headers)
        except Exception:
            response = await self._async_send_request(method, url, payload, headers)

        if "errorcode" in response:
            if response["errorcode"] == 2007:
                await self.async_retrieve_token()
                response = await self._async_send_request(method, url, payload, headers)
            else:
                raise ErrorCodeException(response["errorcode"])
        return response

    async def _async_send_request(
        self, method, url: str, payload=None, headers=None
    ) -> dict:
        async with self._web_session.request(
            method,
            url,
            json=payload,
            headers=headers,
            ssl=False,
            timeout=REQUEST_TIMEOUT,
        ) as res:
            data = await res.json()
            return data

    async def async_get_controller(self) -> dict[str, Any]:
        """Get Livisi Smart Home controller data."""
        shc_info = await self.async_send_authorized_request("get", path="status")
        return shc_info

    async def async_get_devices(
        self,
    ) -> list[dict[str, Any]]:
        """Send a request for getting the devices."""
        devices, capabilities, messages = await asyncio.gather(
            self.async_send_authorized_request("get", path="device"),
            self.async_send_authorized_request("get", path="capability"),
            self.async_send_authorized_request("get", path="message"),
        )

        capability_map = {}
        capability_config = {}

        for capability in capabilities:
            if "device" in capability:
                device_id = capability["device"].removeprefix("/device/")
                if device_id not in capability_map:
                    capability_map[device_id] = {}
                    capability_config[device_id] = {}
                capability_map[device_id][capability["type"]] = capability["id"]
                if "config" in capability:
                    capability_config[device_id][capability["type"]] = capability[
                        "config"
                    ]

        low_battery_devices = set()
        update_available_devices = set()
        for message in messages:
            msgtype = message.get("type", "")
            msgtimestamp = parseTimestamp(message.get("timestamp", ""))
            if msgtimestamp is None:
                continue

            if self._lastest_message is None or msgtimestamp > self._lastest_message:
                self._lastest_message = msgtimestamp

            device_ids = [
                d.removeprefix("/device/") for d in message.get("devices", [])
            ]
            if len(device_id) == 0:
                source = message.get("source", "00000000000000000000000000000000")
                device_ids.add(source.replace("/device/", ""))
            if msgtype == "DeviceLowBattery":
                for device_id in device_ids:
                    low_battery_devices.add(device_id)
            elif msgtype == "DeviceUpdateAvailable":
                for device_id in device_ids:
                    update_available_devices.add(device_id)
            elif msgtype == "ProductUpdated" or msgtype == "ShcUpdateCompleted":
                pass
            elif msgtype == "DeviceUnreachable":
                pass

        for device in devices:
            device_id = device["id"]
            device[CAPABILITY_MAP] = capability_map.get(device_id, {})
            device[CAPABILITY_CONFIG] = capability_config.get(device_id, {})
            if device_id in low_battery_devices:
                device[BATTERY_LOW] = True
            if device_id in update_available_devices:
                device[UPDATE_AVAILABLE] = True
            if LOCATION in device and device.get(LOCATION) is not None:
                device[LOCATION] = device[LOCATION].removeprefix("/location/")

        LOGGER.debug("Loaded %d devices", len(devices))

        return devices

    async def async_get_device_state(self, capability_id) -> dict[str, Any] | None:
        """Get the state of the device."""
        try:
            return await self.async_send_authorized_request(
                "get", f"capability/{capability_id}/state"
            )
        except Exception:
            LOGGER.warning("Error getting device state", exc_info=True)
            return None

    async def async_set_state(
        self, capability_id: str, key: str, value: bool | float
    ) -> dict[str, Any]:
        """Set the state of a capability."""
        set_state_payload: dict[str, Any] = {
            "id": uuid.uuid4().hex,
            "type": "SetState",
            "namespace": "core.RWE",
            "target": f"/capability/{capability_id}",
            "params": {key: {"type": "Constant", "value": value}},
        }
        return await self.async_send_authorized_request(
            "post", "action", payload=set_state_payload
        )

    async def async_get_all_rooms(self) -> dict[str, Any]:
        """Get all the rooms from LIVISI configuration."""
        return await self.async_send_authorized_request("get", "location")

    @property
    def livisi_connection_data(self):
        """Return the connection data."""
        return self._livisi_connection_data

    @livisi_connection_data.setter
    def livisi_connection_data(self, new_value):
        self._livisi_connection_data = new_value

    @property
    def token(self):
        """Return the token."""
        return self._token

    @token.setter
    def token(self, new_value):
        self._token = new_value

    @property
    def web_session(self):
        """Return the web session."""
        return self._web_session

    @web_session.setter
    def web_session(self, new_value):
        self._web_session = new_value
