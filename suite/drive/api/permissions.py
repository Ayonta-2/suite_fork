import frappe
from frappe.model.document import Document

from suite.drive.utils import (
	FILE_FIELDS,
	GENERAL_USER,
	PERMISSION_TYPES,
	STATUS_ACTIVE,
	entity_kind,
	generate_upward_path,
	get_valid_breadcrumbs,
	hide_storage_key,
)

NO_ACCESS = {
	"read": 0,
	"comment": 0,
	"share": 0,
	"write": 0,
	"upload": 0,
}


def filter_access(path):
	return {k: v for k, v in path[-1].items() if k in NO_ACCESS.keys()}


@frappe.whitelist(allow_guest=True)
def get_user_access(entity: str | Document | frappe._dict, user: str | None = None):
	"""
	Return the user specific permissions for an entity.
	"""
	if isinstance(entity, str):
		entity = frappe.get_cached_doc("File", entity)
	if not user:
		user = frappe.session.user

	# Owners hold everything, bypassing any deny on the path.
	if user != "Guest" and entity.owner == user:
		return {**dict.fromkeys(PERMISSION_TYPES, 1), "type": "admin"}

	access = filter_access(generate_upward_path(entity.name, user))
	return {**access, "type": "user" if access["write"] else "guest"}


@frappe.whitelist(allow_guest=True)
def get_entity_with_permissions(entity_name: str):
	"""
	Return file data with permissions
	"""
	entity = frappe.get_all(
		"File",
		filters={"name": entity_name, "status": STATUS_ACTIVE},
		fields=FILE_FIELDS,
		limit=1,
	)
	if not entity:
		# Mimic API v2 points
		frappe.local.response.errors = [
			{
				"type": "PageDoesNotExistError",
				"message": "We couldn't find what you're looking for.",
			}
		]
		frappe.throw("We couldn't find what you're looking for.", frappe.PageDoesNotExistError)
	entity = entity[0]

	user_access = get_user_access(entity)
	if not user_access.get("read"):
		frappe.local.response.errors = [
			{
				"type": "PermissionError",
				"message": "You don't have access to this file.",
			}
		]
		frappe.throw("You don't have access to this file.", frappe.PermissionError)

	owner_info = frappe.db.get_value("User", entity.owner, ["user_image", "full_name"], as_dict=True) or {}
	breadcrumbs = {"breadcrumbs": get_valid_breadcrumbs(entity.name, user_access)}
	favourite = frappe.db.get_value(
		"Drive Favourite",
		{
			"entity": entity_name,
			"user": frappe.session.user,
		},
		["entity as is_favourite"],
	)
	return_obj = entity | user_access | owner_info | breadcrumbs | {"is_favourite": favourite}

	# General access marker: -2 public (link), -1 site users, 0 restricted.
	default = 0
	if get_user_access(entity, "Guest")["read"]:
		default = -2
	elif generate_upward_path(entity_name, GENERAL_USER)[-1]["read"]:
		default = -1
	return_obj["share_count"] = default

	return_obj["kind"] = entity_kind(entity)
	hide_storage_key(return_obj)

	# To work with modern frappe-ui composables
	frappe.response["data"] = return_obj
	return return_obj


@frappe.whitelist()
def get_shared_with_list(entity: str):
	"""
	Return the list of users with whom this file or folder has been shared

	:param entity: Document-name of this file or folder
	:raises PermissionError: If the user does not have edit permissions
	:return: List of users, with permissions and last modified datetime
	:rtype: list[frappe._dict]
	"""
	if not user_has_permission(entity, "share"):
		raise frappe.PermissionError("You do not have permission to check the shares.")

	permissions = frappe.db.get_all(
		"Drive Permission",
		filters=[["entity", "=", entity], ["user", "not in", ["", GENERAL_USER]], ["deny", "=", 0]],
		order_by="user",
		fields=["user", "read", "write", "comment", "upload", "share"],
	)

	owner = frappe.db.get_value("File", entity, "owner")
	permissions.insert(
		0,
		frappe.db.get_value("User", owner, ["user_image", "full_name", "name as user"], as_dict=True),
	)

	for p in permissions:
		user_info = frappe.db.get_value("User", p.user, ["user_image", "full_name", "email"], as_dict=True)
		if user_info:
			p.update(user_info)
	return permissions


def drive_permission_has_permission(doc, ptype="read", user=None):
	"""Gate direct Drive Permission access via the generic client API.

	Reads are additionally scoped by `filter_drive_permission`; creating or
	modifying an ACL row requires `share` rights on the target entity, so a user
	can't grant themselves access by inserting permission rows directly. The
	share()/unshare() flows are unaffected as they save with ignore_permissions.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or "Suite Admin" in frappe.get_roles(user):
		return True
	if isinstance(doc, str):
		doc = frappe.get_doc("Drive Permission", doc)
	if ptype in ("read", "select"):
		return doc.owner == user or doc.user == user
	return bool(user_has_permission(doc.entity, "share", user))


def user_has_permission(doc, ptype, user=None):
	if isinstance(doc, str):
		doc = frappe.get_doc("File", doc)
	if not user:
		user = frappe.session.user
	if user == "Administrator" or ptype == "create":
		return True
	if ptype not in PERMISSION_TYPES:
		# Should ideally deflect to Framework
		ptype = "write"
	access = get_user_access(doc, user)
	if ptype in access:
		return bool(access[ptype])
