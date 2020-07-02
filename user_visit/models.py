from __future__ import annotations

import user_agents
from django.conf import settings
from django.db import models
from django.utils import timezone


class UserVisit(models.Model):
    """
    Record of a user visiting the site on a given day.

    This is used for tracking and reporting - knowing the volume of visitors
    to the site, and being able to report, Github heatmap-style on someone's
    interaction with the site.

    The goal is very simple - a single record of each day that someone visits
    the site - irrespective of session mechanics (so **not** a record of last
    logged in).

    Workflow as follows:

    On each request, check for a cached visit; if one exists, and it's for today,
    then carry on. If it is not for today, or does not exist, save a new visit
    for today, and cache the new value.

    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="user_visits", on_delete=models.CASCADE
    )
    timestamp = models.DateTimeField(
        help_text="When the user visit was recorded", default=timezone.now
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
        "User Agent", help_text="Client User-Agent HTTP header", blank=True,
    )

    def __str__(self) -> str:
        return f"{self.user} visited the site on {self.timestamp}"

    def __repr__(self) -> str:
        return f"<UserVisit user_id={self.user_id} timestamp='{self.timestamp}'>"

    @property
    def user_agent(self) -> user_agents.parsers.UserAgent:
        """Return UserAgent object from the raw user_agent string."""
        return user_agents.parsers.parse(self.ua_string)
