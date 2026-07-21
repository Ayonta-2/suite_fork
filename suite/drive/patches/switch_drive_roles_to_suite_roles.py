import frappe
from frappe.utils import now

# (old Drive role -> shared Suite role) that access has been consolidated onto.
ROLE_MAP = {
	"Drive User": "Suite User",
	"Drive Admin": "Suite Admin",
}


def execute() -> None:
	"""Move existing Drive role assignments onto the shared Suite roles.

	Drive access moved from the app-specific "Drive User"/"Drive Admin" roles to
	the suite-wide "Suite User"/"Suite Admin" roles. Both Drive roles carried desk
	access, as do the Suite roles now, so holders stay System Users and their
	``user_type`` needs no recompute — the assignments are simply swapped. Users
	currently holding a Drive role gain the matching Suite role (if they don't have
	it already), then the stale Drive assignments are dropped. The Drive Role docs
	themselves are left in place; deleting a role cascades through core.
	"""

	for suite_role in set(ROLE_MAP.values()):
		if not frappe.db.exists("Role", suite_role):
			frappe.get_doc({"doctype": "Role", "role_name": suite_role, "desk_access": 1}).insert(
				ignore_permissions=True
			)

	for drive_role, suite_role in ROLE_MAP.items():
		users = set(
			frappe.get_all(
				"Has Role",
				filters={"parenttype": "User", "role": drive_role},
				pluck="parent",
			)
		)
		users.discard("Administrator")
		_grant_role(users, suite_role)

	frappe.db.delete("Has Role", {"parenttype": "User", "role": ("in", list(ROLE_MAP.keys()))})


def _grant_role(users: set[str], role: str) -> None:
	"""Grant ``role`` to ``users`` with one bulk insert into ``Has Role``.

	The Suite roles carry desk access, but every user being migrated already holds
	a desk-access Drive role and is therefore already a System User, so inserting
	the child rows directly (rather than via ``User.add_roles``, an N+1 on migrate)
	does not leave ``user_type`` stale. Users who already hold the role are skipped,
	and the next ``idx`` per user is derived from their existing rows.
	"""

	if not users:
		return

	existing = frappe.get_all(
		"Has Role",
		filters={"parenttype": "User", "parent": ("in", list(users))},
		fields=["parent", "role", "idx"],
	)
	already_has = {row.parent for row in existing if row.role == role}
	next_idx = {}
	for row in existing:
		next_idx[row.parent] = max(next_idx.get(row.parent, 0), row.idx)

	timestamp = now()
	rows = [
		(
			frappe.generate_hash(length=10),
			user,
			"User",
			"roles",
			role,
			"Administrator",
			timestamp,
			timestamp,
			"Administrator",
			next_idx.get(user, 0) + 1,
			0,
		)
		for user in users
		if user not in already_has
	]
	if not rows:
		return

	frappe.db.bulk_insert(
		"Has Role",
		fields=[
			"name",
			"parent",
			"parenttype",
			"parentfield",
			"role",
			"owner",
			"creation",
			"modified",
			"modified_by",
			"idx",
			"docstatus",
		],
		values=rows,
	)
