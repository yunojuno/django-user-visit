import logging
from typing import Callable, Optional

from django.core.exceptions import MiddlewareNotUsed
from django.db import transaction, IntegrityError
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from user_visit.models import UserVisit
from .settings import DUPLICATE_LOG_LEVEL, RECORDING_BYPASS, RECORDING_DISABLED

logger = logging.getLogger(__name__)


def log_duplicate_visit(user_visit_hash: str) -> None:
    """Log a message when a duplicate user visit is detected."""
    log_method = getattr(logger, DUPLICATE_LOG_LEVEL)
    log_method("Error saving user visit (hash='%s')", user_visit_hash)


def save_user_visit(user_visit: UserVisit) -> None:
    """Save the user visit."""
    try:
        user_visit.save()
    except IntegrityError:
        log_duplicate_visit(user_visit.hash)


class UserVisitMiddleware:
    """Middleware to record user visits."""

    def __init__(self, get_response: Callable) -> None:
        if RECORDING_DISABLED:
            raise MiddlewareNotUsed("UserVisit recording has been disabled")
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Process each request to record user visits."""
        # Do not record visits for anonymous users or if bypassed by settings
        if request.user.is_anonymous or RECORDING_BYPASS(request):
            return self.get_response(request)

        # Build a UserVisit instance and check for duplicates
        user_visit = UserVisit.objects.build(request, timezone.now())
        duplicate_exists = UserVisit.objects.filter(hash=user_visit.hash).exists()

        if not duplicate_exists:
            # Save the user visit instance when the database commits successfully
            transaction.on_commit(lambda: save_user_visit(user_visit))

        return self.get_response(request)
