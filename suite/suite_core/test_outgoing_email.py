from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from suite.suite_core import outgoing_email
from suite.suite_core.outgoing_email import EMAIL_ACCOUNT, EmailNotSentError, email_type, sendmail_now
from suite.suite_core.patches import send_mail_through_suite_cloud

RECIPIENT = "someone@example.test"


class TestOutgoingEmail(IntegrationTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.enterContext(patch.object(frappe.db, "commit"))  # Email Queue commits as it sends
        for name in (EMAIL_ACCOUNT, "Notifications"):
            if frappe.db.exists("Email Account", name):
                frappe.delete_doc("Email Account", name, force=True)
        self.connect()
        outgoing_email.ensure_email_account()
        self.client = MagicMock()
        self.client.call.return_value = {"status": "Sent", "error": None}
        self.enterContext(patch("suite.mail.suite_cloud.get_client", return_value=self.client))
        frappe.flags.testing_email = True
        self.addCleanup(setattr, frappe.flags, "testing_email", False)

    def connect(self, url: str = "https://cloud.example.test") -> None:
        values = {"suite_cloud_url": url, "suite_cloud_tenant": "tenant", "suite_cloud_secret": "secret"}
        self.enterContext(
            self.change_settings("Suite Settings", **(values if url else dict.fromkeys(values, "")))
        )
        frappe.local.request_cache.clear()

    def sendmail(self, **kwargs) -> dict:
        return {
            "recipients": [RECIPIENT],
            "subject": "Reset your password",
            "message": "Follow the link.",
            "email_headers": email_type("password-reset"),
            **kwargs,
        }

    def test_connecting_in_suite_settings_sets_up_the_account(self) -> None:
        with patch("frappe.enqueue") as enqueue:
            frappe.get_single("Suite Settings").save()  # no change: nothing to set up
            enqueue.assert_not_called()
            self.connect(url="https://other-cloud.example.test")

        self.assertEqual(enqueue.call_args.args[0], "suite.suite_core.outgoing_email.ensure_email_account")

    def test_connecting_to_suite_cloud_makes_its_account_the_default(self) -> None:
        account = frappe.get_doc("Email Account", EMAIL_ACCOUNT)

        self.assertEqual((account.email_id, account.default_outgoing), ("noreply@cloud.example.test", 1))
        outgoing_email.ensure_email_account()
        self.assertEqual(frappe.db.count("Email Account", {"name": EMAIL_ACCOUNT}), 1)

    def test_a_site_without_suite_cloud_keeps_its_own_mail(self) -> None:
        frappe.delete_doc("Email Account", EMAIL_ACCOUNT, force=True)
        self.connect(url="")

        outgoing_email.ensure_email_account()

        self.assertFalse(frappe.db.exists("Email Account", EMAIL_ACCOUNT))

    def test_an_email_sent_now_goes_through_suite_cloud_with_its_type(self) -> None:
        sendmail_now(**self.sendmail())

        queue = frappe.get_last_doc("Email Queue")
        method, kwargs = self.client.call.call_args.args[0], self.client.call.call_args.kwargs
        self.assertEqual(method, "email.send_email")
        self.assertEqual(
            (kwargs["recipient"], kwargs["request_key"]), (RECIPIENT, f"{queue.name}:{RECIPIENT}")
        )
        self.assertIsInstance(kwargs["message"], str)
        self.assertIn("X-Suite-Email-Type: password-reset", kwargs["message"])
        self.assertEqual(queue.status, "Sent")  # Email Queue does not send it again

    def test_an_email_suite_cloud_did_not_send_now_raises_to_the_caller(self) -> None:
        self.client.call.return_value = {"status": "Failed", "error": "550 No such user"}

        self.assertRaisesRegex(EmailNotSentError, "550 No such user", sendmail_now, **self.sendmail())

    def test_a_queued_email_goes_through_suite_cloud_and_is_tried_again_on_failure(self) -> None:
        self.client.call.return_value = {"status": "Failed", "error": "421 Try later"}
        queue = frappe.sendmail(**self.sendmail(now=False))

        self.assertRaises(EmailNotSentError, queue.send)
        self.assertEqual(frappe.db.get_value("Email Queue", queue.name, "status"), "Not Sent")

        self.client.call.return_value = {"status": "Sent", "error": None}
        frappe.get_doc("Email Queue", queue.name).send()
        self.assertEqual(frappe.db.get_value("Email Queue", queue.name, "status"), "Sent")
        keys = {call.kwargs["request_key"] for call in self.client.call.call_args_list}
        self.assertEqual(keys, {f"{queue.name}:{RECIPIENT}"})  # Suite Cloud sends a key only once

    def test_another_accounts_mail_is_sent_as_frappe_sends_it(self) -> None:
        account = MagicMock(service="")
        account.name = "Support"
        queue = MagicMock(reference_doctype=None)
        queue.get_email_account.return_value = account

        outgoing_email.send(queue, "support@acme.test", RECIPIENT, "Subject: hi\r\n\r\nhi")

        account.get_smtp_server().session.sendmail.assert_called_once_with(
            from_addr="support@acme.test", to_addrs=RECIPIENT, msg=b"Subject: hi\r\n\r\nhi"
        )
        self.client.call.assert_not_called()

    def test_the_patch_moves_the_notification_accounts_queue_to_suite_cloud(self) -> None:
        frappe.delete_doc("Email Account", EMAIL_ACCOUNT, force=True)
        frappe.get_doc(
            {
                "doctype": "Email Account",
                "email_account_name": "Notifications",
                "email_id": "notification@acme.example.test",
                "smtp_server": "mail.example.test",
                "enable_outgoing": 1,
                "default_outgoing": 1,
                "no_smtp_authentication": 1,
            }
        ).insert()
        queued = frappe.get_doc(
            {
                "doctype": "Email Queue",
                "email_account": "Notifications",
                "sender": "notification@acme.example.test",
                "message": "Subject: hi\r\n\r\nhi",
                "status": "Not Sent",
            }
        ).insert(ignore_permissions=True)

        send_mail_through_suite_cloud.execute()

        self.assertFalse(frappe.db.exists("Email Account", "Notifications"))
        self.assertEqual(frappe.db.get_value("Email Account", EMAIL_ACCOUNT, "default_outgoing"), 1)
        self.assertEqual(frappe.db.get_value("Email Queue", queued.name, "email_account"), EMAIL_ACCOUNT)
