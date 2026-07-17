# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Builds iMIP-ready iCalendar payloads for event invitation emails.

Reuses the JSCalendar -> VEVENT conversion from Calendar Exchange so invites and the
export feature stay in sync. The only extra work here is wrapping the components in a
VCALENDAR with the right iTIP METHOD (REQUEST for invites/updates, CANCEL for removals).
"""

from icalendar import Calendar

from suite.mail.doctype.calendar_exchange.calendar_exchange import _build_components

PRODID = "-//Frappe Mail//Calendar Invite//EN"


def build_event_ics(event: dict, method: str = "REQUEST") -> str:
	"""Returns the iCalendar text for a JSCalendar event using the given iTIP method."""

	cal = Calendar()
	cal.add("prodid", PRODID)
	cal.add("version", "2.0")
	cal.add("method", method)

	for component in _build_components(event):
		if method == "CANCEL":
			_mark_cancelled(component)
		cal.add_component(component)

	return cal.to_ical().decode("utf-8")


def _mark_cancelled(component) -> None:
	"""Forces STATUS:CANCELLED so recipients' clients remove the event on a CANCEL."""

	if "status" in component:
		del component["status"]
	component.add("status", "CANCELLED")
