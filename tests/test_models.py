import datetime
from unittest import mock

import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpRequest
from django.utils import timezone
from user_visit.models import RequestParser, UserVisit

from .utils import mock_request

ONE_DAY = datetime.timedelta(days=1)
ONE_SEC = datetime.timedelta(seconds=1)


class TestRequestParser:
    def mock_session(self):
        return mock.Mock(session_key="test")

    def test_init__no_session(self):
        request = mock_request()
        request.session = None
        with pytest.raises(ValueError, match=r"Request object has no session."):
            RequestParser(request)

    def test_init__no_user(self):
        request = mock_request()
        request.user = None
        with pytest.raises(ValueError, match=r"Request object has no user."):
            RequestParser(request)

    def test_init__anon(self):
        request = mock_request(is_authenticated=False)
        with pytest.raises(ValueError, match=r"Request user is anonymous."):
            RequestParser(request)

    @pytest.mark.parametrize(
        "xff,remote,output",
        (
            ("", "", ""),
            ("127.0.0.1", "", "127.0.0.1"),
            ("127.0.0.1,192.168.0.1", "", "127.0.0.1"),
            ("127.0.0.1", "192.168.0.1", "127.0.0.1"),
            ("", "192.168.0.1", "192.168.0.1"),
        ),
    )
    def test_remote_addr(self, xff, remote, output):
        request = mock_request()
        request.headers["X-Forwarded-For"] = xff
        request.META["REMOTE_ADDR"] = remote
        parser = RequestParser(request)
        assert parser.remote_addr == output

    @pytest.mark.parametrize("ua_string", ("", "Chrome"))
    def test_ua_string(self, ua_string):
        request = mock_request()
        request.headers["User-Agent"] = ua_string
        parser = RequestParser(request)
        assert parser.ua_string == ua_string

    @pytest.mark.django_db
    def test_hash(self):
        r1 = mock_request()
        r2 = mock_request()
        user = User.objects.create(username="Ginger")
        r1.user = r2.user = user
        assert r1 != r2
        p1 = RequestParser(r1)
        p2 = RequestParser(r2)
        assert hash(p1) == hash(p2)

    def test_hash__different_date(self):
        r1 = mock_request()
        r2 = mock_request()
        r1.user = r2.user = User(pk=1)
        p1 = RequestParser(r1)
        p1.date = p1.date + datetime.timedelta(days=1)
        p2 = RequestParser(r2)
        assert hash(p1) != hash(p2)


class TestUserVisit:

    UA_STRING = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36"

    def test_user_agent(self):
        uv = UserVisit(ua_string=TestUserVisit.UA_STRING)
        assert str(uv.user_agent) == "PC / Mac OS X 10.15.5 / Chrome 83.0.4103"


@pytest.mark.django_db
class TestUserVisitManager:
    def test_record(self):
        request = mock_request()
        request.user = User.objects.create_user(username="test")
        assert UserVisit.objects.count() == 0
        uv = UserVisit.objects.record(request)
        assert UserVisit.objects.count() == 1
        assert uv.user == request.user
        assert uv.session_key == "test"
        assert uv.remote_addr == "127.0.0.1"
        assert uv.ua_string == "Chrome 99"

    def test_record_duplicate(self):
        """Test recording a new visit on the same day does not create a new record."""
        request = mock_request()
        request.user = User.objects.create_user(username="test")
        assert UserVisit.objects.count() == 0
        uv1 = UserVisit.objects.record(request)
        uv2 = UserVisit.objects.record(request, timestamp=uv1.timestamp + ONE_SEC)
        assert UserVisit.objects.count() == 1
        assert uv1 == uv2

    def test_record_different_day(self):
        """Test same user, different day."""
        request = mock_request()
        request.user = User.objects.create_user(username="test")
        timestamp = timezone.now()
        uv1 = UserVisit.objects.record(request, timestamp=timestamp)
        uv2 = UserVisit.objects.record(request, timestamp=timestamp + ONE_DAY)
        assert UserVisit.objects.count() == 2
        assert uv1.user == uv2.user
        assert uv1.date != uv2.date
        assert uv1.remote_addr == uv2.remote_addr
        assert uv1.session_key == uv2.session_key
        assert uv1.ua_string == uv2.ua_string

    def test_record_ip_address(self):
        """Test same user, different IP."""
        request = mock_request()
        request.user = User.objects.create_user(username="test")
        uv1 = UserVisit.objects.record(request)
        request.headers["X-Forwarded-For"] = "192.168.0.1"
        uv2 = UserVisit.objects.record(request)
        assert UserVisit.objects.count() == 2
        assert uv1.user == uv2.user
        assert uv1.date == uv2.date
        assert uv1.remote_addr != uv2.remote_addr
        assert uv1.session_key == uv2.session_key
        assert uv1.ua_string == uv2.ua_string

    def test_record_session(self):
        """Test same user, different session."""
        request = mock_request()
        request.user = User.objects.create_user(username="test")
        uv1 = UserVisit.objects.record(request)
        request.session.session_key = "bar"
        uv2 = UserVisit.objects.record(request)
        assert UserVisit.objects.count() == 2
        assert uv1.user == uv2.user
        assert uv1.date == uv2.date
        assert uv1.remote_addr == uv2.remote_addr
        assert uv1.session_key != uv2.session_key
        assert uv1.ua_string == uv2.ua_string

    def test_record_ua_string(self):
        """Test same user, different device."""
        request = mock_request()
        request.user = User.objects.create_user(username="test")
        uv1 = UserVisit.objects.record(request)
        request.headers["User-Agent"] = "Chrome 100"
        uv2 = UserVisit.objects.record(request)
        assert UserVisit.objects.count() == 2
        assert uv1.user == uv2.user
        assert uv1.date == uv2.date
        assert uv1.remote_addr == uv2.remote_addr
        assert uv1.session_key == uv2.session_key
        assert uv1.ua_string != uv2.ua_string

    def test_record_multiple_objects(self):
        """Test what happens if duplicate date records exist."""
        request = mock_request()
        request.user = User.objects.create_user(username="test")
        uv1 = UserVisit.objects.record(request)
        uv2 = UserVisit.objects.record(request, timestamp=uv1.timestamp + ONE_DAY)
        assert UserVisit.objects.count() == 2
        # revert uv2 to the same day as uv1
        uv2.timestamp -= ONE_DAY
        uv2.save()
        assert uv1.user == uv2.user
        assert uv1.date == uv2.date
        assert uv1.remote_addr == uv2.remote_addr
        assert uv1.session_key == uv2.session_key
        assert uv1.ua_string == uv2.ua_string
        # we have two duplicates - now lets try a third
        uv3 = UserVisit.objects.record(request)
        assert UserVisit.objects.count() == 2
        assert uv3 == uv2
