# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Scheduled send, read and acted on through JMAP EmailSubmission objects.

The server's held (FUTURERELEASE) submissions are the source of truth: listing queries them
directly, so emails scheduled by other clients appear too, and nothing is reconciled into the
Mail Queue — its rows are only a log of what this app submitted. Every action is keyed on the
EmailSubmission id. Since undoStatus is a submission's only mutable property (RFC 8621 §7.5),
reschedule and send-now cancel the held submission and create a replacement.

The referenced Email may have been deleted after scheduling (EmailSubmission/get then returns a
dangling emailId): such a delivery can still be cancelled — there is just no message to move
back to Drafts — but not resubmitted, so reschedule and send-now refuse it.
"""

from uuid import uuid7

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, get_datetime_str, now, now_datetime, time_diff_in_seconds

from suite.mail.jmap import (
    get_email_service,
    get_email_submission_service,
    get_jmap_set_error_message,
    get_mailbox_id_by_role,
)
from suite.mail.jmap.services.mail.submission.email_submission import EmailSubmissionService
from suite.mail.utils import log_mail_error
from suite.mail.utils.dt import from_utc_z, to_utc_z

SUBMISSION_PROPERTIES = ["id", "emailId", "threadId", "undoStatus", "sendAt", "envelope"]
EMAIL_SUMMARY_PROPERTIES = ["id", "threadId", "subject", "from", "to", "cc", "bcc"]


@frappe.whitelist()
def get_scheduled_mails(account: str) -> list[dict]:
    """Returns the account's held (FUTURERELEASE) submissions, soonest first."""

    service = get_email_submission_service(account)

    ids = service.query({"undoStatus": "pending"})
    if not ids:
        return []

    # Re-read undoStatus from the get: a submission can go final between query and get.
    submissions = [
        s for s in service.get(ids, properties=SUBMISSION_PROPERTIES) if s.get("undoStatus") == "pending"
    ]

    email_ids = [s["emailId"] for s in submissions if s.get("emailId")]
    emails = (
        get_email_service(account).get(email_ids, properties=EMAIL_SUMMARY_PROPERTIES) if email_ids else []
    )
    emails_by_id = {e["id"]: e for e in emails}

    rows = [_serialize_submission(s, emails_by_id.get(s.get("emailId"))) for s in submissions]
    rows.sort(key=lambda row: row["send_at"] or "")
    return rows


@frappe.whitelist()
def reschedule_mail(account: str, id: str, send_at: str) -> dict:
    """Moves a held submission's delivery time. `send_at` is UTC `...Z`."""

    service = get_email_submission_service(account)
    submission = _get_pending_submission(service, id)
    send_at = _validate_send_at(service, from_utc_z(send_at))

    created = _replace_submission(account, service, submission, hold_until=_hold_until(send_at))
    _sync_queue_log(id, submission_id=created["id"], send_at=send_at)

    return {"id": created["id"], "send_at": to_utc_z(send_at)}


@frappe.whitelist()
def send_scheduled_mail_now(account: str, id: str) -> dict:
    """Delivers a held submission immediately."""

    service = get_email_submission_service(account)
    submission = _get_pending_submission(service, id)

    created = _replace_submission(account, service, submission, hold_until=None)
    _sync_queue_log(id, submission_id=created["id"], status="Submitted", submitted_at=now(), send_at=None)

    return {"id": created["id"], "thread_id": submission.get("threadId")}


@frappe.whitelist()
def cancel_scheduled_mail(account: str, id: str) -> dict:
    """Cancels a held submission's delivery and moves the message back to Drafts."""

    service = get_email_submission_service(account)
    submission = _get_submission(service, id)

    undo_status = submission.get("undoStatus")
    if undo_status == "pending":
        service.cancel(id)
    elif undo_status != "canceled":
        frappe.throw(_("This email has already been delivered and can no longer be changed."))
    # Already canceled (e.g. a retried undo whose move below failed): skip straight to the move.

    email_id = _move_email_to_drafts(account, submission.get("emailId"))
    # The row stays Submitted — it did get submitted; cancelled_at records the undone hold.
    _sync_queue_log(id, cancelled_at=now())

    return {"id": email_id}


def _serialize_submission(submission: dict, email: dict | None) -> dict:
    """One Scheduled-page row. Display fields come from the referenced Email; when it was deleted
    after scheduling, the envelope's SMTP recipients are all that is left to show."""

    if email:
        recipients = [
            {"type": rcpt_type, "email": a.get("email"), "display_name": a.get("name")}
            for rcpt_type in ("To", "Cc", "Bcc")
            for a in email.get(rcpt_type.lower()) or []
        ]
    else:
        envelope = submission.get("envelope") or {}
        recipients = [
            {"type": "To", "email": r.get("email"), "display_name": None}
            for r in envelope.get("rcptTo") or []
        ]

    sender = (email.get("from") or [{}])[0] if email else {}
    return {
        "id": submission["id"],
        "email_id": submission.get("emailId"),
        "thread_id": (email or {}).get("threadId") or submission.get("threadId"),
        "subject": (email or {}).get("subject"),
        "from_name": sender.get("name"),
        "from_email": sender.get("email"),
        "recipients": recipients,
        "send_at": submission.get("sendAt"),
        "email_deleted": email is None,
    }


def _get_submission(service: EmailSubmissionService, id: str) -> dict:
    submissions = service.get([id], properties=SUBMISSION_PROPERTIES)
    if not submissions:
        frappe.throw(_("This scheduled email no longer exists."))

    return submissions[0]


def _get_pending_submission(service: EmailSubmissionService, id: str) -> dict:
    submission = _get_submission(service, id)

    undo_status = submission.get("undoStatus")
    if undo_status == "canceled":
        frappe.throw(_("This scheduled delivery has been cancelled."))
    if undo_status != "pending":
        frappe.throw(_("This email has already been delivered and can no longer be changed."))

    return submission


def _validate_send_at(service: EmailSubmissionService, send_at: str) -> str:
    """Validates a new delivery time (system-time string) against the FUTURERELEASE window."""

    send_at = get_datetime_str(get_datetime(send_at))
    if get_datetime(send_at) <= now_datetime():
        frappe.throw(_("Send At must be in the future."))

    max_delay = service.max_delayed_send
    if time_diff_in_seconds(send_at, now()) > max_delay:
        frappe.throw(_("Send At cannot be more than {0} days in the future.").format(max_delay // 86400))

    return send_at


def _hold_until(send_at: str) -> int:
    """The RFC 4865 HOLDUNTIL value (epoch seconds) for a system-time `send_at` string."""

    from suite.utils.dt import convert_to_utc

    return int(convert_to_utc(get_datetime(send_at)).timestamp())


def _replace_submission(
    account: str, service: EmailSubmissionService, submission: dict, hold_until: int | None
) -> dict:
    """Cancels the held submission and creates its replacement (reschedule / send-now)."""

    email_id = submission.get("emailId")
    emails = (
        get_email_service(account).get([email_id], properties=["from", "to", "cc", "bcc"])
        if email_id
        else []
    )
    if not emails:
        frappe.throw(_("The scheduled message no longer exists, so its delivery can only be cancelled."))

    from_email, rcpt_emails, priority = _envelope_args(submission, emails[0])

    service.cancel(submission["id"])
    try:
        return service.resubmit(
            email_id=email_id,
            from_email=from_email,
            rcpt_emails=rcpt_emails,
            envelope_id=str(uuid7()),
            priority=priority,
            hold_until=hold_until,
        )
    except Exception:
        # The old submission is already canceled: fail closed as a cancellation, so the
        # message lands back in Drafts instead of sitting in Sent never sending.
        log_mail_error(_("Failed to resubmit scheduled email"), frappe.get_traceback(with_context=True))
        _move_email_to_drafts(account, email_id)
        _sync_queue_log(submission["id"], cancelled_at=now())
        frappe.throw(
            _(
                "The email could not be resubmitted; its delivery was cancelled and the message "
                "moved back to Drafts."
            )
        )


def _envelope_args(submission: dict, email: dict) -> tuple[str, list[str], int]:
    """SMTP sender, recipients, and MT-Priority for a replacement submission.

    The stored envelope is preferred — it repeats exactly what the server accepted before.
    Submissions created without one (the server derived it from the message) fall back to the
    Email's headers.
    """

    if envelope := submission.get("envelope"):
        mail_from = envelope.get("mailFrom") or {}
        parameters = mail_from.get("parameters") or {}
        rcpt_emails = [r["email"] for r in envelope.get("rcptTo") or []]
        return mail_from["email"], rcpt_emails, cint(parameters.get("MT-PRIORITY"))

    rcpt_emails = [a["email"] for key in ("to", "cc", "bcc") for a in email.get(key) or []]
    return email["from"][0]["email"], rcpt_emails, 0


def _move_email_to_drafts(account: str, email_id: str | None) -> str | None:
    """Returns a cancelled delivery's message to Drafts; a message deleted after scheduling
    (or a submission with no emailId) has nothing to move."""

    from suite.mail.doctype.mail_message.mail_message import _remove_cached_messages

    if not email_id:
        return None

    email_service = get_email_service(account)
    emails = email_service.get([email_id], properties=["mailboxIds"])
    if not emails:
        return None

    drafts_mailbox_id = get_mailbox_id_by_role(
        account, "drafts", create_if_not_exists=True, raise_exception=True
    )

    # Replace (not patch) mailboxIds so the message leaves Sent; restore $draft.
    result = email_service.update(
        [{"id": email_id, "mailbox_ids": {drafts_mailbox_id: True}, "keywords": {"$draft": True}}],
        replace_mailboxes=True,
    )
    if email_id not in result["updated"]:
        # The submission is already canceled; retrying this action skips the cancel
        # step (undoStatus is "canceled") and reattempts the move.
        frappe.throw(get_jmap_set_error_message(result, "notUpdated", email_id))

    # Evict the cached copy — it still carries the Sent mailbox and would show a
    # stale folder label in Drafts until the next sync.
    _remove_cached_messages(account, [email_id])

    # Refresh the open mailbox views (both the folder it left and the one it landed in). The
    # composer that raised the undo toast is unmounted by the time Undo runs, so the refresh
    # rides the same realtime event the message actions use.
    previous_mailbox_ids = list(emails[0].get("mailboxIds") or {})
    frappe.publish_realtime(
        "new_mail_created", list({drafts_mailbox_id, *previous_mailbox_ids}), user=frappe.session.user
    )

    return email_id


def _sync_queue_log(current_submission_id: str, **values) -> None:
    """Best-effort mirror into the Mail Queue log for sends that originated here — submissions
    created by other clients have no row. `values` may carry a replacement submission_id."""

    if name := frappe.db.get_value("Mail Queue", {"submission_id": current_submission_id}):
        frappe.db.set_value("Mail Queue", name, values)
