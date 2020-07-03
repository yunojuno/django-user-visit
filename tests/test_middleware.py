from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from user_visit.middleware import UserVisitMiddleware, check_cache, update_cache
from user_visit.models import RequestParser, UserVisitManager

from .utils import mock_request


class TestUserVisitMiddleware:
    """RequestTokenMiddleware tests."""

    def get_middleware(self):
        return UserVisitMiddleware(get_response=lambda r: HttpResponse())

    @mock.patch.object(UserVisitManager, "record")
    def test_middleware__anon(self, mock_record):
        """Check that anonymous users are ignored."""
        request = mock_request(is_authenticated=False)
        middleware = self.get_middleware()
        middleware(request)
        assert mock_record.call_count == 0
        cache.clear()

    @pytest.mark.django_db
    @mock.patch.object(UserVisitManager, "record")
    def test_middleware__auth(self, mock_record):
        """Check that authenticated users are recorded."""
        user = User.objects.create_user("Fred")
        request = mock_request()
        request.user = user
        middleware = self.get_middleware()
        middleware(request)
        assert mock_record.call_count == 1
        cache.clear()

    @pytest.mark.django_db
    @mock.patch.object(UserVisitManager, "record")
    def test_middleware__cache(self, mock_record):
        """Check that cached visits are not recorded."""
        request = mock_request()
        request.user = User.objects.create_user("Fred")
        parser = RequestParser(request)
        middleware = self.get_middleware()
        update_cache(parser)
        assert check_cache(parser)
        middleware(request)
        assert mock_record.call_count == 0
        cache.clear()
        middleware(request)
        assert mock_record.call_count == 1
        cache.clear()

    @pytest.mark.django_db
    @mock.patch.object(UserVisitManager, "record")
    def test_middleware__cache_manager(self, mock_record):
        """Test update_cache and check_cache functions."""
        cache.clear()
        request = mock_request()
        request.user = User.objects.create_user("Fred")
        parser = RequestParser(request)
        # nothing in the cache
        assert cache.get(parser.cache_key) is None
        assert not check_cache(parser)
        update_cache(parser)
        # cache populated as expected
        assert check_cache(parser)
        assert cache.get(parser.cache_key) == hash(parser)
        cache.clear()
