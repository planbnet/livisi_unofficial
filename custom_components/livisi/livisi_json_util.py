"""Helper code to parse json to python dataclass (simple and non recursive)."""
from dataclasses import fields
import json
import re


def parse_dataclass(jsondata, clazz):
    """Convert keys to snake_case and parse to dataclass."""

    if isinstance(jsondata, str | bytes | bytearray):
        parsed_json = json.loads(jsondata)
    elif isinstance(jsondata, dict):
        parsed_json = jsondata
    else:
        parsed_json = {}

    # Convert keys to snake_case
    parsed_json = {
        re.sub("([A-Z])", r"_\1", k).lower(): v for k, v in parsed_json.items()
    }
    # Only include keys that are fields in the dataclass
    data_dict = {f.name: parsed_json.get(f.name) for f in fields(clazz)}
    return clazz(**data_dict)
