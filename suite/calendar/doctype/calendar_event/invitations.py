# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Client-side calendar invitation delivery.

When custom event invites are enabled (Mail Settings), the app sends invitation, update,
and cancellation emails itself instead of letting the JMAP server emit iMIP scheduling
mail. Each email carries an .ics (iTIP REQUEST/CANCEL) plus signed HTTP RSVP links.

Entry point: `notify_participants(account, action, ...)`, enqueued from the Calendar Event
API after the event is written to JMAP.
"""

import re
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, strip_html_tags

from suite.calendar.doctype.calendar_event.ics import build_event_ics
from suite.calendar.doctype.calendar_event.invite_templates import (
	DEFAULT_SUBJECTS,
	DEFAULT_TEMPLATES,
	template_path,
)
from suite.calendar.doctype.calendar_exchange.calendar_exchange import _parse_local_datetime
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
	event_snapshot: dict | None = None,
	previous_emails: list[str] | None = None,
	recurrence_id: str | None = None,
) -> None:
	"""Sends invite/update/cancel emails for an event's participants.

	`action` is one of "invite", "update", "cancel". Pass `event_id` to fetch the current
	event, or a pre-fetched `event_snapshot` (needed for cancellations after deletion).
	For updates, `previous_emails` enables new -> invite / kept -> update / gone -> cancel;
	omit it to send a plain update to everyone. `recurrence_id` scopes a cancellation to a
	single occurrence of a recurring event.

	Note: the snapshot arg is named `event_snapshot`, not `event` — `event` is a reserved
	kwarg of `frappe.enqueue` and would be swallowed before reaching this function.
	"""

	event = event_snapshot
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
			_send(
				account, user, event, organizer, email, attendees.get(email), kind, expires_at, recurrence_id
			)
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
	recurrence_id: str | None = None,
) -> None:
	"""Renders and enqueues a single invitation/update/cancellation email."""

	from suite.calendar.api.rsvp import build_rsvp_links

	method = "CANCEL" if kind == "cancel" else "REQUEST"
	ics = build_event_ics(event, method=method, recurrence_id=recurrence_id)

	links = None
	if kind in ("invite", "update") and participant and participant.get("uid"):
		links = build_rsvp_links(account, event["id"], participant["uid"], email, expires_at)

	from_name = _organizer_name(account, event, organizer)
	subject, html = _render(kind, event, organizer, from_name, participant, links)
	message = _build_mime(from_name, organizer, email, subject, html, ics, method)

	MailQueue._create(
		user=user,
		account=account,
		from_name=from_name,
		from_email=organizer,
		recipients=[{"name": (participant or {}).get("name"), "email": email, "type": "To"}],
		raw_message=message,
		via_api=True,
		delivery_mode="Enqueue",
	)


def _render(kind, event, organizer, organizer_name, participant, links) -> tuple[str, str]:
	"""Returns (subject, html) from the on-disk template for the given action."""

	context = _context(event, organizer, organizer_name, participant, links)

	subject = frappe.render_template(DEFAULT_SUBJECTS[kind], context, is_path=False)
	html = frappe.render_template(template_path(DEFAULT_TEMPLATES[kind]), context, is_path=True)
	return subject, html


def _context(event, organizer, organizer_name, participant, links) -> dict:
	"""Builds the Jinja render context shared by subject and body templates."""

	locations = [l.get("name") for l in (event.get("locations") or {}).values() if l.get("name")]

	return {
		"title": event.get("title") or "(No title)",
		"when": _format_when(event),
		# Timezone shown on its own line under the date; omitted for all-day events.
		"timezone": "" if event.get("showWithoutTime") else (event.get("timeZone") or ""),
		"location": "; ".join(locations),
		"description": event.get("description") or "",
		"organizer_name": organizer_name or organizer,
		"organizer_display": f"{organizer_name} ({organizer})" if organizer_name else organizer,
		"organizer_email": organizer,
		"attendee_name": (participant or {}).get("name") or "",
		"meet": _meet_link(event),
		"rsvp": links,
	}


def _meet_link(event: dict) -> dict | None:
	"""Returns {url, label} for the event's first Frappe Meet link, or None.

	Powers the "Frappe Meet video call" card in the invite/update emails. Only links whose
	URL carries a `/meet/` path are treated as a meeting; other links are left out.
	"""

	for link in (event.get("links") or {}).values():
		href = link.get("href") or ""
		if "/meet/" in href:
			return {"url": href, "label": re.sub(r"^https?://", "", href).rstrip("/")}

	return None


def _build_mime(from_name, organizer, to_email, subject, html, ics, method) -> str:
	"""Builds a multipart/mixed iMIP message: HTML body (with inline logo), text/calendar, .ics.

	The logo is embedded as an inline CID image rather than a remote URL, so it renders in
	email clients without the recipient having to load external images (and works even when
	the site isn't publicly reachable).
	"""

	root = MIMEMultipart("mixed")
	root["Subject"] = subject
	root["From"] = formataddr((from_name, organizer)) if from_name else organizer
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

	# Wrap the body with any inline images the templates reference by CID. The Calendar logo
	# (`cid:eventlogo`) leads every email; the Frappe Meet logo (`cid:meetlogo`) is attached only
	# when the body actually shows the Meet card, so no orphan image rides along otherwise.
	inline_images = []
	if logo := _image_bytes("public", "calendar", "images", "logo.png"):
		inline_images.append(("eventlogo", logo))
	if "cid:meetlogo" in html and (meet_logo := _image_bytes("public", "meet", "images", "meet.png")):
		inline_images.append(("meetlogo", meet_logo))

	if inline_images:
		related = MIMEMultipart("related")
		related.attach(alternative)
		for cid, data in inline_images:
			image = MIMEImage(data, _subtype="png")
			image.add_header("Content-ID", f"<{cid}>")
			image.add_header("Content-Disposition", "inline", filename=f"{cid}.png")
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


_IMAGE_CACHE: dict[str, bytes] = {}


def _image_bytes(*path_parts: str) -> bytes | None:
	"""Returns an app public image's bytes for inline embedding, cached per process."""

	key = "/".join(path_parts)
	if key not in _IMAGE_CACHE:
		try:
			with open(frappe.get_app_path("suite", *path_parts), "rb") as f:
				_IMAGE_CACHE[key] = f.read()
		except OSError:
			log_error("Calendar", title=_("Event invite image not found: {0}").format(key))
			_IMAGE_CACHE[key] = b""

	return _IMAGE_CACHE[key] or None


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
	"""Formats the event start for display, e.g. 'Monday, 21 Jul 2025, 10:00 AM'."""

	start = _parse_local_datetime(event.get("start"), event.get("timeZone"))
	if not start:
		return ""

	if event.get("showWithoutTime"):
		return start.strftime("%A, %d %b %Y")

	# The timezone is surfaced separately (context["timezone"]) so the template can put it on
	# its own line under the date, matching the design.
	return start.strftime("%A, %d %b %Y, %I:%M %p")


def _display_name(event: dict, email: str) -> str:
	"""Returns the participant display name for an email, if the event lists one."""

	for participant in (event.get("participants") or {}).values():
		address = (participant.get("calendarAddress") or participant.get("email") or "").lower()
		if address.replace("mailto:", "") == email and participant.get("name"):
			return participant["name"]

	return ""


def _organizer_name(account: str, event: dict, organizer: str) -> str | None:
	"""Returns the organizer's display name, preferring the sending identity's name.

	Falls back to a participant name, then None — never the bare email, so the From header
	doesn't render as "alice@x.com <alice@x.com>".
	"""

	try:
		for identity in get_identities(account):
			if identity["email"] == organizer:
				name = (identity.get("_name") or "").strip()
				return name if name and name.lower() != organizer else None
	except Exception:
		pass

	name = _display_name(event, organizer).strip()
	return name if name and name.lower() != organizer else None


def _rsvp_expiry(event: dict) -> int | None:
	"""Returns the RSVP link expiry (event start + grace) as a unix timestamp."""

	start = _parse_local_datetime(event.get("start"), event.get("timeZone"))
	if not start:
		return None

	return int(get_datetime(add_to_date(start, days=RSVP_GRACE_DAYS)).timestamp())
