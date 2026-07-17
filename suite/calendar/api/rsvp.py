# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Signed RSVP links for custom event invitations.

An invitation email carries three signed links (Yes / Maybe / No) that point at the
`event_rsvp` web page. `resolve_rsvp` verifies the token and writes the participant's
response to the organizer's copy of the event via JMAP. Recipients may be on any mail
server, so we never require a login — the signed token is the only authorization.
"""

import base64
import hashlib
import hmac
import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from suite.mail.jmap import get_jmap_connection
from suite.mail.jmap.services.calendars.calendar_event import CalendarEventService
from suite.utils import log_error

# response key -> (JSCalendar participationStatus, human label)
RESPONSES: dict[str, tuple[str, str]] = {
	"accept": ("accepted", "Yes"),
	"tentative": ("tentative", "Maybe"),
	"decline": ("declined", "No"),
}


def build_rsvp_links(
	account: str,
	event_id: str,
	participant_uid: str,
	participant_email: str,
	expires_at: int | None = None,
) -> dict[str, str]:
	"""Returns {accept|tentative|decline: url} signed links for one participant."""

	return {
		response: _rsvp_url(account, event_id, participant_uid, participant_email, response, expires_at)
		for response in RESPONSES
	}


def resolve_rsvp(token: str) -> dict:
	"""Verifies a token, records the response via JMAP, and returns the page result.

	Returns {success: bool, title: str, message: str} for the confirmation page.
	"""

	payload = _verify(token)
	if not payload:
		return _result(False, _("Invalid Link"), _("This response link is invalid or has expired."))

	response = RESPONSES.get(payload.get("r"))
	if not response:
		return _result(False, _("Invalid Response"), _("This response link is not valid."))

	status, label = response

	try:
		service = _guest_calendar_service(payload["a"])
		result = service.set_participation_status(payload["e"], payload["u"], status)
		frappe.db.commit()
	except Exception:
		log_error("Calendar", title=_("Calendar RSVP failed"))
		return _result(
			False,
			_("Something Went Wrong"),
			_("We couldn't record your response. The event may no longer exist."),
		)

	if result.get("notUpdated"):
		return _result(
			False,
			_("Something Went Wrong"),
			_("We couldn't record your response. The event may no longer exist."),
		)

	return _result(
		True,
		_("Response Recorded"),
		_("Your response ({0}) has been sent to the organizer.").format(label),
	)


def _guest_calendar_service(account: str) -> CalendarEventService:
	"""Builds a CalendarEventService for the organizer's account without a logged-in user."""

	users = frappe.db.get_all("User Account", {"account": account}, pluck="user")
	if not users:
		frappe.throw(_("Calendar account not found."))

	connection = get_jmap_connection(users[0], ignore_permissions=True)
	return CalendarEventService(account, connection)


def _rsvp_url(
	account: str,
	event_id: str,
	participant_uid: str,
	participant_email: str,
	response: str,
	expires_at: int | None,
) -> str:
	payload = {"a": account, "e": event_id, "u": participant_uid, "m": participant_email, "r": response}
	if expires_at:
		payload["x"] = int(expires_at)

	token = _sign(payload)
	return frappe.utils.get_url(f"/event_rsvp?token={token}")


def _result(success: bool, title: str, message: str) -> dict:
	return {"success": success, "title": title, "message": message}


def _sign(payload: dict) -> str:
	"""Returns a `<body>.<signature>` token, both URL-safe base64 (unpadded)."""

	body = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
	signature = _b64encode(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
	return f"{body}.{signature}"


def _verify(token: str) -> dict | None:
	"""Validates the signature and expiry. Returns the payload, or None on any failure."""

	try:
		body, signature = token.split(".", 1)
		expected = _b64encode(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
		if not hmac.compare_digest(signature, expected):
			raise ValueError("signature mismatch")
		payload = json.loads(_b64decode(body))
	except Exception:
		return None

	if (expires_at := payload.get("x")) and now_datetime().timestamp() > expires_at:
		return None

	return payload


def _secret() -> bytes:
	return (frappe.local.conf.get("encryption_key") or frappe.local.site or "").encode()


def _b64encode(data: bytes) -> str:
	return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64decode(data: str) -> bytes:
	return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
