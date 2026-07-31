import frappe


def execute() -> None:
    """Sites that predate Suite's onboarding should not be sent through it."""
    frappe.db.set_single_value("Suite Settings", "setup_complete", 1)
