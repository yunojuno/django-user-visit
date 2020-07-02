import typing

from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from .models import UserVisit


class UserVisitMiddleware:
    """Middleware to record user visits."""

    def __init__(self, get_response: typing.Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> typing.Optional[HttpResponse]:
        if request.user and request.user.is_authenticated:
            UserVisit.objects.record(request)
        return self.get_response(request)
