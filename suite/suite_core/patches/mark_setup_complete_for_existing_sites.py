import frappe


def execute() -> None:
	"""Sites that predate Suite's onboarding must not be sent through it.

	Fresh installs never run this patch, so they still get the wizard.
	"""
	frappe.db.set_single_value("Suite Settings", "setup_complete", 1)
