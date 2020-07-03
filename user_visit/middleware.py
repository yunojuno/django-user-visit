import datetime
import logging
import typing

from django.core.cache import cache
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from .models import RequestParser, UserVisit
from .settings import RECORDING_DISABLED

logger = logging.getLogger(__name__)


def seconds_to_midnight() -> int:
    """Calculate seconds from now to midnight."""
    now = timezone.now()
    tomorrow = now + datetime.timedelta(days=1)
    midnight = datetime.datetime.combine(tomorrow, datetime.time.min, tzinfo=now.tzinfo)
    return (midnight - now).seconds


def check_cache(parser: RequestParser) -> bool:
    """Check cache for parser and return True if the hashes match."""
    return cache.get(parser.cache_key) == hash(parser)


def update_cache(parser: RequestParser) -> None:
    """Cache instance of a RequestParser."""
    cache.set(parser.cache_key, hash(parser), timeout=seconds_to_midnight())


class UserVisitMiddleware:
    """
    Middleware to record user visits.

    This middleware caches visits on a daily basis. Same user, device, IP
    and session - no new visit.

    """

    def __init__(self, get_response: typing.Callable) -> None:
        if RECORDING_DISABLED:
            raise MiddlewareNotUsed("UserVisit recording has been disabled")
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> typing.Optional[HttpResponse]:
        # this will fail hard if session or authentication middleware are
        # not configured.
        if request.user.is_anonymous:
            return self.get_response(request)

        parser = RequestParser(request)
        if check_cache(parser):
            return self.get_response(request)

        uv = UserVisit.objects.record(request)
        update_cache(parser)
        logger.debug("Recorded and cached new user visit: %r", uv)

        return self.get_response(request)
