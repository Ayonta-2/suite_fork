# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Client-side calendar invitation delivery.

When custom event invites are enabled (Mail Settings), the app sends invitation, update,
and cancellation emails itself instead of letting the JMAP server emit iMIP scheduling
mail. Each email carries an .ics (iTIP REQUEST/CANCEL) plus signed HTTP RSVP links.

Entry point: `notify_participants(account, action, ...)`, enqueued from the Calendar Event
API after the event is written to JMAP.
"""

from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, strip_html_tags

from suite.mail.doctype.calendar_event.ics import build_event_ics
from suite.mail.doctype.calendar_event.invite_templates import (
	DEFAULT_SUBJECTS,
	DEFAULT_TEMPLATES,
	template_path,
)
from suite.mail.doctype.calendar_exchange.calendar_exchange import _parse_local_datetime
from suite.mail.doctype.mail_queue.mail_queue import MailQueue
from suite.mail.doctype.user_account.user_account import get_user_for_jmap_account
from suite.mail.jmap import get_calendar_event_service, get_identities
from suite.utils import log_error

# RSVP links stay valid until this long after the event starts.
RSVP_GRACE_DAYS = 1


def custom_event_invites_enabled() -> bool:
	"""Returns True when Mail Settings is configured to send invites from the client."""

	return bool(frappe.get_cached_doc("Mail Settings").get("custom_event_invites"))


def acting_as_organizer(account: str, organizer: str | None) -> bool:
	"""True when the organizer address is one of the acting account's own identities.

	Guards against firing invite blasts when an attendee (not the organizer) edits their
	own response on a shared event — that case should fall back to server scheduling.
	"""

	if not organizer:
		return True

	organizer = organizer.lower().replace("mailto:", "")
	try:
		return organizer in {i["email"] for i in get_identities(account)}
	except Exception:
		return False


def notify_participants(
	account: str,
	action: str,
	event_id: str | None = None,
	event: dict | None = None,
	previous_emails: list[str] | None = None,
) -> None:
	"""Sends invite/update/cancel emails for an event's participants.

	`action` is one of "invite", "update", "cancel". Pass `event_id` to fetch the current
	event, or a pre-fetched `event` snapshot (needed for cancellations after deletion).
	For updates, `previous_emails` enables new -> invite / kept -> update / gone -> cancel;
	omit it to send a plain update to everyone.
	"""

	if event is None:
		events = get_calendar_event_service(account).get([event_id])
		if not events:
			return
		event = events[0]

	organizer = (event.get("organizerCalendarAddress") or "").lower().replace("mailto:", "")
	attendees = _attendees(event, organizer)
	plan = _plan(action, set(attendees), previous_emails)
	if not plan:
		return

	user = get_user_for_jmap_account(account, raise_exception=True)
	expires_at = _rsvp_expiry(event)

	for email, kind in plan.items():
		try:
			_send(account, user, event, organizer, email, attendees.get(email), kind, expires_at)
		except Exception:
			log_error("Calendar", title=_("Failed to send event {0} email to {1}").format(kind, email))


def _plan(action: str, current: set[str], previous_emails: list[str] | None) -> dict[str, str]:
	"""Maps each recipient email to the email kind (invite/update/cancel) to send."""

	if action == "invite":
		return {email: "invite" for email in current}
	if action == "cancel":
		return {email: "cancel" for email in current}

	# action == "update"
	if previous_emails is None:
		return {email: "update" for email in current}

	previous = set(previous_emails)
	plan = {email: ("update" if email in previous else "invite") for email in current}
	for email in previous - current:
		plan[email] = "cancel"
	return plan


def _send(
	account: str,
	user: str,
	event: dict,
	organizer: str,
	email: str,
	participant: dict | None,
	kind: str,
	expires_at: int | None,
) -> None:
	"""Renders and enqueues a single invitation/update/cancellation email."""

	from suite.calendar.api.rsvp import build_rsvp_links

	method = "CANCEL" if kind == "cancel" else "REQUEST"
	ics = build_event_ics(event, method=method)

	links = None
	if kind in ("invite", "update") and participant and participant.get("uid"):
		links = build_rsvp_links(account, event["id"], participant["uid"], email, expires_at)

	subject, html = _render(kind, event, organizer, participant, links)
	message = _build_mime(organizer, email, subject, html, ics, method)

	MailQueue._create(
		user=user,
		account=account,
		from_name=_display_name(event, organizer) or None,
		from_email=organizer,
		recipients=[{"name": (participant or {}).get("name"), "email": email, "type": "To"}],
		raw_message=message,
		via_api=True,
		delivery_mode="Enqueue",
	)


def _render(kind, event, organizer, participant, links) -> tuple[str, str]:
	"""Returns (subject, html) from the on-disk template for the given action."""

	context = _context(event, organizer, participant, links)

	subject = frappe.render_template(DEFAULT_SUBJECTS[kind], context, is_path=False)
	html = frappe.render_template(template_path(DEFAULT_TEMPLATES[kind]), context, is_path=True)
	return subject, html


def _context(event, organizer, participant, links) -> dict:
	"""Builds the Jinja render context shared by subject and body templates."""

	locations = [l.get("name") for l in (event.get("locations") or {}).values() if l.get("name")]

	return {
		"title": event.get("title") or "(No title)",
		"when": _format_when(event),
		"location": "; ".join(locations),
		"description": event.get("description") or "",
		"organizer_name": _display_name(event, organizer) or organizer,
		"organizer_email": organizer,
		"attendee_name": (participant or {}).get("name") or "",
		"rsvp": links,
	}


def _build_mime(organizer, to_email, subject, html, ics, method) -> str:
	"""Builds a multipart/mixed iMIP message: HTML body (with inline logo), text/calendar, .ics.

	The logo is embedded as an inline CID image rather than a remote URL, so it renders in
	email clients without the recipient having to load external images (and works even when
	the site isn't publicly reachable).
	"""

	root = MIMEMultipart("mixed")
	root["Subject"] = subject
	root["From"] = organizer
	root["To"] = to_email
	root["Date"] = formatdate(localtime=True)
	root["Message-ID"] = make_msgid()

	alternative = MIMEMultipart("alternative")
	alternative.attach(MIMEText(strip_html_tags(html), "plain", "utf-8"))
	alternative.attach(MIMEText(html, "html", "utf-8"))

	# Inline calendar part carries the iTIP method so clients can offer native controls.
	inline_calendar = MIMEText(ics, "calendar", "utf-8")
	inline_calendar.set_param("method", method)
	inline_calendar.set_param("component", "VEVENT")
	alternative.attach(inline_calendar)

	# Wrap the body with the inline logo (referenced as `cid:eventlogo` in the templates).
	if logo := _logo_bytes():
		related = MIMEMultipart("related")
		related.attach(alternative)
		image = MIMEImage(logo, _subtype="png")
		image.add_header("Content-ID", "<eventlogo>")
		image.add_header("Content-Disposition", "inline", filename="logo.png")
		related.attach(image)
		root.attach(related)
	else:
		root.attach(alternative)

	# A downloadable copy so any calendar app can import the event.
	attachment = MIMEText(ics, "calendar", "utf-8")
	attachment.set_param("method", method)
	attachment.add_header("Content-Disposition", "attachment", filename="invite.ics")
	root.attach(attachment)

	return root.as_string()


_LOGO_CACHE: bytes | None = None


def _logo_bytes() -> bytes | None:
	"""Returns the Calendar logo PNG bytes for inline embedding, cached per process."""

	global _LOGO_CACHE
	if _LOGO_CACHE is None:
		path = frappe.get_app_path("suite", "public", "calendar", "images", "logo.png")
		try:
			with open(path, "rb") as f:
				_LOGO_CACHE = f.read()
		except OSError:
			log_error("Calendar", title=_("Event invite logo not found"))
			_LOGO_CACHE = b""

	return _LOGO_CACHE or None


def _attendees(event: dict, organizer: str) -> dict[str, dict]:
	"""Returns {email: {uid, name}} for every participant except the organizer."""

	attendees = {}
	for uid, participant in (event.get("participants") or {}).items():
		email = (participant.get("calendarAddress") or "").lower().replace("mailto:", "")
		email = email or (participant.get("email") or "").lower()
		if email and email != organizer:
			attendees[email] = {"uid": uid, "name": participant.get("name") or email}

	return attendees


def _format_when(event: dict) -> str:
	"""Formats the event start for display, e.g. 'Monday, 21 Jul 2025, 10:00 AM (UTC)'."""

	start = _parse_local_datetime(event.get("start"), event.get("timeZone"))
	if not start:
		return ""

	if event.get("showWithoutTime"):
		return start.strftime("%A, %d %b %Y")

	formatted = start.strftime("%A, %d %b %Y, %I:%M %p")
	return f"{formatted} ({event['timeZone']})" if event.get("timeZone") else formatted


def _display_name(event: dict, email: str) -> str:
	"""Returns the participant display name for an email, if the event lists one."""

	for participant in (event.get("participants") or {}).values():
		address = (participant.get("calendarAddress") or participant.get("email") or "").lower()
		if address.replace("mailto:", "") == email and participant.get("name"):
			return participant["name"]

	return ""


def _rsvp_expiry(event: dict) -> int | None:
	"""Returns the RSVP link expiry (event start + grace) as a unix timestamp."""

	start = _parse_local_datetime(event.get("start"), event.get("timeZone"))
	if not start:
		return None

	return int(get_datetime(add_to_date(start, days=RSVP_GRACE_DAYS)).timestamp())
