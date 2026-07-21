import os

import frappe
import requests
from frappe.rate_limiter import rate_limit
from frappe.utils import now


def mark_as_viewed(entity):
	if (
		frappe.session.user == "Guest"
		or not frappe.has_permission(doctype="Drive Entity Log", ptype="create", user=frappe.session.user)
		or entity.is_folder
	):
		return

	entity_log = frappe.db.get_value(
		"Drive Entity Log", {"entity_name": entity.name, "user": frappe.session.user}
	)
	if entity_log:
		frappe.db.set_value(
			"Drive Entity Log",
			entity_log,
			"last_interaction",
			now(),
			update_modified=False,
		)
		return
	doc = frappe.new_doc("Drive Entity Log")
	doc.entity_name = entity.name
	doc.user = frappe.session.user
	doc.last_interaction = now()
	doc.insert()
	return doc


def get_country_info():
	ip = frappe.local.request_ip

	def _get_country_info():
		fields = [
			"status",
			"message",
			"continent",
			"continentCode",
			"country",
			"countryCode",
			"region",
			"regionName",
			"city",
			"district",
			"zip",
			"lat",
			"lon",
			"timezone",
			"offset",
			"currency",
			"isp",
			"org",
			"as",
			"asname",
			"reverse",
			"mobile",
			"proxy",
			"hosting",
			"query",
		]

		try:
			res = requests.get(f"https://pro.ip-api.com/json/{ip}?fields={','.join(fields)}")
			data = res.json()
			if data.get("status") != "fail":
				return data
		except Exception:
			pass

		return {}

	return frappe.cache().hget("ip_country_map", ip, generator=_get_country_info)


def assign_drive_role(user, method: str | None = None) -> None:
	"""Assign the "Drive User" role to a new User.

	Runs on `before_insert` (not `after_insert`) so the role is present by the
	time Frappe's `User.validate` runs: `check_roles_added` would otherwise warn
	"Newly created user X has no roles enabled", and `set_system_user` would
	demote the user to a Website User for having no desk-access role.
	"""
	from suite.suite_core.roles import assign_role

	assign_role(user, "Drive User")


def create_drive_settings_and_team(user, method: str | None = None) -> None:
	"""Create Drive Settings and a personal team for a newly created User."""
	from suite.drive.api.product import create_team

	user_name = user.name

	if not user_name or user_name in ("Guest", "Administrator"):
		return

	frappe.get_doc({"doctype": "Drive Settings", "user": user.email}).insert(ignore_permissions=True)

	# Created as the new user so the team is owned by and shared with them.
	# Snapshot the full session state: frappe.set_user() overwrites session.sid with the
	# username and wipes session.data, so restoring only the user would leave the original
	# session corrupted (logging the acting user out on the next request).
	original_user = frappe.session.user
	original_sid = frappe.session.sid
	original_data = frappe.session.data
	try:
		frappe.set_user(user_name)
		create_team(user=user_name, team_name=user_name, personal=1)
	finally:
		frappe.set_user(original_user)
		frappe.session.sid = original_sid
		frappe.session.data = original_data
