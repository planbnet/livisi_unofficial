"""Code to handle the communication with Livisi Smart home controllers."""
from __future__ import annotations

import asyncio
from typing import Any
import uuid
from aiohttp import ClientConnectionError
from aiohttp.client import ClientSession, ClientError, TCPConnector
from dateutil.parser import parse as parse_timestamp

from .livisi_json_util import parse_dataclass
from .livisi_controller import LivisiController
from .livisi_room import LivisiRoom

from .livisi_errors import (
    IncorrectIpAddressException,
    LivisiException,
    ShcUnreachableException,
    WrongCredentialException,
    ErrorCodeException,
)


from .livisi_websocket import LivisiWebsocket

from .livisi_const import (
    AUTH_GRANT_TYPE,
    AUTH_PASSWORD,
    AUTH_USERNAME,
    AUTHENTICATION_HEADERS,
    AVATAR,
    BATTERY_LOW,
    LOCATION,
    LOGGER,
    CAPABILITY_MAP,
    CAPABILITY_CONFIG,
    REQUEST_TIMEOUT,
    USERNAME,
    UPDATE_AVAILABLE,
    WEBSERVICE_PORT,
)


async def connect(host: str, password: str) -> LivisiConnection:
    """Initialize the lib and connect to the livisi SHC."""
    connection = LivisiConnection()
    await connection.connect(host, password)
    return connection


class LivisiConnection:
    """Handles the communication with the Livisi Smart Home controller."""

    def __init__(self) -> None:
        """Initialize the livisi connector."""

        self.host: str = None
        self.controller: LivisiController = None

        self._password: str = None
        self._token: str = None

        self._web_session = None
        self._websocket = LivisiWebsocket(self)

    async def connect(self, host: str, password: str):
        """Connect to the livisi SHC and retrieve controller information."""
        if self._web_session is not None:
            await self.close()
        self._web_session = self._create_web_session(concurrent_connections=1)
        if host is not None and password is not None:
            self.host = host
            self._password = password
        await self._async_retrieve_token()
        self.controller = await self._async_get_controller()
        if self.controller.is_v2:
            # reconnect with more concurrent connections on v2 SHC
            await self._web_session.close()
            self._web_session = self._create_web_session(concurrent_connections=10)

    async def close(self):
        """Disconnect the http client session and websocket."""
        if self._web_session is not None:
            await self._web_session.close()
            self._web_session = None
        self.controller = None
        await self._websocket.disconnect()

    async def listen_for_events(self, on_data, on_close) -> None:
        """Connect to the websocket."""
        if self._web_session is None:
            raise LivisiException("Not authenticated to SHC")
        if self._websocket.is_connected():
            await self._websocket.disconnect()
        await self._websocket.connect(on_data, on_close)

    async def async_send_authorized_request(
        self,
        method,
        path: str,
        payload=None,
    ) -> dict:
        """Make a request to the Livisi Smart Home controller."""
        url = f"http://{self.host}:{WEBSERVICE_PORT}/{path}"
        auth_headers = {
            "authorization": f"Bearer {self.token}",
            "Content-type": "application/json",
            "Accept": "*/*",
        }
        return await self._async_send_request(method, url, payload, auth_headers)

    def _create_web_session(self, concurrent_connections: int = 1):
        """Create a custom web session which limits concurrent connections."""
        connector = TCPConnector(
            limit=concurrent_connections, limit_per_host=concurrent_connections
        )
        web_session = ClientSession(connector=connector)
        return web_session

    async def _async_retrieve_token(self) -> None:
        """Set the JWT from the LIVISI Smart Home Controller."""
        access_data: dict = {}

        login_credentials = {
            AUTH_USERNAME: USERNAME,
            AUTH_PASSWORD: self._password,
            AUTH_GRANT_TYPE: "password",
        }
        headers = AUTHENTICATION_HEADERS

        try:
            access_data = await self._async_send_request(
                "post",
                url=f"http://{self.host}:{WEBSERVICE_PORT}/auth/token",
                payload=login_credentials,
                headers=headers,
            )
            self.token = access_data["access_token"]
            # self._refresh_token = access_data["refresh_token"]
        except TimeoutError as error:
            raise ShcUnreachableException from error
        except ClientError as error:
            if len(access_data) == 0:
                raise IncorrectIpAddressException from error
            if access_data["errorcode"] == 2009:
                raise WrongCredentialException from error
            raise ShcUnreachableException from error

    async def _async_send_request(
        self, method, url: str, payload=None, headers=None
    ) -> dict:
        """Send a request to the Livisi Smart Home controller and handle requesting new token."""

        # The try...catch statement is needed as a workaround for random request failures on V1 SHC
        try:
            response = await self._async_send_request(method, url, payload, headers)
        except ClientConnectionError:
            response = await self._async_send_request(method, url, payload, headers)

        if "errorcode" in response:
            # reconnect on expired token
            if response["errorcode"] == 2007:
                await self._async_retrieve_token()
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

    async def _async_get_controller(self) -> dict[str, Any]:
        """Get Livisi Smart Home controller data."""
        shc_info = await self.async_send_authorized_request("get", path="status")
        controller = parse_dataclass(shc_info, LivisiController)
        controller.is_v2 = shc_info.get("controllerType") == AVATAR
        return controller

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
            msgtimestamp = parse_timestamp(message.get("timestamp", ""))
            if msgtimestamp is None:
                continue

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

    async def async_get_all_rooms(self) -> list[LivisiRoom]:
        """Get all the rooms from LIVISI configuration."""
        rooms = await self.async_send_authorized_request("get", "location")
        return [parse_dataclass(item, LivisiRoom) for item in rooms]

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
