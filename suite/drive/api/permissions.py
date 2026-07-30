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

	if entity.get("attached_to_doctype") and entity.get("attached_to_name"):
		# Attachments follow their reference document — the framework contract
		# content apps (e.g. Slides media) rely on — instead of the tree's
		# root-inherited read. Explicit Drive rows override it per type, so a
		# deny revokes rather than falling through to the reference document.
		path = generate_upward_path(entity.name, user, baseline_read=False)
		access = filter_access(path)
		decided = set(path[-1]["decided"])
		if decided != set(PERMISSION_TYPES):
			access = {**_ref_doc_access(entity, user), **{t: access[t] for t in decided}}
		return {**access, "type": "user" if access["write"] else "guest"}

	access = filter_access(generate_upward_path(entity.name, user))
	return {**access, "type": "user" if access["write"] else "guest"}


def _ref_doc_access(entity, user):
	"""Framework attachment semantics: write on the reference document gives
	write, read gives read, public files are readable by anyone."""
	public = not frappe.db.get_value("File", entity.name, "is_private")
	write = read = False
	if frappe.db.exists(entity.attached_to_doctype, entity.attached_to_name):
		ref = frappe.get_doc(entity.attached_to_doctype, entity.attached_to_name)
		write = bool(frappe.has_permission(ref.doctype, "write", doc=ref, user=user))
		read = write or bool(frappe.has_permission(ref.doctype, "read", doc=ref, user=user))
	return {
		**NO_ACCESS,
		"read": int(read or public),
		"comment": int(write),
		"write": int(write),
	}


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


def exceeds_grant_ceiling(entity, requested, user=None):
	"""Levels in `requested` the user can't hand out because they don't hold
	them: a user with read+share can't grant write. Admins hold everything
	implicitly — get_user_access doesn't know that."""
	user = user or frappe.session.user
	if user == "Administrator" or "Suite Admin" in frappe.get_roles(user):
		return []
	granter = get_user_access(entity, user)
	return [t for t in PERMISSION_TYPES if requested.get(t) and not granter.get(t)]


def drive_permission_has_permission(doc, ptype="read", user=None):
	"""Gate direct Drive Permission access via the generic client API.

	Reads are additionally scoped by `filter_drive_permission`; creating or
	modifying an ACL row requires `share` rights on the target entity and, since
	the generic API bypasses share(), the same grant ceiling that method
	enforces. The share()/unshare() flows save with ignore_permissions.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or "Suite Admin" in frappe.get_roles(user):
		return True
	if isinstance(doc, str):
		doc = frappe.get_doc("Drive Permission", doc)
	if ptype in ("read", "select"):
		return doc.owner == user or doc.user == user
	if not user_has_permission(doc.entity, "share", user):
		return False
	if ptype == "delete" or doc.deny:
		# Removing a row, or writing a deny, revokes rather than grants.
		return True
	return not exceeds_grant_ceiling(doc.entity, doc.as_dict(), user)


def drive_settings_has_permission(doc, ptype="read", user=None):
	"""Settings are per-user self-service. `quota` and `user_folder` are
	server-managed and additionally guarded in the controller."""
	user = user or frappe.session.user
	if user == "Administrator" or "Suite Admin" in frappe.get_roles(user):
		return True
	if user == "Guest":
		return False
	if isinstance(doc, str):
		doc = frappe.get_doc("Drive Settings", doc)
	return doc.user == user


def drive_invitation_has_permission(doc, ptype="read", user=None):
	"""Only admins issue invitations from the client. Sharing with an
	unregistered address goes through `create_invites`, which inserts with
	ignore_permissions once share rights are checked."""
	user = user or frappe.session.user
	if user == "Administrator" or "Suite Admin" in frappe.get_roles(user):
		return True
	if isinstance(doc, str):
		doc = frappe.get_doc("Drive User Invitation", doc)
	return ptype in ("read", "select") and doc.email == user


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
