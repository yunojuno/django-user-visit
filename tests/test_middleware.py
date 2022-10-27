from unittest import mock

import django.db
import freezegun
import pytest
from django.contrib.auth.models import User
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpResponse
from django.test import Client
from django.utils import timezone

from user_visit.middleware import UserVisitMiddleware, save_user_visit
from user_visit.models import UserVisit, UserVisitManager


@pytest.mark.django_db
def test_save_user_visit():
    """Test standalone save method handles db.IntegrityError."""
    user = User.objects.create(username="Yoda")
    timestamp = timezone.now()
    uv = UserVisit.objects.create(
        user=user,
        session_key="test",
        ua_string="Chrome",
        remote_addr="127.0.0.1",
        timestamp=timestamp,
    )
    uv.id = None
    save_user_visit(uv)


@pytest.mark.django_db
@mock.patch("user_visit.middleware.logger")
def test_save_user_visit__duplicate(mock_logger):
    """Test standalone save method handles db.IntegrityError."""
    user = User.objects.create(username="Yoda")
    timestamp = timezone.now()
    uv = UserVisit.objects.create(
        user=user,
        session_key="test",
        ua_string="Chrome",
        remote_addr="127.0.0.1",
        timestamp=timestamp,
    )
    uv.id = None
    # this should raise an IntegrityError as the object hash hasn't changed.
    save_user_visit(uv)
    assert mock_logger.warning.call_count == 1


@pytest.mark.django_db
@mock.patch("user_visit.middleware.logger")
@mock.patch("user_visit.middleware.DUPLICATE_LOG_LEVEL", "debug")
def test_save_user_visit__duplicate__log_levels(mock_logger):
    """Test standalone save method handles db.IntegrityError."""
    user = User.objects.create(username="Yoda")
    timestamp = timezone.now()
    uv = UserVisit.objects.create(
        user=user,
        session_key="test",
        ua_string="Chrome",
        remote_addr="127.0.0.1",
        timestamp=timestamp,
    )
    uv.id = None
    save_user_visit(uv)
    assert mock_logger.warning.call_count == 0
    assert mock_logger.debug.call_count == 1



@pytest.mark.django_db
class TestUserVisitMiddleware:
    """RequestTokenMiddleware tests."""

    def get_middleware(self):
        return UserVisitMiddleware(get_response=lambda r: HttpResponse())

    def test_middleware__anon(self):
        """Check that anonymous users are ignored."""
        client = Client()
        with mock.patch.object(UserVisitManager, "build") as build:
            client.get("/")
            assert build.call_count == 0

    def test_middleware__auth(self):
        """Check that authenticated users are recorded."""
        client = Client()
        client.force_login(User.objects.create_user("Fred"))
        client.get("/")
        assert UserVisit.objects.count() == 1

    def test_middleware__same_day(self):
        """Check that same user, same day, gets only one visit recorded."""
        client = Client()
        client.force_login(User.objects.create_user("Fred"))
        client.get("/")
        client.get("/")
        assert UserVisit.objects.count() == 1

    def test_middleware__new_day(self):
        """Check that same user, new day, gets new visit."""
        user = User.objects.create_user("Fred")
        client = Client()
        client.force_login(user)
        with freezegun.freeze_time("2020-07-04"):
            client.get("/")
            assert UserVisit.objects.count() == 1
        # new day, new visit
        with freezegun.freeze_time("2020-07-05"):
            client.get("/")
            assert UserVisit.objects.count() == 2

    def test_middleware__db_integrity_error(self):
        """Check that a failing save doesn't kill middleware."""
        user = User.objects.create_user("Fred")
        client = Client()
        client.force_login(user)
        with mock.patch.object(UserVisit, "save", side_effect=django.db.IntegrityError):
            client.get("/")

    @mock.patch("user_visit.middleware.RECORDING_DISABLED", True)
    def test_middleware__disabled(self):
        """Test update_cache and check_cache functions."""
        with pytest.raises(MiddlewareNotUsed):
            UserVisitMiddleware(get_response=lambda r: HttpResponse())

    @mock.patch(
        "user_visit.middleware.RECORDING_BYPASS",
        lambda r: r.user.username == "Fred",
    )
    @pytest.mark.parametrize("username", ["Fred", "Ginger"])
    def test_middleware__bypassed(self, username: str) -> None:
        """Test the RECORDING_BYPASS function."""
        user = User.objects.create_user(username)
        client = Client()
        client.force_login(user)
        client.get("/")
        count = 0 if user.username == "Fred" else 1
        assert UserVisit.objects.count() == count
