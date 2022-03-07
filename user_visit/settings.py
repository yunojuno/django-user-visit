from os import getenv
from typing import Any, Callable

from django.conf import settings
from django.http import HttpRequest


def _env_or_setting(key: str, default: Any, cast_func: Callable = lambda x: x) -> Any:
    return cast_func(getenv(key) or getattr(settings, key, default))


RECORDING_DISABLED = _env_or_setting(
    "USER_VISIT_RECORDING_DISABLED", False, lambda x: bool(x)
)


# function that takes a request object and returns a dictionary of info
# that will be stored against the request. By default returns empty dict.
# canonical example of a use case for this is extracting GeoIP info.
CUSTOM_REQUEST_EXTRACTOR: Callable[[HttpRequest], dict] = getattr(
    settings, "USER_VISIT_CUSTOM_REQUEST_EXTRACTOR", lambda r: {}
)
