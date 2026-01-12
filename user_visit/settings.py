from os import getenv
from typing import Any, Callable

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpRequest


def _env_or_setting(key: str, default: Any, cast_func: Callable = lambda x: x) -> Any:
    return cast_func(getenv(key) or getattr(settings, key, default))


RECORDING_DISABLED = _env_or_setting(
    "USER_VISIT_RECORDING_DISABLED", False, lambda x: bool(x)
)


# function that takes a request object and returns a dictionary of info
# that will be stored against the request. By default returns empty
# dict. canonical example of a use case for this is extracting GeoIP
# info.
REQUEST_CONTEXT_EXTRACTOR: Callable[[HttpRequest], dict] = getattr(
    settings, "USER_VISIT_REQUEST_CONTEXT_EXTRACTOR", lambda r: {}
)


# Can be used to override the JSON encoder used for the context JSON
# fields
REQUEST_CONTEXT_ENCODER = getattr(
    settings, "USER_VISIT_CONTEXT_ENCODER", DjangoJSONEncoder
)


# function used to bypass recording for specific requests - this can be
# used to e.g. prevent staff users from being recorded. The function
# must be a Callable that takes a HttpRequest arg and returns a bool -
# if True then the recording is bypassed.
RECORDING_BYPASS = getattr(settings, "USER_VISIT_RECORDING_BYPASS", lambda r: False)


# The log level to use when logging duplicate hashes. This is WARNING by
# default, but if it's noisy you can turn this down by setting this
# value. Must be one of "debug", "info", "warning", "error"
DUPLICATE_LOG_LEVEL: str = getattr(
    settings, "USER_VISIT_DUPLICATE_LOG_LEVEL", "warning"
).lower()


# FORCE_ASYNC: Forces async processing even when middleware is called in sync context
#
# When True, the middleware will use async_to_sync to run async logic in the sync
# code path. This is useful when you have legacy sync-only middleware in your chain
# that prevents Django's ASGI handler from calling the async __acall__ method.
#
# When False (default), the middleware will:
#   - Use pure async logic if called as async (get_response is async)
#   - Use pure sync logic if called as sync (get_response is sync)
#
# Note: This setting has no effect on async request/response cycles - async views
# and async-capable middleware will always use the async path naturally.
#
# Typical use cases:
#   - Django projects with many legacy sync-only middleware
#   - ASGI servers (Daphne, Uvicorn) where you want consistent async patterns
#   - When you're migrating to async and want async patterns even in sync contexts
#
# Can be set via:
#   - Django setting: USER_VISIT_FORCE_ASYNC = True
#   - Environment variable: USER_VISIT_FORCE_ASYNC=1
FORCE_ASYNC = _env_or_setting("USER_VISIT_FORCE_ASYNC", False, lambda x: bool(x))
