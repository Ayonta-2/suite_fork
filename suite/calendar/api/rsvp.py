# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Guest-facing RSVP endpoint for custom event invitations.

An invitation email carries three signed links (Yes / Maybe / No). Clicking one lands
here: the token is verified, and the participant's response is written to the organizer's
copy of the event via JMAP. Recipients may be on any mail server, so we never require a
login — the signed token is the only authorization.
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
from suite.mail.utils.rate_limiter import dynamic_rate_limit
from suite.utils import log_error

# response key -> (JSCalendar participationStatus, human label)
RESPONSES: dict[str, tuple[str, str]] = {
	"accept": ("accepted", "Yes"),
	"tentative": ("tentative", "Maybe"),
	"decline": ("declined", "No"),
}

# Confirmation page: Suite logo + auto-close countdown.
LOGO_URL = "/assets/suite/frontend/logo.svg"
AUTO_CLOSE_SECONDS = 5

_CHECK_SVG = '<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"></polyline></svg>'
_CROSS_SVG = (
	'<svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"></line>'
	'<line x1="6" y1="6" x2="18" y2="18"></line></svg>'
)


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


@frappe.whitelist(allow_guest=True, methods=["GET"])
@dynamic_rate_limit()
def respond(token: str) -> None:
	"""Records a participant's RSVP from a signed link and shows a confirmation page."""

	payload = _verify(token)
	if not payload:
		return

	response = RESPONSES.get(payload.get("r"))
	if not response:
		_render(_("Invalid Response"), _("This response link is not valid."), success=False)
		return

	status, label = response

	try:
		service = _guest_calendar_service(payload["a"])
		result = service.set_participation_status(payload["e"], payload["u"], status)
		frappe.db.commit()
	except Exception:
		log_error("Calendar", title=_("Calendar RSVP failed"))
		_render(
			_("Something Went Wrong"),
			_("We couldn't record your response. The event may no longer exist."),
			success=False,
		)
		return

	if result.get("notUpdated"):
		_render(
			_("Something Went Wrong"),
			_("We couldn't record your response. The event may no longer exist."),
			success=False,
		)
		return

	_render(_("Response Recorded"), _("Your response ({0}) has been sent to the organizer.").format(label))


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
	return frappe.utils.get_url(f"/api/method/suite.calendar.api.rsvp.respond?token={token}")


def _sign(payload: dict) -> str:
	"""Returns a `<body>.<signature>` token, both URL-safe base64 (unpadded)."""

	body = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
	signature = _b64encode(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
	return f"{body}.{signature}"


def _verify(token: str) -> dict | None:
	"""Validates the signature and expiry. Renders the failure page and returns None on error."""

	try:
		body, signature = token.split(".", 1)
		expected = _b64encode(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
		if not hmac.compare_digest(signature, expected):
			raise ValueError("signature mismatch")
		payload = json.loads(_b64decode(body))
	except Exception:
		_render(
			_("Invalid Link"),
			_("This response link is invalid or has been tampered with."),
			success=False,
		)
		return None

	if (expires_at := payload.get("x")) and now_datetime().timestamp() > expires_at:
		_render(_("Link Expired"), _("This response link has expired."), success=False)
		return None

	return payload


def _render(title: str, message: str, success: bool = True) -> None:
	"""Sends a standalone branded confirmation page (no site chrome) as the HTTP response."""

	html = (
		_PAGE.replace("__TITLE__", frappe.utils.escape_html(title))
		.replace("__MESSAGE__", frappe.utils.escape_html(message))
		.replace("__LOGO__", LOGO_URL)
		.replace("__ICON_CLASS__", "success" if success else "error")
		.replace("__ICON_SVG__", _CHECK_SVG if success else _CROSS_SVG)
		.replace("__SECONDS__", str(AUTO_CLOSE_SECONDS))
	)

	frappe.local.response["type"] = "download"
	frappe.local.response["filename"] = "rsvp.html"
	frappe.local.response["filecontent"] = html.encode("utf-8")
	frappe.local.response["content_type"] = "text/html; charset=utf-8"
	frappe.local.response["display_content_as"] = "inline"


def _secret() -> bytes:
	return (frappe.local.conf.get("encryption_key") or frappe.local.site or "").encode()


def _b64encode(data: bytes) -> str:
	return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64decode(data: str) -> bytes:
	return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


_PAGE = """<!doctype html>
<html lang="en">
<head>
	<meta charset="utf-8" />
	<meta name="viewport" content="width=device-width, initial-scale=1" />
	<meta name="robots" content="noindex" />
	<title>__TITLE__</title>
	<style>
		:root { color-scheme: light dark; }
		* { box-sizing: border-box; }
		body {
			margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
			font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
			background: #f4f5f6; color: #1f272e; padding: 20px;
		}
		.card {
			background: #fff; border: 1px solid #e2e6e9; border-radius: 12px;
			box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06); padding: 40px 32px; width: 100%; max-width: 400px;
			text-align: center;
		}
		.logo { height: 28px; margin-bottom: 28px; }
		.icon {
			width: 56px; height: 56px; border-radius: 50%; margin: 0 auto 20px;
			display: flex; align-items: center; justify-content: center;
		}
		.icon svg { width: 28px; height: 28px; stroke: #fff; stroke-width: 3; fill: none;
			stroke-linecap: round; stroke-linejoin: round; }
		.icon.success { background: #16a34a; }
		.icon.error { background: #dc2626; }
		h1 { font-size: 18px; font-weight: 600; margin: 0 0 8px; }
		p { font-size: 14px; line-height: 1.5; color: #5f6b76; margin: 0; }
		.countdown { margin-top: 24px; font-size: 12px; color: #98a2ac; }
		@media (prefers-color-scheme: dark) {
			body { background: #0f1417; color: #e6eaed; }
			.card { background: #1a2024; border-color: #2b3339; box-shadow: none; }
			p, .countdown { color: #98a2ac; }
		}
	</style>
</head>
<body>
	<div class="card">
		<img class="logo" src="__LOGO__" alt="Frappe Suite" />
		<div class="icon __ICON_CLASS__">__ICON_SVG__</div>
		<h1>__TITLE__</h1>
		<p>__MESSAGE__</p>
		<div class="countdown" id="countdown"></div>
	</div>
	<script>
		(function () {
			var s = __SECONDS__;
			var el = document.getElementById("countdown");
			function tick() {
				if (s <= 0) {
					window.close();
					if (el) { el.textContent = "You can close this tab now."; }
					return;
				}
				if (el) { el.textContent = "This tab will close in " + s + " second" + (s === 1 ? "" : "s") + "…"; }
				s -= 1;
				setTimeout(tick, 1000);
			}
			tick();
		})();
	</script>
</body>
</html>
"""
