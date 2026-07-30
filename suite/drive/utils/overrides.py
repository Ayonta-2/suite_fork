import frappe
from frappe.permissions import SYSTEM_USER_ROLE, get_doctypes_with_read

from suite.drive.utils import GENERAL_USER


def filter_file(user=None):
	"""Replaces the framework's File query conditions (skipped because of the
	`ignore_file_permissions` hook). Conservative: owner, direct Drive grants,
	public files, DocShares, and readable attachments — folder-inherited access
	needs Drive's recursive path traversal, impractical in SQL, so it's left to
	`has_permission`."""
	user = user or frappe.session.user
	roles = frappe.get_roles(user)
	if user == "Administrator" or "Suite Admin" in roles:
		return ""

	escaped = frappe.db.escape(user)
	clauses = [
		"`tabFile`.`is_private` = 0",
		f"`tabFile`.`owner` = {escaped}",
		f"`tabFile`.`name` IN (SELECT `entity` FROM `tabDrive Permission`"
		f" WHERE `user` IN ({escaped}, '{GENERAL_USER}', '') AND `read` = 1 AND `deny` = 0)",
		f"`tabFile`.`name` IN (SELECT `share_name` FROM `tabDocShare`"
		f" WHERE `share_doctype` = 'File' AND `user` = {escaped} AND `read` = 1)",
	]
	if SYSTEM_USER_ROLE in roles:
		readable = ", ".join(frappe.db.escape(dt) for dt in get_doctypes_with_read(user)) or "''"
		clauses.append(f"`tabFile`.`attached_to_doctype` IN ({readable})")
	return "(" + " OR ".join(clauses) + ")"


def common_filters(func):
	def decorator(user):
		user = user or frappe.session.user
		if user == "Administrator" or "Suite Admin" in frappe.get_roles(user):
			return ""
		return func(user)

	return decorator


@common_filters
def filter_drive_permission(user):
	user = frappe.db.escape(user)
	return f"""(`tabDrive Permission`.`owner` = {user} or `tabDrive Permission`.user = {user})"""


@common_filters
def filter_drive_settings(user):
	return f"(`tabDrive Settings`.`user` = {frappe.db.escape(user)})"


@common_filters
def filter_drive_invitation(user):
	return f"(`tabDrive User Invitation`.`email` = {frappe.db.escape(user)})"


@common_filters
def filter_drive_favourite(user):
	return f"""(`tabDrive Favourite`.`user` = {frappe.db.escape(user)})"""


@common_filters
def filter_drive_recent(user):
	return f"""(`tabDrive Entity Log`.`user` = {frappe.db.escape(user)})"""


@common_filters
def filter_drive_notif(user):
	user = frappe.db.escape(user)
	return f"(`tabDrive Notification`.to_user = {user} or `tabDrive Notification`.from_user = {user})"
