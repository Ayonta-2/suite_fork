"""Mail the site sends goes out through Suite Cloud, which picks the account that sends it.

The site's default outgoing Email Account, ``Suite Cloud``, only marks the mail: Frappe's
``override_email_send`` hook hands each built email to Suite Cloud, which sends it there and then
and answers whether it went. A failure raises: Email Queue tries a queued email again, and
``sendmail_now`` tells its caller.
"""

from urllib.parse import urlparse

import frappe
from frappe import _

from suite.suite_core.utils import get_suite_cloud_config, is_suite_cloud_configured

EMAIL_ACCOUNT = "Suite Cloud"
EMAIL_TYPE_HEADER = "X-Suite-Email-Type"


class EmailNotSentError(frappe.ValidationError):
    """Suite Cloud's mail server did not take the email."""


def email_type(name: str) -> dict[str, str]:
    """``email_headers`` for ``frappe.sendmail`` naming what the email is, e.g. password-reset."""

    return {EMAIL_TYPE_HEADER: name}


def sendmail_now(**kwargs) -> None:
    """``frappe.sendmail`` that sends before it returns, so a failure reaches the caller: an admin
    learns that an invite did not go. ``now=True`` sends only after the request commits."""

    from frappe.email.doctype.email_queue.email_queue import SendMailContext

    queue = frappe.sendmail(**kwargs, now=False)
    if not queue:
        return  # every recipient unsubscribed
    context = SendMailContext(queue)
    for row in queue.recipients:
        send(queue, queue.sender, row.recipient, context.build_message(row.recipient))
        row.db_set("status", "Sent")  # in this transaction: Email Queue never sends it again
    queue.db_set("status", "Sent")


def send(queue, sender: str, recipient: str, message: bytes | str) -> None:
    """Frappe's ``override_email_send`` hook: the Suite Cloud account's mail goes through Suite
    Cloud, any other account's as Frappe sends it."""

    if frappe.in_test and not frappe.flags.testing_email:
        return
    account = queue.get_email_account(raise_error=True)
    if account.name != EMAIL_ACCOUNT:
        send_with_email_account(account, queue, sender, recipient, message)
        return

    from suite.mail import suite_cloud

    result = suite_cloud.get_client().call(
        "email.send_email",
        recipient=recipient,
        message=frappe.safe_decode(message),  # Email Queue builds bytes; JSON carries text
        request_key=f"{queue.name}:{recipient}",
    )
    if result["status"] != "Sent":
        frappe.throw(
            _("The email to {0} was not sent: {1}").format(recipient, result.get("error")), EmailNotSentError
        )


def send_with_email_account(account, queue, sender: str, recipient: str, message: bytes | str) -> None:
    """What Frappe does without the hook."""

    if account.service == "Frappe Mail":
        account.get_frappe_mail_client().send_raw(
            sender=sender,
            recipients=recipient,
            message=message,
            is_newsletter=queue.reference_doctype == "Newsletter",
        )
        return
    account.get_smtp_server().session.sendmail(
        from_addr=sender, to_addrs=recipient, msg=frappe.safe_encode(message)
    )


def ensure_email_account() -> None:
    """The ``Suite Cloud`` account, made the default outgoing one, once Suite Cloud is configured.

    It never logs in anywhere: its address only stands in until Suite Cloud sets the sender.
    """

    if not is_suite_cloud_configured() or frappe.db.exists("Email Account", EMAIL_ACCOUNT):
        return
    host = urlparse(get_suite_cloud_config("suite_cloud_url")).hostname
    frappe.get_doc(
        {
            "doctype": "Email Account",
            "email_account_name": EMAIL_ACCOUNT,
            "email_id": f"noreply@{host}",
            "smtp_server": host,
            "no_smtp_authentication": 1,
            "enable_outgoing": 1,
            "default_outgoing": 1,
        }
    ).insert(ignore_permissions=True)
