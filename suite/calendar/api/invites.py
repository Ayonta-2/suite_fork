from uuid import uuid7

import frappe
from frappe import _

from suite.calendar.doctype.calendar_event.calendar_event import (
    format_calendar_event,
    get_calendar_events,
)
from suite.calendar.doctype.calendar_exchange.calendar_exchange import SERVER_MANAGED_KEYS
from suite.mail.jmap import format_jmap_error, get_calendar_event_service, get_participant_identities
from suite.mail.jmap.services.calendars.calendar import CalendarService
from suite.mail.jmap.services.calendars.calendar_event import CalendarEventService

# JSCalendar participationStatus values a reader can respond with.
RSVP_RESPONSES = ("accepted", "tentative", "declined")


@frappe.whitelist()
def get_invite_details(account: str, blob_id: str) -> dict | None:
    """Parses a text/calendar mail attachment (already a blob in the account's JMAP namespace) and
    reports whether its event is on the calendar yet, so the thread view can offer "Add to Calendar".

    Returns None when the blob has no parsable event or the event carries no UID (nothing to
    deduplicate against). ``event`` is the existing calendar copy when one is found, else a preview
    formatted from the parsed invite (its id is empty — it does not exist on the server yet).
    ``participant`` is the viewer's own entry on that event (None when they aren't invited), so the
    thread view can offer RSVP actions with their current response.

    Caveat: the UID lookup runs on the server's search index, which is updated asynchronously, so
    an event added moments ago may still report ``exists: False``."""

    service = get_calendar_event_service(account)
    events = _parse_events(service, blob_id)
    if not events:
        return None

    invite = events[0]
    uid = invite.get("uid")
    if not uid:
        return None

    # The iTIP METHOD (request/cancel/reply/...) travels through the parse; only a request or
    # publish is something the reader can add.
    method = (invite.get("method") or "").lower()

    exists = False
    event = None
    if master_ids := service.get_master_ids([uid]):
        if existing := get_calendar_events(account, master_ids[:1]):
            exists = True
            event = existing[0]

    if event is None:
        event = _format_preview(account, invite)

    return {
        "uid": uid,
        "method": method,
        "exists": exists,
        "event": event,
        "participant": _viewer_participant(account, event),
    }


@frappe.whitelist()
def add_invite_to_calendar(account: str, blob_id: str) -> dict:
    """Creates the invite's event(s) from a text/calendar mail attachment on the account's default
    calendar and returns the calendar copy. No scheduling messages are sent — adding the invite is
    not an RSVP. Idempotent: an event whose UID is already on the calendar is not recreated."""

    service = get_calendar_event_service(account)
    event_id = _ensure_on_calendar(service, _parse_events(service, blob_id))

    if formatted := get_calendar_events(account, [event_id]):
        return formatted[0]

    frappe.throw(_("Could not add the event to the calendar."))


@frappe.whitelist()
def rsvp_to_invite(account: str, blob_id: str, response: str) -> dict:
    """Records the viewer's RSVP to an invite attachment: puts the event on their calendar first if
    it isn't yet, then patches their own participationStatus with scheduling messages on, so the
    JMAP server sends the iTIP reply to the organizer. Returns the updated calendar copy."""

    response = (response or "").lower()
    if response not in RSVP_RESPONSES:
        frappe.throw(_("Invalid RSVP response."))

    service = get_calendar_event_service(account)
    event_id = _ensure_on_calendar(service, _parse_events(service, blob_id))

    copies = service.get([event_id])
    if not copies:
        frappe.throw(_("Could not record your response. The event may no longer exist."))

    # Participant keys are per-copy (each server generates its own), so locate the viewer in this
    # copy by address — any of the account's participant identities counts as "me".
    emails = {identity["email"] for identity in get_participant_identities(account)}
    participant_uid = _find_participant_uid(copies[0], emails)
    if not participant_uid:
        frappe.throw(_("You are not a participant of this event."))

    result = service.set_participation_status(
        event_id, participant_uid, response, send_scheduling_messages=True
    )
    if result.get("notUpdated"):
        error = next(iter(result["notUpdated"].values()), None)
        frappe.throw(_("Could not record your response: {0}").format(format_jmap_error(error)))

    if formatted := get_calendar_events(account, [event_id]):
        return formatted[0]

    frappe.throw(_("Could not record your response."))


def _ensure_on_calendar(service: CalendarEventService, events: list[dict]) -> str:
    """Creates the parsed events that aren't on the calendar yet (idempotent by UID, on the default
    calendar, no scheduling messages) and returns the master id of the invite's event."""

    uids = [e["uid"] for e in events if e.get("uid")]
    if not uids:
        frappe.throw(_("The attachment does not contain a valid calendar event."))

    existing_ids = service.get_master_ids(uids)
    existing_uids = {e["uid"] for e in service.get(existing_ids) if e.get("uid")} if existing_ids else set()

    default_calendar_id = None

    payload = {}
    for event in events:
        if not event.get("uid") or event["uid"] in existing_uids:
            continue
        if default_calendar_id is None:
            default_calendar_id = CalendarService(service.account, service.connection).get_default(
                raise_exception=True
            )
        event = {k: v for k, v in event.items() if k not in SERVER_MANAGED_KEYS}
        event["@type"] = "Event"
        event["calendarIds"] = {default_calendar_id: True}
        payload[str(uuid7())] = event

    created_ids = []
    if payload:
        response = service._create(payload, sendSchedulingMessages=False)
        method_responses = response.get("methodResponses") or []
        result = method_responses[0][1] if method_responses else {}
        created_ids = [info["id"] for info in (result.get("created") or {}).values()]

        if not_created := result.get("notCreated"):
            error = next(iter(not_created.values()), None)
            frappe.throw(_("Could not add the event to the calendar: {0}").format(format_jmap_error(error)))

    return (created_ids or existing_ids)[0]


def _parse_events(service: CalendarEventService, blob_id: str) -> list[dict]:
    """Parses the blob into JSCalendar events. A mail attachment's blob id lives in the same JMAP
    account namespace as calendar blobs, so it can be parsed directly without re-uploading."""

    if not blob_id:
        frappe.throw(_("Blob ID is required."))

    response = service.parse([blob_id])

    events = []
    for parsed in (response.get("parsed") or {}).values():
        events.extend(parsed or [])

    return events


def _viewer_participant(account: str, event: dict) -> dict | None:
    """Returns the viewer's entry from a *formatted* event's participants, or None if they aren't
    one. Matched by address against the account's participant identities, mirroring how the
    calendar app decides whose RSVP the "Going?" control edits."""

    emails = {identity["email"] for identity in get_participant_identities(account)}

    for participant in event.get("participants") or []:
        if (participant.get("email") or "").lower() in emails:
            return {
                "uid": participant["uid"],
                "email": participant["email"],
                "status": participant.get("participation_status") or "",
            }

    return None


def _find_participant_uid(event: dict, emails: set[str]) -> str | None:
    """Returns the participant key in a *raw* JMAP event copy matching any of the given addresses."""

    for uid, participant in (event.get("participants") or {}).items():
        address = (participant.get("calendarAddress") or participant.get("email") or "").lower()
        if address.replace("mailto:", "") in emails:
            return uid

    return None


def _format_preview(account: str, event: dict) -> dict:
    """Formats a parsed (not yet created) invite through the same formatter served events go
    through, so the frontend renders one shape either way."""

    preview = dict(event)
    # A parsed invite has no server id or calendar membership yet, and the formatter indexes into
    # these (and iterates the sub-object maps) unconditionally.
    preview["id"] = preview.get("id") or ""
    for key in ("calendarIds", "locations", "links", "alerts", "participants"):
        preview[key] = preview.get(key) or {}

    return format_calendar_event(account, {}, preview)
