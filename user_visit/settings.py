from os import getenv
from typing import Any, Callable

from django.conf import settings


def _env_or_setting(key: str, default: Any, cast_func: Callable = lambda x: x) -> Any:
    return cast_func(getenv(key) or getattr(settings, key, default))


RECORDING_DISABLED = _env_or_setting(
    "USER_VISIT_RECORDING_DISABLED", False, lambda x: bool(x)
)
