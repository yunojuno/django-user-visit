# django-user-visit

Django app for recording daily user visits

#### Compatibility

This package supports Python 3.8 and above and Django 3.2 and above.

## Upgrading from v1 to v2

v2 added three new denormalised fields extracted from the User Agent
string - device, os, browser - to make it easier to analyse directly
in the database.

If you want to backfill historical data you will need to run the
management command `update_user_visit_user_agent_data` after the
upgrade.

---

This app consists of middleware to record user visits, and a single
`UserVisit` model to capture that data.

The principal behind this is _not_ to record every single request made
by a user. It is to record each daily visit to a site.

The one additional factor is that it will record a single daily visit
per session / device / ip combination. This means that if a user visits
a site multiple times from the same location / same device, without
logging out, then they will be recorded once. If the same user logs in
from a different device, IP address, then they will be recorded again.

The goal is to record unique daily visits per user 'context' ( where
context is the location / device combo).

Admin list view:

![UserVisit list view](assets/screenshot-admin-list-view.png)

Admin edit view:

![UserVisit edit view](assets/screenshot-admin-edit-view.png)
