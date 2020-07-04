import logging
import typing

import django.db
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from user_visit.models import UserVisit

from .settings import RECORDING_DISABLED

logger = logging.getLogger(__name__)

# used to store unique hash of the visit
SESSION_KEY = "user_visit.hash"


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
        # this method will fail hard if session or auth middleware are not configured.
        if request.user.is_anonymous:
            return self.get_response(request)

        uv = UserVisit.objects.build(request, timezone.now())
        if request.session.get(SESSION_KEY, "") == uv.hash:
            return self.get_response(request)

        try:
            uv.save()
        except django.db.IntegrityError:
            logger.warning("Unable to record user visit - duplicate request hash")
        else:
            request.session[SESSION_KEY] = uv.hash
        return self.get_response(request)
