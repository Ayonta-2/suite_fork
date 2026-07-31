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
from frappe.utils import escape_html

from suite.mail.jmap import get_jmap_connection
from suite.mail.jmap.services.calendars.calendar_event import CalendarEventService
from suite.utils import log_error
from suite.utils.dt import get_utc_now

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

    status = response[0]

    try:
        service = _guest_calendar_service(payload["a"])
        result = service.set_participation_status(payload["e"], payload["u"], status)
        if not result.get("notUpdated"):
            _notify_organizer(payload, status)
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

    state, heading, sub = _confirmation_copy(payload["r"])
    event = _fetch_event(service, payload["e"])
    return {
        "success": True,
        "state": state,
        "title": heading,
        "message": sub,
        # The title is organizer-supplied and lands in the guest RSVP page, which frappe renders
        # through a Jinja environment built without autoescaping - so escape it here rather than
        # relying on the template.
        "event_title": escape_html((event or {}).get("title") or ""),
        "event_when": _format_event_when(event) if event else "",
    }


def _notify_organizer(payload: dict, status: str) -> None:
    """Enqueues the organizer heads-up email for a just-recorded RSVP (best-effort).

    Runs after the response commits so the email reflects the stored state, and off the request
    so a mail hiccup never breaks the guest's confirmation page.
    """

    frappe.enqueue(
        "suite.calendar.doctype.calendar_event.invitations.notify_organizer_of_response",
        queue="short",
        enqueue_after_commit=True,
        account=payload["a"],
        event_id=payload["e"],
        participant_email=payload["m"],
        status=status,
    )


def _confirmation_copy(response_key: str) -> tuple[str, str, str]:
    """Returns (state, heading, sub) for a confirmed response, keyed by the RSVP response."""

    return {
        "accept": (
            "yes",
            _("You're going"),
            _("Your response has been sent to the organizer. This event is now on your calendar."),
        ),
        "tentative": (
            "maybe",
            _("Marked as maybe"),
            _("Your response has been sent to the organizer. We'll hold a tentative spot on your calendar."),
        ),
        "decline": (
            "no",
            _("You declined"),
            _("Your response has been sent to the organizer. This event won't be added to your calendar."),
        ),
    }[response_key]


def _fetch_event(service: CalendarEventService, event_id: str) -> dict | None:
    """Best-effort fetch of the event for the confirmation card; None if unavailable."""

    try:
        events = service.get([event_id])
        return events[0] if events else None
    except Exception:
        return None


def _format_event_when(event: dict) -> str:
    """Compact event start for the confirmation card, e.g. 'Tue, 14 Jul · 10:00 AM'."""

    from suite.calendar.doctype.calendar_exchange.calendar_exchange import _parse_local_datetime

    start = _parse_local_datetime(event.get("start"), event.get("timeZone"))
    if not start:
        return ""

    day = f"{start.strftime('%a')}, {start.day} {start.strftime('%b')}"
    if event.get("showWithoutTime"):
        return day

    hour = start.hour % 12 or 12
    meridiem = "AM" if start.hour < 12 else "PM"
    return f"{day} · {hour}:{start.minute:02d} {meridiem}"


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

    # Every token must carry an expiry. Reject a missing one outright so a link can never replay
    # indefinitely (older links minted without an expiry are invalidated by this too).
    # Compare in real UTC. now_datetime() is naive in the *site* timezone, and .timestamp() on a
    # naive value resolves it against the *OS* timezone - so when the two differ the expiry was off
    # by their offset, cutting links short or leaving them valid past the intended window.
    expires_at = payload.get("x")
    if not expires_at or get_utc_now().timestamp() > expires_at:
        return None

    return payload


def _secret() -> bytes:
    # The site's encryption key is the only acceptable signing secret. Never fall back to a
    # predictable value (site name) or an empty string — that would let anyone forge RSVP tokens.
    key = frappe.local.conf.get("encryption_key")
    if not key:
        frappe.throw(_("Site encryption key is not configured; cannot sign RSVP links."))
    return key.encode()


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
