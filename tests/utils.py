from unittest import mock

from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpRequest


def mock_request(is_authenticated: bool = True) -> mock.Mock:
    return mock.Mock(
        spec=HttpRequest,
        user=User() if is_authenticated else AnonymousUser(),
        session=mock.Mock(session_key="test"),
        headers={"X-Forwarded-For": "127.0.0.1", "User-Agent": "Chrome 99"},
        META={"REMOTE_ADDR": "192.168.0.1"},
    )
