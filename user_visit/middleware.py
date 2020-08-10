import logging
import typing

import django.db
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from user_visit.models import UserVisit

from .settings import RECORDING_DISABLED

logger = logging.getLogger(__name__)


def save_user_visit(user_visit: UserVisit) -> None:
    """Save the user visit and handle db.IntegrityError."""
    try:
        user_visit.save()
    except django.db.IntegrityError:
        logger.warning("Error saving user visit (hash='%s')", user_visit.hash)


def update_user_visit(uv: UserVisit) -> None:
    """Update the user visit and handle db.IntegrityError."""
    try:
        user_visit = UserVisit.objects.get(hash=uv.hash)
    except django.db.IntegrityError as error:
        logger.warning("Error updating user visit: ", str(error))
    else:
        user_visit.update()


class UserVisitMiddleware:
    """Middleware to record user visits."""

    def __init__(self, get_response: typing.Callable) -> None:
        if RECORDING_DISABLED:
            raise MiddlewareNotUsed("UserVisit recording has been disabled")
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> typing.Optional[HttpResponse]:
        if request.user.is_anonymous:
            return self.get_response(request)

        uv = UserVisit.objects.build(request, timezone.now())
        if not UserVisit.objects.filter(hash=uv.hash).exists():
            save_user_visit(uv)
        else:
            update_user_visit(uv)

        return self.get_response(request)
