from unittest import mock

import django.db
import freezegun
import pytest
from django.contrib.auth.models import User
from django.contrib.sessions.backends.base import SessionBase
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpResponse
from django.test import Client
from user_visit.middleware import (
    SESSION_KEY,
    UserVisitMiddleware,
    cache_visit,
    visit_is_cached,
)
from user_visit.models import UserVisit, UserVisitManager


class TestMiddlewareFunctions:
    @pytest.mark.parametrize(
        "hash_value,cached_value,result",
        (
            ("", "", False),
            ("", "foo", False),
            ("foo", "", False),
            ("foo", "bar", False),
            ("bar", "bar", True),
        ),
    )
    def test_visit_is_cached(self, hash_value, cached_value, result):
        session = {SESSION_KEY: cached_value}
        visit = UserVisit(hash=hash_value)
        assert visit_is_cached(visit, session) == result

    @pytest.mark.parametrize("hash_value,cached", (("", False), ("bar", True),))
    def test_cache_visit(self, hash_value, cached):
        """Check that hash is not stored if empty."""
        session = {}
        visit = UserVisit(hash=hash_value)
        assert SESSION_KEY not in session
        cache_visit(visit, session)
        assert (SESSION_KEY in session) == cached


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

    def test_middleware__duplicate(self):
        """Check that middleware handles duplicate uuids."""
        user = User.objects.create_user("Fred")
        client = Client()
        client.force_login(user)
        client.get("/")
        with mock.patch("user_visit.middleware.visit_is_cached", return_value=False):
            client.get("/")

    def test_middleware__db_integrity_error(self):
        """Check that middleware stores hash when db raises duplicate hash error."""
        user = User.objects.create_user("Fred")
        client = Client()
        client.force_login(user)
        assert not client.session.get(SESSION_KEY)
        with mock.patch.object(UserVisit, "save", side_effect=django.db.IntegrityError):
            client.get("/")
            assert client.session[SESSION_KEY]

    @mock.patch("user_visit.middleware.RECORDING_DISABLED", True)
    def test_middleware__disabled(self):
        """Test update_cache and check_cache functions."""
        with pytest.raises(MiddlewareNotUsed):
            UserVisitMiddleware(get_response=lambda r: HttpResponse())
