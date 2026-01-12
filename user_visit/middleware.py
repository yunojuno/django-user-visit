import inspect
import logging
import typing

import django.db
from asgiref.sync import async_to_sync, sync_to_async
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.decorators import sync_and_async_middleware

from user_visit.models import UserVisit

from .settings import (
    DUPLICATE_LOG_LEVEL,
    FORCE_ASYNC,
    RECORDING_BYPASS,
    RECORDING_DISABLED,
)

logger = logging.getLogger(__name__)


@django.db.transaction.atomic
def save_user_visit(user_visit: UserVisit) -> None:
    """Save the user visit and handle db.IntegrityError."""
    try:
        user_visit.save()
    except django.db.IntegrityError:
        getattr(logger, DUPLICATE_LOG_LEVEL)(
            "Error saving user visit (hash='%s')", user_visit.hash
        )


def _check_recording_bypass(request: HttpRequest) -> bool:
    """
    Check the RECORDING_BYPASS setting, handling both sync and async callables.

    In the sync context, if RECORDING_BYPASS is an async callable, we need to
    run it with async_to_sync to get the actual boolean result. Simply calling
    an async function returns a coroutine object, which is always truthy.
    """
    if inspect.iscoroutinefunction(RECORDING_BYPASS):
        return async_to_sync(RECORDING_BYPASS)(request)
    return RECORDING_BYPASS(request)


async def _check_recording_bypass_async(request: HttpRequest) -> bool:
    """
    Check the RECORDING_BYPASS setting asynchronously.

    Handles both sync and async callables appropriately.
    """
    if inspect.iscoroutinefunction(RECORDING_BYPASS):
        return await RECORDING_BYPASS(request)
    return RECORDING_BYPASS(request)


@sync_and_async_middleware
def UserVisitMiddleware(get_response: typing.Callable) -> typing.Callable:
    """Middleware to record user visits.

    Automatically supports both sync and async request/response cycles.
    When FORCE_ASYNC is True and the middleware is called in sync context
    (due to legacy sync middleware in the chain), it will use async_to_sync
    to run async processing logic.
    """
    if RECORDING_DISABLED:
        raise MiddlewareNotUsed("UserVisit recording has been disabled")

    # Check if get_response is async
    if inspect.iscoroutinefunction(get_response):
        # ASYNC PATH: Full async middleware
        async def async_middleware(
            request: HttpRequest,
        ) -> typing.Optional[HttpResponse]:
            await _process_visit_async(request)
            return await get_response(request)

        return async_middleware

    else:
        # SYNC PATH: Sync middleware, but may use async internally
        def sync_middleware(request: HttpRequest) -> typing.Optional[HttpResponse]:
            if FORCE_ASYNC:
                # Force async processing in sync context
                async_to_sync(_process_visit_async)(request)
            else:
                # Pure sync processing
                _process_visit_sync(request)

            return get_response(request)

        return sync_middleware


def _process_visit_sync(request: HttpRequest) -> None:
    if request.user.is_anonymous:
        return

    if _check_recording_bypass(request):
        return

    uv = UserVisit.objects.build(request, timezone.now())
    if not UserVisit.objects.filter(hash=uv.hash).exists():
        save_user_visit(uv)


async def _process_visit_async(request: HttpRequest) -> None:
    """Asynchronous visit processing.

    Used when:
    - Middleware is in async context (full async middleware chain), OR
    - Middleware is in sync context but FORCE_ASYNC is True

    In the latter case, this is called via async_to_sync(), so the async
    operations are properly handled without blocking.
    """
    # Check if user is anonymous
    is_anonymous = await sync_to_async(lambda: request.user.is_anonymous)()
    if is_anonymous:
        return

    # Check recording bypass
    if await _check_recording_bypass_async(request):
        return

    # Build the visit object
    uv = await sync_to_async(UserVisit.objects.build)(request, timezone.now())

    # Check if visit already exists
    exists = await sync_to_async(
        lambda: UserVisit.objects.filter(hash=uv.hash).exists()
    )()

    if not exists:
        # Save the visit
        await sync_to_async(save_user_visit)(uv)
