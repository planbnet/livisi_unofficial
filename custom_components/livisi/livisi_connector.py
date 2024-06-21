"""Code to handle the communication with Livisi Smart home controllers."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from typing import Any
import uuid
import json
from aiohttp import ClientResponseError, ServerDisconnectedError, ClientConnectorError
from aiohttp.client import ClientSession, ClientError, TCPConnector
from dateutil.parser import parse as parse_timestamp

from .livisi_device import LivisiDevice

from .livisi_json_util import parse_dataclass
from .livisi_controller import LivisiController

from .livisi_errors import (
    ERROR_CODES,
    IncorrectIpAddressException,
    LivisiException,
    ShcUnreachableException,
    WrongCredentialException,
    ErrorCodeException,
)

from .livisi_websocket import LivisiWebsocket

from .livisi_const import (
    COMMAND_RESTART,
    CONTROLLER_DEVICE_TYPES,
    V1_NAME,
    V2_NAME,
    LOGGER,
    REQUEST_TIMEOUT,
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
        try:
            await self._async_retrieve_token()
        except:
            await self.close()
            raise

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
            with suppress(Exception):
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
        return await self._async_request(method, url, payload, auth_headers)

    def _create_web_session(self, concurrent_connections: int = 1):
        """Create a custom web session which limits concurrent connections."""
        connector = TCPConnector(
            limit=concurrent_connections,
            limit_per_host=concurrent_connections,
            force_close=True,
        )
        web_session = ClientSession(connector=connector)
        return web_session

    async def _async_retrieve_token(self) -> None:
        """Set the JWT from the LIVISI Smart Home Controller."""
        access_data: dict = {}

        if self._password is None:
            raise LivisiException("No password set")

        login_credentials = {
            "username": "admin",
            "password": self._password,
            "grant_type": "password",
        }
        headers = {
            "Authorization": "Basic Y2xpZW50SWQ6Y2xpZW50UGFzcw==",
            "Content-type": "application/json",
            "Accept": "application/json",
        }

        try:
            LOGGER.debug("Updating access token")
            access_data = await self._async_send_request(
                "post",
                url=f"http://{self.host}:{WEBSERVICE_PORT}/auth/token",
                payload=login_credentials,
                headers=headers,
            )
            LOGGER.debug("Updated access token")
            self.token = access_data.get("access_token")
            if self.token is None:
                errorcode = access_data.get("errorcode")
                errordesc = access_data.get("description", "Unknown Error")
                if errorcode in (2003, 2009):
                    raise WrongCredentialException
                # log full response for debugging
                LOGGER.error("SHC response does not contain access token")
                LOGGER.error(access_data)
                raise LivisiException(f"No token received from SHC: {errordesc}")
        except ClientError as error:
            if len(access_data) == 0:
                raise IncorrectIpAddressException from error
            raise ShcUnreachableException from error

    async def _async_request(
        self, method, url: str, payload=None, headers=None
    ) -> dict:
        """Send a request to the Livisi Smart Home controller and handle requesting new token."""
        response = await self._async_send_request(method, url, payload, headers)

        if response is not None and "errorcode" in response:
            errorcode = response.get("errorcode")
            # reconnect on expired token
            if errorcode == 2007:
                await self._async_retrieve_token()
                response = await self._async_send_request(method, url, payload, headers)
                if response is not None and "errorcode" in response:
                    LOGGER.error(
                        "Livisi sent error code %d after token request",
                        response.get("errorcode"),
                    )
                    raise ErrorCodeException(response["errorcode"])
            else:
                LOGGER.error(
                    "Error code %d (%s) on url %s",
                    errorcode,
                    ERROR_CODES.get(errorcode, "unknown"),
                    url,
                )
                raise ErrorCodeException(response["errorcode"])

        return response

    async def _async_send_request(
        self, method, url: str, payload=None, headers=None
    ) -> dict:
        try:
            if payload is not None:
                data = json.dumps(payload).encode("utf-8")
                if headers is None:
                    headers = {}
                headers["Content-Type"] = "application/json"
                headers["Content-Encoding"] = "utf-8"
            else:
                data = None

            async with self._web_session.request(
                method,
                url,
                json=payload,
                headers=headers,
                ssl=False,
                timeout=REQUEST_TIMEOUT,
            ) as res:
                try:
                    data = await res.json()
                    if data is None and res.status != 200:
                        raise LivisiException(
                            f"No data received from SHC, response code {res.status} ({res.reason})"
                        )
                except ClientResponseError as exc:
                    raise LivisiException(
                        f"Invalid response from SHC, response code {res.status} ({res.reason})"
                    ) from exc
                return data
        except TimeoutError as exc:
            raise ShcUnreachableException("Timeout waiting for shc") from exc
        except ClientConnectorError as exc:
            raise ShcUnreachableException("Failed to connect to shc") from exc

    async def _async_get_controller(self) -> LivisiController:
        """Get Livisi Smart Home controller data."""
        shc_info = await self.async_send_authorized_request("get", path="status")
        controller = parse_dataclass(shc_info, LivisiController)
        controller.is_v2 = shc_info.get("controllerType") == V2_NAME
        controller.is_v1 = shc_info.get("controllerType") == V1_NAME
        return controller

    async def async_get_devices(
        self,
    ) -> list[LivisiDevice]:
        """Send requests for getting all required data."""

        # retrieve messages first, this will also refresh the token if
        # needed so subsequent parallel requests don't fail
        messages = await self.async_send_authorized_request("get", path="message")

        (
            low_battery_devices,
            update_available_devices,
            unreachable_devices,
            updated_devices,
        ) = self.parse_messages(messages)

        devices, capabilities, rooms = await asyncio.gather(
            self.async_send_authorized_request("get", path="device"),
            self.async_send_authorized_request("get", path="capability"),
            self.async_send_authorized_request("get", path="location"),
            return_exceptions=True,
        )

        for result, path in zip(
            (devices, capabilities, rooms),
            ("device", "capability", "location"),
        ):
            if isinstance(result, Exception):
                LOGGER.warn(f"Error loading {path}")
                raise result  # Re-raise the exception immediately

        controller_id = next(
            (x.get("id") for x in devices if x.get("type") in CONTROLLER_DEVICE_TYPES),
            None,
        )
        if controller_id is not None:
            try:
                shc_state = await self.async_send_authorized_request(
                    "get", path=f"device/{controller_id}/state"
                )
                if self.controller.is_v1:
                    shc_state = shc_state["state"]
            except Exception:
                LOGGER.warning("Error getting shc state", exc_info=True)

        capability_map = {}
        capability_config = {}

        room_map = {}

        for room in rooms:
            if "id" in room:
                roomid = room["id"]
                room_map[roomid] = room.get("config", {}).get("name")

        for capability in capabilities:
            if "device" in capability:
                device_id = capability["device"].removeprefix("/device/")

                if device_id not in capability_map:
                    capability_map[device_id] = {}
                    capability_config[device_id] = {}

                cap_type = capability.get("type")
                if cap_type is not None:
                    capability_map[device_id][cap_type] = capability["id"]
                    if "config" in capability:
                        capability_config[device_id][cap_type] = capability["config"]

        devicelist = []

        for device in devices:
            device_id = device.get("id")
            device["capabilities"] = capability_map.get(device_id, {})
            device["capability_config"] = capability_config.get(device_id, {})
            device["cls"] = device.get("class")
            device["battery_low"] = device_id in low_battery_devices
            device["update_available"] = device_id in update_available_devices
            device["updated"] = device_id in updated_devices
            device["unreachable"] = device_id in unreachable_devices
            if device.get("location") is not None:
                roomid = device["location"].removeprefix("/location/")
                device["room"] = room_map.get(roomid)

            if device["type"] in CONTROLLER_DEVICE_TYPES:
                device["state"] = shc_state

            devicelist.append(parse_dataclass(device, LivisiDevice))

        LOGGER.debug("Loaded %d devices", len(devices))

        return devicelist

    def parse_messages(self, messages):
        """Parse message data from shc."""
        low_battery_devices = set()
        update_available_devices = set()
        unreachable_devices = set()
        updated_devices = set()

        for message in messages:
            if isinstance(message, str):
                LOGGER.warning("Invalid message")
                LOGGER.warning(messages)
                continue

            msgtype = message.get("type", "")
            msgtimestamp = parse_timestamp(message.get("timestamp", ""))
            if msgtimestamp is None:
                continue

            device_ids = [
                d.removeprefix("/device/") for d in message.get("devices", [])
            ]
            if len(device_ids) == 0:
                source = message.get("source", "")
                device_ids = [source.replace("/device/", "")]
            if msgtype == "DeviceLowBattery":
                for device_id in device_ids:
                    low_battery_devices.add(device_id)
            elif msgtype == "DeviceUpdateAvailable":
                for device_id in device_ids:
                    update_available_devices.add(device_id)
            elif msgtype == "ProductUpdated" or msgtype == "ShcUpdateCompleted":
                for device_id in device_ids:
                    updated_devices.add(device_id)
            elif msgtype == "DeviceUnreachable":
                for device_id in device_ids:
                    unreachable_devices.add(device_id)
        return (
            low_battery_devices,
            update_available_devices,
            unreachable_devices,
            updated_devices,
        )

    async def async_get_value(
        self, capability: str, property: str, key: str = "value"
    ) -> Any | None:
        """Get current value of the capability."""
        state = await self.async_get_state(capability, property)
        if state is None:
            return None
        return state.get(key, None)

    async def async_get_state(self, capability: str, property: str) -> dict | None:
        """Get state of a capability."""

        if capability is None:
            return None

        requestUrl = f"capability/{capability}/state"
        try:
            response = await self.async_send_authorized_request("get", requestUrl)
            if response is None:
                return None
            if not isinstance(response, dict):
                return None
            return response.get(property, None)
        except Exception:
            LOGGER.warning(
                f"Error getting device state (url: {requestUrl})", exc_info=True
            )
            return None

    async def async_set_state(
        self,
        capability_id: str,
        *,
        key: str = None,
        value: bool | float = None,
        namespace: str = "core.RWE",
    ) -> bool:
        """Set the state of a capability."""
        params = {}
        if key is not None:
            params = {key: {"type": "Constant", "value": value}}

        return await self.async_send_capability_command(
            capability_id, "SetState", namespace=namespace, params=params
        )

    async def _async_send_command(
        self,
        target: str,
        command_type: str,
        *,
        namespace: str = "core.RWE",
        params: dict = None,
    ) -> bool:
        """Send a command to a target."""

        if params is None:
            params = {}

        set_state_payload: dict[str, Any] = {
            "id": uuid.uuid4().hex,
            "type": command_type,
            "namespace": namespace,
            "target": target,
            "params": params,
        }
        try:
            response = await self.async_send_authorized_request(
                "post", "action", payload=set_state_payload
            )
            if response is None:
                return False
            return response.get("resultCode") == "Success"
        except ServerDisconnectedError:
            # Funny thing: The SHC restarts immediatly upon processing the restart command, it doesn't even answer to the request
            # In order to not throw an error we need to catch and assume the request was successfull.
            if command_type == COMMAND_RESTART:
                return True
            raise

    async def async_send_device_command(
        self,
        device_id: str,
        command_type: str,
        *,
        namespace: str = "core.RWE",
        params: dict = None,
    ) -> bool:
        """Send a command to a device."""

        return await self._async_send_command(
            target=f"/device/{device_id}",
            command_type=command_type,
            namespace=namespace,
            params=params,
        )

    async def async_send_capability_command(
        self,
        capability_id: str,
        command_type: str,
        *,
        namespace: str = "core.RWE",
        params: dict = None,
    ) -> bool:
        """Send a command to a capability."""

        return await self._async_send_command(
            target=f"/capability/{capability_id}",
            command_type=command_type,
            namespace=namespace,
            params=params,
        )

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
