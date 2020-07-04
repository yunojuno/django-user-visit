import logging
import typing

from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from .models import UserVisit, UserVisitRequestParser
from .settings import RECORDING_DISABLED

logger = logging.getLogger(__name__)

SESSION_KEY = "user_visit.request_hash"


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
        # this will fail hard if session or auth middleware are not configured.
        if request.user.is_anonymous:
            return self.get_response(request)

        parser = UserVisitRequestParser(request, timezone.now())
        if request.session.get(SESSION_KEY, "") == hash(parser):
            return self.get_response(request)

        uv = UserVisit.objects.record(request, parser.timestamp)
        request.session[SESSION_KEY] = hash(parser)
        logger.debug("Recorded new user visit: %r", uv)

        return self.get_response(request)
