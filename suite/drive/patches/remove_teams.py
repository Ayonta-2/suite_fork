import frappe

from suite.drive.utils import (
	GENERAL_USER,
	PERMISSION_TYPES,
	get_new_file_name,
	get_root_folder,
	get_user_folder,
)

FULL_ACCESS = dict.fromkeys(PERMISSION_TYPES, 1)


def execute():
	"""Collapse Drive Teams into the single site tree.

	Personal team roots become private user folders; other team roots become
	folders under the site root with membership rewritten as Drive Permission
	rows. Runs while the Drive Team tables still exist (they are dropped by a
	later patch) and is idempotent: every step is guarded on current state.
	"""
	if not frappe.db.exists("DocType", "Drive Team"):
		return

	root = get_root_folder()

	teams = frappe.get_all(
		"Drive Team", fields=["name", "title", "owner", "personal", "public", "quota"]
	)
	for team in teams:
		home = frappe.db.get_value("File", {"team": team.name, "folder": ("is", "not set")}, "name")
		if not home:
			continue
		members = frappe.get_all(
			"Drive Team Member",
			filters={"parenttype": "Drive Team", "parent": team.name},
			fields=["user", "access_level"],
		)
		members = [m for m in members if m.user and m.user != team.owner]

		if team.personal and not frappe.db.get_value("Drive Settings", team.owner, "user_folder"):
			_to_user_folder(root, home, team)
		else:
			_to_shared_folder(root, home, team)
			if not team.public:
				_deny(home, GENERAL_USER)
		_grant_members(home, members)

	_expand_team_rows()
	_convert_public_revoke_rows()
	_tuck_away_stray_root_children(root)


def _to_user_folder(root, home, team):
	frappe.db.set_value(
		"File",
		home,
		{"folder": root.name, "file_name": team.owner, "owner": team.owner},
		update_modified=False,
	)
	_deny(home, GENERAL_USER)

	if not frappe.db.exists("Drive Settings", team.owner):
		frappe.get_doc({"doctype": "Drive Settings", "user": team.owner}).insert(ignore_permissions=True)
	frappe.db.set_value(
		"Drive Settings",
		team.owner,
		{"user_folder": home, "quota": team.quota or 0},
		update_modified=False,
	)


def _to_shared_folder(root, home, team):
	frappe.db.set_value(
		"File",
		home,
		{
			"folder": root.name,
			"file_name": get_new_file_name(team.title or team.name, root.name, "Folder"),
			"owner": team.owner,
		},
		update_modified=False,
	)


def _grant_members(entity, members):
	for m in members:
		if frappe.db.exists("Drive Permission", {"entity": entity, "user": m.user}):
			continue
		perms = (
			{"read": 1}
			if not m.access_level
			else {"read": 1, "comment": 1, "upload": 1, **({"write": 1, "share": 1} if m.access_level == 2 else {})}
		)
		frappe.get_doc({"doctype": "Drive Permission", "entity": entity, "user": m.user, **perms}).insert(
			ignore_permissions=True
		)


def _deny(entity, user):
	if frappe.db.exists("Drive Permission", {"entity": entity, "user": user, "deny": 1}):
		return
	frappe.get_doc(
		{"doctype": "Drive Permission", "entity": entity, "user": user, "deny": 1, **FULL_ACCESS}
	).insert(ignore_permissions=True)


def _expand_team_rows():
	"""team=1 rows granted the row's team (stored in `user`) access to an
	entity; expand them into per-member rows. All-zero team rows were revoke
	attempts — turn them into $GENERAL denies."""
	for row in frappe.get_all("Drive Permission", filters={"team": 1}, fields=["*"]):
		if not any(row.get(t) for t in PERMISSION_TYPES):
			_deny(row.entity, GENERAL_USER)
		else:
			members = frappe.get_all(
				"Drive Team Member",
				filters={"parenttype": "Drive Team", "parent": row.user},
				fields=["user", "access_level"],
			)
			for m in members:
				if not m.user or frappe.db.exists(
					"Drive Permission", {"entity": row.entity, "user": m.user, "team": 0}
				):
					continue
				frappe.get_doc(
					{
						"doctype": "Drive Permission",
						"entity": row.entity,
						"user": m.user,
						**{t: row.get(t) or 0 for t in PERMISSION_TYPES},
					}
				).insert(ignore_permissions=True)
		frappe.delete_doc("Drive Permission", row.name, ignore_permissions=True, force=True)


def _convert_public_revoke_rows():
	"""All-zero `user=''` rows were the old, inert "revoke public access"
	hack; deny rows are their working equivalent."""
	for row in frappe.get_all("Drive Permission", filters={"user": "", "deny": 0}, fields=["*"]):
		if any(row.get(t) for t in PERMISSION_TYPES):
			continue
		frappe.db.set_value("Drive Permission", row.name, {"deny": 1, **FULL_ACCESS}, update_modified=False)


def _tuck_away_stray_root_children(root):
	"""Framework files sitting directly under Home were owner-only under
	framework permissions; root-inherited read would expose them, so move each
	into its owner's user folder (or the deny-marked attachments folder)."""
	attachments = frappe.db.exists("File", "Home/Attachments")
	if attachments:
		_deny(attachments, GENERAL_USER)

	for f in frappe.get_all(
		"File",
		filters={"folder": root.name, "team": ("is", "not set")},
		fields=["name", "owner"],
	):
		if f.name == attachments:
			continue
		target = frappe.db.get_value("Drive Settings", f.owner, "user_folder")
		if not target and frappe.db.exists("User", f.owner):
			# Owner never had a personal team; give them a user folder rather
			# than leaving the file under the root, where baseline read exposes it.
			target = get_user_folder(f.owner).name
		frappe.db.set_value("File", f.name, "folder", target or attachments, update_modified=False)
