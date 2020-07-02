import typing

from django.http import HttpRequest, HttpResponse

from .models import UserVisit


class RequestParser:
    """Parse HttpRequest object."""

    def __init__(self, request: HttpRequest) -> None:
        self.request = request

    @property
    def remote_addr(self) -> str:
        """Extract client IP from request."""
        x_forwarded_for = self.request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return self.request.META.get("REMOTE_ADDR", "")

    @property
    def session_key(self) -> str:
        """Extract session id from request."""
        return self.request.session.session_key or ""

    @property
    def ua_string(self) -> str:
        """Extract client user-agent from request."""
        return self.request.headers.get("User-Agent", "")


def record_user_visit(request: HttpRequest) -> None:
    """Record a new UserVisit if none exists."""
    user = request.user
    if not user:
        return
    if user.is_anonymous:
        return
    parser = RequestParser(request)
    UserVisit.objects.get_or_create(
        user=user,
        session_key=parser.session_key,
        ua_string=parser.ua_string,
        remote_addr=parser.remote_addr,
    )


class UserVisitMiddleware:
    """Middleware to record user visits."""

    def __init__(self, get_response: typing.Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> typing.Optional[HttpResponse]:
        record_user_visit(request)
        return self.get_response(request)
