from unittest import mock

import freezegun
import pytest
from django.contrib.auth.models import User
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpResponse
from django.test import Client

from user_visit.middleware import SESSION_KEY, UserVisitMiddleware
from user_visit.models import UserVisitManager, UserVisitRequestParser

from .utils import mock_request


@pytest.mark.django_db
class TestUserVisitMiddleware:
    """RequestTokenMiddleware tests."""

    def get_middleware(self):
        return UserVisitMiddleware(get_response=lambda r: HttpResponse())

    @mock.patch.object(UserVisitManager, "record")
    def test_middleware__anon(self, mock_record):
        """Check that anonymous users are ignored."""
        client = Client()
        client.get("/")
        assert mock_record.call_count == 0

    @mock.patch.object(UserVisitManager, "record")
    def test_middleware__auth(self, mock_record):
        """Check that authenticated users are recorded."""
        client = Client()
        client.force_login(User.objects.create_user("Fred"))
        client.get("/")
        assert mock_record.call_count == 1

    @mock.patch.object(UserVisitManager, "record")
    def test_middleware__same_day(self, mock_record):
        """Check that same user, same day, gets only one visit recorded."""
        client = Client()
        client.force_login(User.objects.create_user("Fred"))
        client.get("/")
        client.get("/")
        assert mock_record.call_count == 1

    @mock.patch.object(UserVisitManager, "record")
    def test_middleware__new_day(self, mock_record):
        """Check that same user, new day, gets new visit."""
        user = User.objects.create_user("Fred")
        client = Client()
        client.force_login(user)
        with freezegun.freeze_time("2020-07-04"):
            client.get("/")
            assert mock_record.call_count == 1
        # new day, new visit
        with freezegun.freeze_time("2020-07-05"):
            client.get("/")
            assert mock_record.call_count == 2

    @mock.patch.object(UserVisitRequestParser, "__hash__")
    @mock.patch.object(UserVisitManager, "record")
    def test_middleware__new_request_hash(self, mock_record, mock_hash):
        """Record a new visit if the request hash is different."""
        user = User.objects.create_user("Fred")
        client = Client()
        client.force_login(user)
        mock_hash.return_value = 0
        client.get("/")
        mock_hash.return_value = 1
        client.get("/")
        assert mock_record.call_count == 2

    @mock.patch("user_visit.middleware.RECORDING_DISABLED", True)
    def test_middleware__disabled(self):
        """Test update_cache and check_cache functions."""
        with pytest.raises(MiddlewareNotUsed):
            UserVisitMiddleware(get_response=lambda r: HttpResponse())


# class TestMiddlewareFunctions:

#     @pytest.mark.parametrize(
#         "xff,remote,output",
#         (
#             ("", "", ""),
#             ("127.0.0.1", "", "127.0.0.1"),
#             ("127.0.0.1,192.168.0.1", "", "127.0.0.1"),
#             ("127.0.0.1", "192.168.0.1", "127.0.0.1"),
#             ("", "192.168.0.1", "192.168.0.1"),
#         ),
#     )
#     def test_remote_addr(self, xff, remote, output):
#         request = mock_request()
#         request.headers["X-Forwarded-For"] = xff
#         request.META["REMOTE_ADDR"] = remote
#         assert parse_remote_addr(request) == output

#     # @pytest.mark.django_db
#     # def test_hash(self):
#     #     r1 = mock_request()
#     #     r2 = mock_request()
#     #     user = User.objects.create(username="Ginger")
#     #     r1.user = r2.user = user
#     #     assert r1 != r2
#     #     p1 = RequestParser(r1)
#     #     p2 = RequestParser(r2)
#     #     assert hash(p1) == hash(p2)

#     # def test_hash__different_date(self):
#     #     r1 = mock_request()
#     #     r2 = mock_request()
#     #     r1.user = r2.user = User(pk=1)
#     #     p1 = RequestParser(r1)
#     #     p1.date = p1.date + datetime.timedelta(days=1)
#     #     p2 = RequestParser(r2)
#     #     assert hash(p1) != hash(p2)
