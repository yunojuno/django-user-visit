import logging
import typing

import django.db
from django.contrib.sessions.backends.base import SessionBase
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from user_visit.models import UserVisit

from .settings import RECORDING_DISABLED

logger = logging.getLogger(__name__)

# used to store unique hash of the visit
SESSION_KEY = "user_visit.hash"


def visit_is_cached(user_visit: UserVisit, session: SessionBase) -> bool:
    """Return True if the visit is already in the request session."""
    if not user_visit.hash:
        return False
    return session.get(SESSION_KEY) == user_visit.hash


def cache_visit(user_visit: UserVisit, session: SessionBase) -> None:
    """Cache UserVisit in session."""
    if not user_visit.hash:
        return
    session[SESSION_KEY] = user_visit.hash


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
        if visit_is_cached(uv, request.session):
            return self.get_response(request)

        try:
            uv.save()
        except django.db.IntegrityError as ex:
            logger.warning("Error saving user visit (hash='%s'): %s", uv.hash, ex)
            logger.debug("Session hash='%s'", request.session.get(SESSION_KEY, ""))
            logger.debug("UserVisit.session_key='%s'", uv.session_key)
            logger.debug("UserVisit.remote_addr='%s'", uv.remote_addr)
            logger.debug("UserVisit.ua_string='%s'", uv.ua_string)
            logger.debug("UserVisit.user_id='%s'", uv.user_id)
        # if the database has raised an IntegrityError it means the hash is already
        # stored, but is not in the session for some reason.
        cache_visit(uv, request.session)
        return self.get_response(request)
