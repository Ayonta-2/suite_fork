from datetime import datetime
from email.utils import parsedate_to_datetime as parsedate

import frappe
from frappe import _
from frappe.utils import convert_utc_to_system_timezone, get_datetime_str

from suite.utils.dt import convert_to_utc, parse_iso_datetime

# The one timestamp shape the mail APIs accept and return, matching what Stalwart speaks.
UTC_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def to_utc_z(value: "datetime | str | None") -> str | None:
	"""Formats a value as the ``2026-07-28T09:02:30Z`` UTC timestamp the mail APIs return.

	Aware values (Stalwart's timestamps, or the ``...Z`` an API was called with) are converted;
	naive ones are read as system time, which is how Frappe stores datetimes in the database.

	Distinct from ``suite.utils.dt.to_iso8601_z``, which reads a naive value as UTC — wrong for a
	value that came out of a Frappe field.
	"""

	if not value:
		return None

	return convert_to_utc(value).strftime(UTC_DATETIME_FORMAT)


def from_utc_z(value: str | None) -> str | None:
	"""Converts a ``...Z`` timestamp an API was called with to the system-time string Frappe stores.

	Only for values written to Frappe datetime fields; Stalwart's own fields stay in UTC.
	"""

	if not value:
		return None

	return get_datetime_str(parse_iso_datetime(value, as_str=False))


def parsedate_to_datetime(date_header: str) -> "datetime":
	"""Returns datetime object from parsed date header."""

	# email.utils.parsedate_to_datetime raises ValueError on an unparsable header rather than
	# returning None, so the guard below only works if we catch it - otherwise a malformed Date
	# on an inbound or imported message escapes as a traceback instead of this validation error.
	try:
		utc_dt = parsedate(date_header)
	except ValueError:
		utc_dt = None

	if not utc_dt:
		frappe.throw(_("Invalid date format: {0}").format(date_header))

	return convert_utc_to_system_timezone(utc_dt)
