from __future__ import annotations

import datetime
import uuid
from typing import Optional

import user_agents
from django.conf import settings
from django.db import models
from django.http import HttpRequest
from django.utils import timezone


class RequestParser:
    """Parse HttpRequest object."""

    def __init__(self, request: HttpRequest) -> None:
        """
        Initialise parser from HttpRequest object.

        Raises ValueError if the request.user is not authenticated.

        """
        if not request.user:
            raise ValueError("Request object has no user.")
        if request.user.is_anonymous:
            raise ValueError("Request user is anonymous.")
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


class UserVisitManager(models.Manager):
    """Custom model manager for UserVisit objects."""

    def record(
        self, request: HttpRequest, timestamp: datetime.datetime = timezone.now()
    ) -> Optional[UserVisit]:
        """
        Record a new user visit.

        This method will look for an existing UserVisit for the date (extracted
        from the timestamp), matching the session, user-agent and remote_addr
        properties. If any of these have changed, we create a new object. This
        ensures that we get one record per day, per user, per session, device
        and IP address. If any of these change, we get a new record.

        Returns the UserVisit object that is found or created.

        """
        parser = RequestParser(request)
        try:
            uv = UserVisit.objects.get(
                user=request.user,
                timestamp__date=timestamp.date(),
                session_key=parser.session_key,
                ua_string=parser.ua_string,
                remote_addr=parser.remote_addr,
            )
        except UserVisit.DoesNotExist:
            uv = UserVisit.objects.create(
                user=request.user,
                timestamp=timestamp,
                session_key=parser.session_key,
                ua_string=parser.ua_string,
                remote_addr=parser.remote_addr,
            )
        # this should never happen, but race condition.
        except UserVisit.MultipleObjectsReturned:
            uv = UserVisit.objects.filter(
                user=request.user,
                timestamp__date=timestamp.date(),
                session_key=parser.session_key,
                ua_string=parser.ua_string,
                remote_addr=parser.remote_addr,
            ).last()
        return uv


class UserVisit(models.Model):
    """
    Record of a user visiting the site on a given day.

    This is used for tracking and reporting - knowing the volume of visitors
    to the site, and being able to report on someone's interaction with the site.

    We record minimal info required to identify user sessions, plus changes in
    IP and device. This is useful in identifying suspicious activity (multiple
    logins from different locations).

    Also helpful in identifying support issues (as getting useful browser data
    out of users can be very difficult over live chat).

    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="user_visits", on_delete=models.CASCADE
    )
    timestamp = models.DateTimeField(
        help_text="The time at which the first visit of the day was recorded",
        default=timezone.now,
    )
    session_key = models.CharField(help_text="Django session identifier", max_length=40)
    remote_addr = models.CharField(
        help_text=(
            "Client IP address (from X-Forwarded-For HTTP header, "
            "or REMOTE_ADDR request property)"
        ),
        max_length=100,
        blank=True,
    )
    ua_string = models.TextField(
        "User agent (raw)", help_text="Client User-Agent HTTP header", blank=True,
    )
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    objects = UserVisitManager()

    def __str__(self) -> str:
        return f"{self.user} visited the site on {self.timestamp}"

    def __repr__(self) -> str:
        return f"<UserVisit user_id={self.user_id} timestamp='{self.timestamp}'>"

    @property
    def user_agent(self) -> user_agents.parsers.UserAgent:
        """Return UserAgent object from the raw user_agent string."""
        return user_agents.parsers.parse(self.ua_string)

    @property
    def date(self) -> datetime.date:
        """Extract the date of the visit from the timestamp."""
        return self.timestamp.date()
