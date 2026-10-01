# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""What a Mail Queue row records when the server refuses to draft or submit it.

The pending-mail worker retries only rows marked failed with a retry time, so a refusal the row
does not record that way is a mail that is never sent.
"""

import json
import unittest
from unittest import mock

import frappe
import httpx
from jmap.auth import BasicAuth
from jmap.core.retry import RetryPolicy
from jmap.testing.fake import FakeJMAPServer

from suite.mail.doctype.mail_queue import mail_queue
from suite.mail.jmap import SuiteJMAPClient

CORE = "urn:ietf:params:jmap:core"
MAIL = "urn:ietf:params:jmap:mail"
SUBMISSION = "urn:ietf:params:jmap:submission"
URNS = (CORE, MAIL, SUBMISSION)
ACCOUNT = "f7"
USER = "user@example.test"
QUEUE = "q1"
DRAFTED = {"created": {f"draft-{QUEUE}": {"id": "e1", "blobId": "B1", "threadId": "t1", "size": 42}}}


def _server() -> FakeJMAPServer:
    return FakeJMAPServer(
        capabilities={urn: {} for urn in URNS},
        accounts={
            ACCOUNT: {"name": USER, "isPersonal": True, "accountCapabilities": {urn: {} for urn in URNS}}
        },
        primary_accounts=dict.fromkeys(URNS, ACCOUNT),
    )


def _client(server: FakeJMAPServer) -> SuiteJMAPClient:
    http = httpx.Client(auth=BasicAuth(USER, "pw"), **server.client_kwargs())
    return SuiteJMAPClient.connect(
        "https://jmap.example.com/.well-known/jmap",
        auth=BasicAuth(USER, "pw"),
        http=http,
        experimental=True,
        retry_policy=RetryPolicy(max_attempts=1),
    )


class RefusedMail(unittest.TestCase):
    def setUp(self) -> None:
        self.server = _server()
        mailboxes = {"drafts": "mb-drafts", "sent": "mb-sent"}
        for patcher in (
            mock.patch.object(mail_queue, "get_account_client", return_value=_client(self.server)),
            mock.patch.object(
                mail_queue, "get_mailbox_id_by_role", side_effect=lambda a, role, **kw: mailboxes[role]
            ),
            mock.patch.object(mail_queue, "get_identity_id_by_email", return_value="i1"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

        # The outcome lands on the document instead of the database.
        self.addCleanup(frappe.flags.update, {"read_only": frappe.flags.read_only})
        frappe.flags.read_only = True

    def process(self, **fields) -> mail_queue.MailQueue:
        doc = frappe.new_doc("Mail Queue")
        doc.update(
            {
                "name": QUEUE,
                "account": ACCOUNT,
                "user": USER,
                "from_email": USER,
                "subject": "Hello",
                "text_body": "Hello there",
                "recipients": json.dumps([{"type": "To", "email": "rcpt@example.test"}]),
                **fields,
            }
        )
        doc._process()
        return doc

    def assert_retried(self, doc: mail_queue.MailQueue, status: str) -> None:
        self.assertEqual(doc.status, status)
        self.assertEqual(doc.retries, 1)
        self.assertTrue(doc.next_retry_after)

    def test_a_submission_the_server_refuses_outright_is_retried(self):
        self.server.respond("Email/set", DRAFTED)
        self.server.fail("EmailSubmission/set", "serverFail", description="try again later")

        doc = self.process()

        self.assert_retried(doc, "Failed to Submit")
        # The draft exists, and the retry replaces it rather than leaving a second copy.
        self.assertEqual(doc.id, "e1")
        self.assertEqual(doc.error_message, "serverFail: try again later")

    def test_a_draft_the_server_refuses_outright_is_retried(self):
        self.server.fail("Email/set", "accountReadOnly")

        doc = self.process(save_as_draft=1)

        self.assert_retried(doc, "Failed to Draft")
        self.assertEqual(doc.error_message, "accountReadOnly")

    def test_a_refused_object_says_why_even_without_a_description(self):
        refusal = {"type": "invalidProperties", "properties": ["to"]}
        self.server.respond("Email/set", {"notCreated": {f"draft-{QUEUE}": refusal}})

        doc = self.process(save_as_draft=1)

        self.assert_retried(doc, "Failed to Draft")
        self.assertEqual(doc.error_message, "invalidProperties (to)")

    def test_a_refused_draft_stays_the_cause_when_its_submission_fails_with_it(self):
        refusal = {"type": "tooLarge", "description": "The message is too large."}
        self.server.respond("Email/set", {"notCreated": {f"draft-{QUEUE}": refusal}})
        # The submission names a draft that was never created, so the server refuses it too.
        self.server.respond(
            "EmailSubmission/set",
            {"notCreated": {f"submit-{QUEUE}": {"type": "invalidProperties", "properties": ["emailId"]}}},
        )

        doc = self.process()

        self.assert_retried(doc, "Failed to Draft")
        self.assertEqual(doc.error_message, "tooLarge: The message is too large.")

    def test_a_mail_the_server_takes_is_submitted(self):
        self.server.respond("Email/set", DRAFTED)
        self.server.respond("EmailSubmission/set", {"created": {f"submit-{QUEUE}": {"id": "s1"}}})

        doc = self.process()

        self.assertEqual((doc.status, doc.submission_id, doc.id), ("Submitted", "s1", "e1"))
        self.assertFalse(doc.retries)
