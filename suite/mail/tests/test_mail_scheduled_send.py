# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Scheduled send via JMAP FUTURERELEASE (RFC 4865).

Scheduling submits immediately with a HOLDUNTIL envelope parameter, so the server holds
delivery; the Mail Queue row is only a log (status ``Submitted``, ``send_at`` recording the
hold). The server's EmailSubmission objects are the source of truth: the Scheduled page lists
them via ``EmailSubmission/query`` (``undoStatus: "pending"``), so submissions created by
other clients appear too, and every action is keyed on the submission id. Reschedule and
send-now cancel the held submission and create a new one (undoStatus is the only mutable
submission property); cancel reverts the message to Drafts. An Email deleted after scheduling
leaves a dangling emailId — such a delivery can only be cancelled.

Delivery state is computed from the submission's deliveryStatus (delivered, displayed,
smtpReply), refined by the MTA queue (correlated via the envelope's ENVID): the listing and
the details endpoint report a status (scheduled, queued, retrying, failed, delivered,
displayed, sent) plus retry counts. A real delivery failure can't be
provoked reliably against the test server, so the failure sieve is covered at the helper level
and retry/dismiss against delivered (final) submissions.
"""

from datetime import datetime

import frappe
from frappe.utils import add_to_date, get_datetime, get_datetime_str, now, time_diff_in_seconds

from suite.mail.api.scheduled import (
    cancel_scheduled_mail,
    dismiss_failed_mail,
    get_scheduled_mail,
    get_scheduled_mails,
    reschedule_mail,
    retry_delivery_now,
    retry_failed_mail,
    send_scheduled_mail_now,
)
from suite.mail.jmap import get_email_service, get_email_submission_service
from suite.mail.tests.base import StalwartIntegrationTestCase, unique_name
from suite.mail.utils.dt import to_utc_z
from suite.utils.dt import convert_to_utc


def _epoch(value: str) -> int:
    """Epoch seconds of an ISO UTC timestamp (either ``...Z`` or offset form)."""

    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


class TestMailScheduledSend(StalwartIntegrationTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.sender = cls.create_member()
        cls.recipient = cls.create_member()
        cls.disable_screening(cls.recipient)

    # --- helpers ------------------------------------------------------------

    def _schedule(self, minutes: int = 120, subject: str | None = None) -> frappe._dict:
        """Schedules a mail from the class sender and returns the send result's details."""

        subject = subject or f"Scheduled {unique_name('subject')}"
        result = self.send_mail(
            self.sender,
            self.recipient.email,
            subject=subject,
            send_at=to_utc_z(add_to_date(now(), minutes=minutes)),
        )
        self.assertEqual(result["status"], "Submitted", result.get("error"))
        self.assertTrue(result["submission_id"])

        return frappe._dict(
            name=result["name"],
            id=result["id"],
            submission_id=result["submission_id"],
            subject=subject,
            result=result,
        )

    def _get_submission(self, account: str, submission_id: str) -> dict | None:
        with self.set_user(self.sender.email):
            submissions = get_email_submission_service(account).get([submission_id])
        return submissions[0] if submissions else None

    def _scheduled_rows(self, account: str) -> list[dict]:
        with self.set_user(self.sender.email):
            return get_scheduled_mails(account)

    def _get_details(self, account: str, submission_id: str) -> dict:
        with self.set_user(self.sender.email):
            return get_scheduled_mail(account, submission_id)

    # --- tests --------------------------------------------------------------

    def test_schedule_holds_delivery(self):
        scheduled = self._schedule(minutes=120)

        # The queue row is just a log now: submitted, with send_at recording the hold.
        with self.set_user("Administrator"):
            doc = frappe.get_doc("Mail Queue", scheduled.name)
        self.assertEqual(doc.status, "Submitted")
        self.assertTrue(doc.submission_id)
        self.assertTrue(doc.send_at)
        self.assertTrue(doc.submitted_at)

        account = self.personal_account(self.sender)

        # Trust EmailSubmission/get, not the create echo (which reports "final").
        submission = self._get_submission(account, scheduled.submission_id)
        self.assertIsNotNone(submission)
        self.assertEqual(submission["undoStatus"], "pending")

        # The server's sendAt reflects the HOLDUNTIL parameter.
        hold_until = int(convert_to_utc(get_datetime(doc.send_at)).timestamp())
        self.assertLessEqual(abs(_epoch(submission["sendAt"]) - hold_until), 5)

        # The message sits in Sent while held (moved there at submission time).
        with self.set_user(self.sender.email):
            sent_id = frappe.get_doc("Mail Queue", scheduled.name).mailbox_id
            emails = get_email_service(account).get([scheduled.id], properties=["mailboxIds"])
        self.assertTrue(emails and emails[0]["mailboxIds"].get(sent_id))

        # Held, so nothing has reached the recipient.
        threads = self.get_inbox_threads(self.recipient)
        self.assertNotIn(scheduled.subject, [t["subject"] for t in threads])

    def test_listing_reads_submissions(self):
        scheduled = self._schedule(minutes=120)
        account = self.personal_account(self.sender)

        rows = self._scheduled_rows(account)
        row = next((r for r in rows if r["id"] == scheduled.submission_id), None)

        self.assertIsNotNone(row, "The held submission is missing from the Scheduled listing.")
        self.assertEqual(row["email_id"], scheduled.id)
        self.assertEqual(row["subject"], scheduled.subject)
        self.assertFalse(row["email_deleted"])
        self.assertIn(self.recipient.email, [r["email"] for r in row["recipients"]])
        self.assertTrue(row["send_at"])

        # The merged delivery state: a held submission is "scheduled", with no attempts yet
        # (retries comes off the MTA queue message, correlated via ENVID) and no errors.
        self.assertEqual(row["status"], "scheduled")
        self.assertFalse(row["retries"])
        self.assertEqual(row["delivery_errors"], [])
        recipient_states = {r["email"]: r["status"] for r in row["recipients_status"]}
        self.assertEqual(recipient_states.get(self.recipient.email), "scheduled")

        # Soonest first.
        send_ats = [r["send_at"] for r in rows]
        self.assertEqual(send_ats, sorted(send_ats))

    def test_delivered_submission_drops_out_of_listing(self):
        # Held only briefly: once the hold elapses and the delivery concludes, the listing
        # must drop the row. Between release and conclusion the row may legitimately linger
        # as "queued", so the check waits on the listing itself.
        subject = f"Delivered {unique_name('subject')}"
        result = self.send_mail(
            self.sender,
            self.recipient.email,
            subject=subject,
            send_at=to_utc_z(add_to_date(now(), seconds=15)),
        )
        self.assertEqual(result["status"], "Submitted", result.get("error"))

        account = self.personal_account(self.sender)
        self.wait_until(
            lambda: result["submission_id"] not in [row["id"] for row in self._scheduled_rows(account)],
            timeout=90,
            message="The delivered submission never left the Scheduled listing.",
        )

        details = self._get_details(account, result["submission_id"])
        self.assertIn(details["status"], ("delivered", "sent"))
        self.assertEqual(details["undo_status"], "final")

    def test_cancel_reverts_to_draft(self):
        scheduled = self._schedule(minutes=120)
        account = self.personal_account(self.sender)

        from suite.mail.doctype.mail_message.mail_message import _cache_messages, _get_cached_messages

        # Seed the data store with the (soon stale, Sent-labelled) cached copy; cancel
        # must evict it or Drafts keeps showing the old folder label until the next sync.
        _cache_messages(account, {scheduled.id: {"id": scheduled.id}})

        with self.set_user(self.sender.email):
            result = cancel_scheduled_mail(account, scheduled.submission_id)
        self.assertEqual(result["id"], scheduled.id)
        self.assertIsNone(_get_cached_messages(account, [scheduled.id])[scheduled.id])

        submission = self._get_submission(account, scheduled.submission_id)
        self.assertEqual(submission["undoStatus"], "canceled")

        # The queue log mirrors the cancellation via cancelled_at; the row stays Submitted.
        with self.set_user("Administrator"):
            doc = frappe.get_doc("Mail Queue", scheduled.name)
        self.assertEqual(doc.status, "Submitted")
        self.assertTrue(doc.cancelled_at)

        # Back in Drafts only (mailboxIds replaced, not patched) with $draft restored.
        with self.set_user(self.sender.email):
            from suite.mail.jmap import get_mailbox_id_by_role

            drafts_id = get_mailbox_id_by_role(account, "drafts", raise_exception=True)
            emails = get_email_service(account).get([scheduled.id], properties=["mailboxIds", "keywords"])

        self.assertEqual(list(emails[0]["mailboxIds"].keys()), [drafts_id])
        self.assertTrue(emails[0]["keywords"].get("$draft"))

    def test_cancel_refreshes_open_mailbox_views(self):
        # The composer that raises the undo toast is unmounted by the time Undo runs, so
        # the refresh rides the same realtime event the message actions use.
        from unittest.mock import patch

        from suite.mail.jmap import get_mailbox_id_by_role

        scheduled = self._schedule(minutes=120)
        account = self.personal_account(self.sender)

        with self.set_user(self.sender.email):
            drafts_id = get_mailbox_id_by_role(account, "drafts", raise_exception=True)
            sent_id = get_mailbox_id_by_role(account, "sent", raise_exception=True)

            with patch("frappe.publish_realtime") as publish:
                cancel_scheduled_mail(account, scheduled.submission_id)

        events = [c for c in publish.call_args_list if c.args and c.args[0] == "new_mail_created"]
        self.assertTrue(events, "cancel did not publish a mailbox refresh")

        # Both the folder it left and the one it landed in, so either open view updates.
        self.assertEqual(set(events[-1].args[1]), {drafts_id, sent_id})
        self.assertEqual(events[-1].kwargs["user"], self.sender.email)

    def test_reschedule_creates_new_submission(self):
        scheduled = self._schedule(minutes=120)
        account = self.personal_account(self.sender)
        new_send_at = to_utc_z(add_to_date(now(), minutes=240))

        with self.set_user(self.sender.email):
            result = reschedule_mail(account, scheduled.submission_id, new_send_at)
        self.assertTrue(result["id"])
        self.assertNotEqual(result["id"], scheduled.submission_id)

        old_submission = self._get_submission(account, scheduled.submission_id)
        self.assertEqual(old_submission["undoStatus"], "canceled")

        new_submission = self._get_submission(account, result["id"])
        self.assertEqual(new_submission["undoStatus"], "pending")
        self.assertLessEqual(abs(_epoch(new_submission["sendAt"]) - _epoch(new_send_at)), 5)

        # The queue log follows the replacement submission.
        with self.set_user("Administrator"):
            doc = frappe.get_doc("Mail Queue", scheduled.name)
        self.assertEqual(doc.submission_id, result["id"])
        self.assertLessEqual(abs(_epoch(to_utc_z(doc.send_at)) - _epoch(new_send_at)), 5)

    def test_send_now_delivers(self):
        scheduled = self._schedule(minutes=60 * 24)
        account = self.personal_account(self.sender)

        with self.set_user(self.sender.email):
            result = send_scheduled_mail_now(account, scheduled.submission_id)
        self.assertTrue(result["id"])

        with self.set_user("Administrator"):
            doc = frappe.get_doc("Mail Queue", scheduled.name)
        self.assertEqual(doc.submission_id, result["id"])
        self.assertFalse(doc.send_at)

        def find_thread():
            threads = self.get_inbox_threads(self.recipient)
            return next((t for t in threads if t["subject"] == scheduled.subject), None)

        self.wait_until(
            find_thread,
            timeout=60,
            message=f"Send-now mail '{scheduled.subject}' did not reach {self.recipient.email}.",
        )

    def test_dangling_email_is_cancel_only(self):
        # The Email may be deleted after scheduling; the submission then carries a dangling
        # emailId. The listing must still show the row (recipients off the envelope), the
        # resubmitting actions must refuse it, and cancel must work without a move.
        scheduled = self._schedule(minutes=120)
        account = self.personal_account(self.sender)

        with self.set_user(self.sender.email):
            get_email_service(account).delete([scheduled.id])

        rows = self._scheduled_rows(account)
        row = next((r for r in rows if r["id"] == scheduled.submission_id), None)
        self.assertIsNotNone(row, "A dangling submission is missing from the Scheduled listing.")
        self.assertTrue(row["email_deleted"])
        self.assertIn(self.recipient.email, [r["email"] for r in row["recipients"]])

        with self.set_user(self.sender.email):
            for action in (
                lambda: send_scheduled_mail_now(account, scheduled.submission_id),
                lambda: reschedule_mail(
                    account, scheduled.submission_id, to_utc_z(add_to_date(now(), minutes=240))
                ),
            ):
                with self.assertRaises(frappe.ValidationError):
                    action()

            # Refusing to resubmit must leave the hold untouched.
            self.assertEqual(
                self._get_submission(account, scheduled.submission_id)["undoStatus"], "pending"
            )

            result = cancel_scheduled_mail(account, scheduled.submission_id)

        self.assertIsNone(result["id"])  # nothing left to move to Drafts
        submission = self._get_submission(account, scheduled.submission_id)
        self.assertEqual(submission["undoStatus"], "canceled")

    def test_validation_errors(self):
        for kwargs in [
            {"send_at": to_utc_z(add_to_date(now(), minutes=-5))},  # in the past
            {"send_at": to_utc_z(add_to_date(now(), days=31))},  # beyond maxDelayedSend
            {"send_at": to_utc_z(add_to_date(now(), minutes=60)), "save_as_draft": True},
        ]:
            with self.assertRaises(frappe.ValidationError):
                self.send_mail(self.sender, self.recipient.email, **kwargs)

        # The same window applies to a reschedule.
        scheduled = self._schedule(minutes=120)
        account = self.personal_account(self.sender)
        with self.set_user(self.sender.email):
            for send_at in (
                to_utc_z(add_to_date(now(), minutes=-5)),
                to_utc_z(add_to_date(now(), days=31)),
            ):
                with self.assertRaises(frappe.ValidationError):
                    reschedule_mail(account, scheduled.submission_id, send_at)

        # destroy_after_submit is not exposed by create_mail; exercise the queue factory.
        from suite.mail.doctype.mail_queue.mail_queue import MailQueue

        with self.set_user(self.sender.email), self.assertRaises(frappe.ValidationError):
            MailQueue._create(
                user=self.sender.email,
                account=self.personal_account(self.sender),
                from_email=self.sender.email,
                subject="Scheduled destroy",
                html_body="<p>Test</p>",
                recipients=[{"type": "To", "email": self.recipient.email, "display_name": None}],
                destroy_after_submit=True,
                send_at=get_datetime_str(add_to_date(now(), minutes=60)),
            )

    def test_undo_send_holds_and_cancels(self):
        # The composer's default Send: the server computes a short hold so the sender
        # can cancel from the undo toast; Undo is just cancel_scheduled_mail.
        from suite.mail.api.mail import UNDO_SEND_HOLD_SECONDS

        result = self.send_mail(self.sender, self.recipient.email, undo_send=True)
        self.assertEqual(result["status"], "Submitted", result.get("error"))
        self.assertTrue(result["submission_id"])
        self.assertTrue(result["send_at"])

        hold = time_diff_in_seconds(frappe.db.get_value("Mail Queue", result["name"], "send_at"), now())
        self.assertGreater(hold, 0)
        self.assertLessEqual(hold, UNDO_SEND_HOLD_SECONDS + 5)

        account = self.personal_account(self.sender)
        with self.set_user(self.sender.email):
            cancelled = cancel_scheduled_mail(account, result["submission_id"])
        self.assertEqual(cancelled["id"], result["id"])

        submission = self._get_submission(account, result["submission_id"])
        self.assertEqual(submission["undoStatus"], "canceled")

    def test_submission_details(self):
        scheduled = self._schedule(minutes=120)
        account = self.personal_account(self.sender)

        details = self._get_details(account, scheduled.submission_id)

        self.assertEqual(details["id"], scheduled.submission_id)
        self.assertEqual(details["subject"], scheduled.subject)
        self.assertEqual(details["status"], "scheduled")
        self.assertEqual(details["undo_status"], "pending")
        self.assertFalse(details["email_deleted"])

        # The envelope this app submitted with, echoed back by the server.
        self.assertEqual(details["envelope_from"], self.sender.email)
        self.assertIn(self.recipient.email, details["envelope_recipients"])
        self.assertIsInstance(details["priority"], int)
        self.assertEqual(details["identity_email"], self.sender.email)

        recipient_states = {r["email"]: r for r in details["recipients_status"]}
        state = recipient_states[self.recipient.email]
        self.assertEqual(state["status"], "scheduled")
        # The raw DeliveryStatus rides along for the details page.
        for key in ("smtp_reply", "delivered", "displayed"):
            self.assertIn(key, state)

        self.assertEqual(details["dsn_count"], 0)
        self.assertEqual(details["mdn_count"], 0)

    def test_status_sifting_helpers(self):
        # The listing keeps a finalized submission only when it was held and troubled;
        # these helpers are that sieve.
        from suite.mail.api.scheduled import _hold_active, _recipient_status, _was_held

        held = {"envelope": {"mailFrom": {"email": "a@x.test", "parameters": {"HOLDUNTIL": "..."}}}}
        self.assertTrue(_was_held(held))
        self.assertFalse(_was_held({"envelope": None}))
        self.assertFalse(
            _was_held({"envelope": {"mailFrom": {"email": "a@x.test", "parameters": {"ENVID": "e"}}}})
        )

        # A hold is active only while pending AND before sendAt: Stalwart keeps a released
        # message pending for as long as it can still be cancelled from the queue.
        future = to_utc_z(add_to_date(now(), minutes=60))
        past = to_utc_z(add_to_date(now(), minutes=-60))
        self.assertTrue(_hold_active({"undoStatus": "pending", "sendAt": future}))
        self.assertFalse(_hold_active({"undoStatus": "pending", "sendAt": past}))
        self.assertFalse(_hold_active({"undoStatus": "final", "sendAt": future}))
        self.assertFalse(_hold_active({"undoStatus": "pending"}))

        # (hold active, DeliveryStatus, queue status, retries) → status. DeliveryStatus drives
        # the state; the queue tells a first attempt apart from one awaiting a retry.
        for expected, args in [
            ("scheduled", (True, {}, None, 0)),
            ("displayed", (False, {"delivered": "yes", "displayed": "yes"}, None, 0)),
            ("failed", (False, {"delivered": "no", "smtpReply": "550 5.1.1"}, None, 0)),
            ("delivered", (False, {"delivered": "yes", "displayed": "unknown"}, None, 0)),
            ("retrying", (False, {"delivered": "queued"}, "TemporaryFailure", 0)),
            ("retrying", (False, {"delivered": "queued"}, "Scheduled", 1)),
            ("queued", (False, {"delivered": "queued"}, None, 0)),
            ("queued", (False, {"delivered": "queued"}, "Scheduled", 0)),
            ("queued", (False, {}, "Scheduled", 0)),
            ("sent", (False, {"delivered": "unknown"}, None, 0)),
            ("sent", (False, {}, None, 0)),
        ]:
            self.assertEqual(_recipient_status(*args), expected, args)

    def test_retry_and_dismiss_finalized_submissions(self):
        account = self.personal_account(self.sender)

        # All three refuse a submission whose delivery is still pending.
        pending = self._schedule(minutes=120)
        with self.set_user(self.sender.email):
            for action in (retry_failed_mail, retry_delivery_now, dismiss_failed_mail):
                with self.assertRaises(frappe.ValidationError):
                    action(account, pending.submission_id)

        subject = f"Retry {unique_name('subject')}"
        result = self.send_mail(
            self.sender,
            self.recipient.email,
            subject=subject,
            send_at=to_utc_z(add_to_date(now(), seconds=15)),
        )
        self.assertEqual(result["status"], "Submitted", result.get("error"))
        self.wait_until(
            lambda: (self._get_submission(account, result["submission_id"]) or {}).get("undoStatus")
            == "final",
            timeout=90,
            message="The held submission never went final.",
        )

        # A concluded delivery has left the MTA queue — nothing there to poke.
        self.wait_until(
            lambda: self._get_details(account, result["submission_id"])["status"] in ("delivered", "sent"),
            timeout=90,
            message="The released delivery never concluded.",
        )
        with self.set_user(self.sender.email):
            with self.assertRaises(frappe.ValidationError):
                retry_delivery_now(account, result["submission_id"])

        # Retry replaces the finalized record with a fresh immediate submission.
        with self.set_user(self.sender.email):
            retried = retry_failed_mail(account, result["submission_id"])
        self.assertTrue(retried["id"])
        self.assertIsNone(self._get_submission(account, result["submission_id"]))

        # Dismiss destroys the record outright.
        self.wait_until(
            lambda: (self._get_submission(account, retried["id"]) or {}).get("undoStatus") == "final",
            timeout=90,
            message="The retried submission never went final.",
        )
        with self.set_user(self.sender.email):
            dismiss_failed_mail(account, retried["id"])
        self.assertIsNone(self._get_submission(account, retried["id"]))

    def test_stale_action_cannot_resurrect_a_cancelled_schedule(self):
        # Reschedule/send-now on a submission that was cancelled in the meantime must not
        # create a live replacement for a message already moved back to Drafts.
        account = self.personal_account(self.sender)

        for action in (
            lambda submission_id: send_scheduled_mail_now(account, submission_id),
            lambda submission_id: reschedule_mail(
                account, submission_id, to_utc_z(add_to_date(now(), minutes=240))
            ),
        ):
            scheduled = self._schedule(minutes=120)

            with self.set_user(self.sender.email):
                cancel_scheduled_mail(account, scheduled.submission_id)

                with self.assertRaises(frappe.ValidationError):
                    action(scheduled.submission_id)

            self.assertEqual(
                self._get_submission(account, scheduled.submission_id)["undoStatus"], "canceled"
            )
