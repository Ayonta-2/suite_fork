import frappe

from suite.suite_core.outgoing_email import EMAIL_ACCOUNT, ensure_email_account
from suite.suite_core.utils import is_suite_cloud_configured

# A hosted site sent through its own notification@ mailbox, which Suite Cloud drops. Suite Cloud
# sends the site's mail now: the Suite Cloud account takes over, queued mail included. A default
# account of the site's own stays the default.
OLD_ACCOUNT = "Notifications"


def execute() -> None:
    if not is_suite_cloud_configured():
        return
    # A Notifications account of the site's own, at another address, keeps its mail.
    dropped = (frappe.db.get_value("Email Account", OLD_ACCOUNT, "email_id") or "").startswith(
        "notification@"
    )
    if dropped:
        # First: while it is the default, the Suite Cloud account would not become one.
        frappe.delete_doc("Email Account", OLD_ACCOUNT, ignore_permissions=True, force=True)
    ensure_email_account()
    if dropped:
        frappe.db.set_value(
            "Email Queue",
            {"email_account": OLD_ACCOUNT, "status": ["in", ["Not Sent", "Partially Sent"]]},
            "email_account",
            EMAIL_ACCOUNT,
        )
