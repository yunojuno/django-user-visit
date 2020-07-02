import pytest
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from user_visit.middleware import UserVisitMiddleware
from user_visit.models import UserVisitManager


class MockSession(object):
    """Fake Session model used to support `session_key` property."""

    @property
    def session_key(self):
        return "test"

# @pytest.mark.django_db
class TestUserVisitMiddleware:
    """RequestTokenMiddleware tests."""

    def get_request(self, user):
        request = RequestFactory().get("/")
        request.session = MockSession()
        request.user = user or AnonymousUser()
        return request

    def get_middleware(self):
        return UserVisitMiddleware(get_response=lambda r: HttpResponse())

    @mock.patch.object(UserVisitManager, "record")
    def test_middleware__anon(self, mock_record):
        """Check that anonymous users are ignored."""
        request = self.get_request(AnonymousUser())
        middleware = self.get_middleware()
        middleware(request)
        assert mock_record.call_count == 0

    @mock.patch.object(UserVisitManager, "record")
    def test_middleware__auth(self, mock_record):
        """Check that authenticated users are recorded."""
        request = self.get_request(User())
        middleware = self.get_middleware()
        middleware(request)
        assert mock_record.call_count == 1
