from __future__ import annotations

import argparse
from typing import Any

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _, gettext_lazy as _lazy

from user_visit.models import UserVisit


class Command(BaseCommand):
    help = _lazy(  # noqa: A003
        "Sync browser, device and OS data missing from UserVisit"
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            default=False,
            help=_(
                "Use the --force option to update all UserVisit "
                "objects (defaults to backfilling empty records only)."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        visits = UserVisit.objects.all()
        if not options["force"]:
            visits = visits.filter(ua_string="")
        updated = 0
        for v in visits.iterator():
            user_agent = v.user_agent
            v.device = user_agent.get_device()
            v.os = user_agent.get_os()
            v.browser = user_agent.get_browser()
            v.save(update_fields=["device", "os", "browser"])
            self.stdout.write(f"Updated UserVisit #{v.pk}")
            updated += 1
        self.stdout.write("---")
        self.stdout.write(f"Updated {updated} UserVisit objects.")
