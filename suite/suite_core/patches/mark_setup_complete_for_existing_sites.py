import frappe


def execute() -> None:
	"""Sites that predate Suite's onboarding must not be sent through it (fresh
	installs never run patches, so they still get onboarding). Also sets Frappe's
	setup flags, which keep Frappe's role-check-free setup endpoints closed."""
	from frappe.desk.page.setup_wizard.setup_wizard import enable_setup_wizard_complete

	frappe.db.set_single_value("Suite Settings", "setup_complete", 1)
	enable_setup_wizard_complete("frappe")
	frappe.db.set_single_value("System Settings", "setup_complete", 1)
