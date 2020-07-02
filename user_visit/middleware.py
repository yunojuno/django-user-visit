import typing

from django.http import HttpRequest, HttpResponse

from .models import UserVisit


class UserVisitMiddleware:
    """Middleware to record user visits."""

    def __init__(self, get_response: typing.Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> typing.Optional[HttpResponse]:
        # this will fail hard if session or authentication middleware are
        # not configured.
        if request.user.is_authenticated:
            UserVisit.objects.record(request)

        return self.get_response(request)
