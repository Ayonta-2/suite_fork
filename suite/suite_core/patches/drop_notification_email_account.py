import frappe

# A hosted site sent through a notification@ mailbox that Suite Cloud set up and now drops, so the
# account can no longer log in. Suite Cloud sends Suite's emails itself; other mail of the site
# goes through an Email Account its owner sets up. A Notifications account of the site's own, at
# another address, stays.
ACCOUNT = "Notifications"


def execute() -> None:
    if (frappe.db.get_value("Email Account", ACCOUNT, "email_id") or "").startswith("notification@"):
        frappe.delete_doc("Email Account", ACCOUNT, ignore_permissions=True, force=True)
