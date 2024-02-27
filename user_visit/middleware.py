import inspect
import logging
import typing

import django.db
from asgiref.sync import sync_to_async
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.decorators import sync_and_async_middleware

from user_visit.models import UserVisit

from .settings import DUPLICATE_LOG_LEVEL, RECORDING_BYPASS, RECORDING_DISABLED

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


# Atomic transactions are not supported async yet
# https://docs.djangoproject.com/en/5.0/topics/async/
asave_user_visit = sync_to_async(save_user_visit)


@sync_to_async
def aget_user_from_request(request):
    return request.user if bool(request.user) else None


@sync_and_async_middleware
def UserVisitMiddleware(  # noqa
    get_response: typing.Callable[
        [HttpRequest],
        HttpResponse | typing.Coroutine[typing.Any, typing.Any, HttpResponse],
    ],
):
    if RECORDING_DISABLED:
        raise MiddlewareNotUsed("UserVisit recording has been disabled")

    if inspect.iscoroutinefunction(get_response):

        async def middleware(request: HttpRequest) -> typing.Optional[HttpResponse]:
            user = await aget_user_from_request(request)
            if user.is_anonymous:
                return await typing.cast(typing.Awaitable, get_response(request))

            if RECORDING_BYPASS(request):
                return await typing.cast(typing.Awaitable, get_response(request))

            uv = UserVisit.objects.build(request, timezone.now())
            if not await UserVisit.objects.filter(hash=uv.hash).aexists():
                await asave_user_visit(uv)

            return await typing.cast(typing.Awaitable, get_response(request))

    else:

        def middleware(request: HttpRequest) -> typing.Optional[HttpResponse]:
            if request.user.is_anonymous:
                return get_response(request)

            if RECORDING_BYPASS(request):
                return get_response(request)

            uv = UserVisit.objects.build(request, timezone.now())
            if not UserVisit.objects.filter(hash=uv.hash).exists():
                save_user_visit(uv)

            return get_response(request)

    return middleware
