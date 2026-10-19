import frappe

from suite.suite_core.outgoing_email import EMAIL_ACCOUNT, ensure_email_account

# A hosted site sent through its own notification@ mailbox, which Suite Cloud drops. Suite Cloud
# sends the site's mail now: the Suite Cloud account takes over, queued mail included.
OLD_ACCOUNT = "Notifications"


def execute() -> None:
    ensure_email_account()
    email_id = frappe.db.get_value("Email Account", OLD_ACCOUNT, "email_id")
    if not frappe.db.exists("Email Account", EMAIL_ACCOUNT) or not (email_id or "").startswith(
        "notification@"
    ):
        return
    frappe.db.set_value(
        "Email Queue",
        {"email_account": OLD_ACCOUNT, "status": ["in", ["Not Sent", "Partially Sent"]]},
        "email_account",
        EMAIL_ACCOUNT,
    )
    frappe.delete_doc("Email Account", OLD_ACCOUNT, ignore_permissions=True, force=True)
