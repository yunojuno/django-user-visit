from django.contrib import admin

from .models import UserVisit


class UserVisitAdmin(admin.ModelAdmin):

    list_display = ("timestamp", "user", "session_key", "remote_addr", "user_agent")
    list_filter = ("timestamp",)
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__username",
        "ua_string",
    )
    raw_id_fields = ("user",)
    readonly_fields = (
        "user",
        "hash",
        "timestamp",
        "session_key",
        "remote_addr",
        "user_agent",
        "ua_string",
        "created_at",
    )
    ordering = ("-timestamp",)


admin.site.register(UserVisit, UserVisitAdmin)
