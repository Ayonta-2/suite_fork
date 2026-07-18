# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""On-disk event invitation email templates.

The HTML bodies live under `suite/templates/emails/` so they can be edited or replaced on
disk. Each action maps to a fixed template file and a default subject.
"""

TEMPLATE_DIR = "templates/emails"

# action -> template name (file under TEMPLATE_DIR without the .html extension)
DEFAULT_TEMPLATES = {
	"invite": "event_invite",
	"update": "event_update",
	"cancel": "event_cancel",
}

# action -> email subject (Jinja string rendered with the invite context)
DEFAULT_SUBJECTS = {
	"invite": "Invitation: {{ title }}",
	"update": "Updated: {{ title }}",
	"cancel": "Cancelled: {{ title }}",
}


def template_path(name: str) -> str:
	"""Returns the app-relative Jinja path for an event email template name."""

	return f"{TEMPLATE_DIR}/{name}.html"
