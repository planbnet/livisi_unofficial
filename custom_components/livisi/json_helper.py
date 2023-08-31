"""JSON helpers for aiolivisi."""
from __future__ import annotations

from typing import Any

import orjson

from aiohttp import ClientResponse


def json_encoder_default(obj: Any) -> Any:
    """Convert objects to json like ha does."""
    if isinstance(obj, set | tuple):
        return list(obj)
    if isinstance(obj, float):
        return float(obj)
    if hasattr(obj, "as_dict"):
        return obj.as_dict()
    raise TypeError


def json_dumps(data: Any) -> str:
    """Dump json string.

    orjson supports serializing dataclasses natively which
    eliminates the need to implement as_dict in many places
    when the data is already in a dataclass. This works
    well as long as all the data in the dataclass can also
    be serialized.

    If it turns out to be a problem we can disable this
    with option |= orjson.OPT_PASSTHROUGH_DATACLASS and it
    will fallback to as_dict
    """
    return orjson.dumps(
        data, option=orjson.OPT_NON_STR_KEYS, default=json_encoder_default
    ).decode("utf-8")


class LivisiClientResponse(ClientResponse):
    """aiohttp.ClientResponse with a json method that uses json_loads by default."""

    async def json(
        self,
        *args: Any,
        loads=orjson.loads,
        **kwargs: Any,
    ) -> Any:
        """Send a json request and parse the json response."""
        return await super().json(*args, loads=loads, **kwargs)
