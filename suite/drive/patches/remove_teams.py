import shutil
from collections import Counter

import frappe

from suite.drive.utils import (
	GENERAL_USER,
	GROUP_PREFIX,
	PERMISSION_TYPES,
	STATUS_ACTIVE,
	STATUS_TRASHED,
	_deny_general_read,
	get_new_file_name,
	get_previous_teams_folder,
	get_root_folder,
	get_users_folder,
	grant_owner_access,
)
from suite.drive.utils.files import TRASH_PREFIX, FileManager, storage_key


def execute():
	"""Collapse Drive Teams into Drive's tree.

	Files are not moved: storage stays flat and every existing file_url keeps
	working. Only thumbnails and trashed blobs move, because their location is
	computed from the root rather than stored, and the root has changed.
	"""
	# captured before the collapse rewrites the homes
	sidecars = _team_prefixes()
	if frappe.db.exists("DocType", "Drive Team"):
		_collapse_teams()
	_sweep_sidecars(sidecars)


def _team_prefixes():
	"""{team: old storage prefix}, while the team homes are still folder-less."""
	if not frappe.db.has_column("File", "team"):
		return {}
	rows = frappe.get_all(
		"File",
		filters={"folder": ("is", "not set"), "team": ("is", "set")},
		fields=["team", "file_url"],
		limit_page_length=0,
	)
	return {r.team: storage_key(r.file_url).rstrip("/") for r in rows if r.file_url}


def _collapse_teams():
	"""Personal team roots become user folders under `Users`; the rest move into
	`Drive/Previous Teams`, membership rewritten as Drive Permission rows.

	`Users` carries no grant, so user folders are private. `Previous Teams` inherits
	`Drive`'s $GENERAL read, so each migrated team gets a $GENERAL deny and is
	reachable only by its old members. A public team keeps $GENERAL read."""
	previous_teams = get_previous_teams_folder()
	roots = {get_root_folder().name, previous_teams.name, get_users_folder().name}
	groups = {}

	teams = frappe.get_all("Drive Team", fields=["name", "title", "owner", "personal", "public", "quota"])
	print(f"Drive: collapsing {len(teams)} team(s)")
	for done, team in enumerate(teams, 1):
		if done % 100 == 0:
			print(f"  {done}/{len(teams)}")
		home = frappe.db.get_value("File", {"team": team.name, "folder": ("is", "not set")}, "name")
		if not home or home in roots:
			continue
		members = frappe.get_all(
			"Drive Team Member",
			filters={"parenttype": "Drive Team", "parent": team.name},
			fields=["user", "access_level"],
		)
		# Nothing matches a deleted user, and `Drive Settings.user` is a Link — a user
		# folder for one aborts the migration.
		members = [m for m in members if m.user and m.user != team.owner]
		members = [m for m in members if frappe.db.exists("User", m.user)]
		owned = bool(team.owner) and frappe.db.exists("User", team.owner)

		if team.personal and owned and not frappe.db.get_value("Drive Settings", team.owner, "user_folder"):
			_to_user_folder(home, team)
			_grant_members(home, members)
			continue

		_to_shared_folder(previous_teams, home, team, owned)
		# own row too, so it stays private if moved out of `Previous Teams`
		if team.public:
			_grant(home, GENERAL_USER, {"read": 1})
		else:
			_deny_general_read(home)

		# A team was a group of people, so it becomes one: members are granted
		# through a User Group, not fanned out per user. Keeps one row where the
		# team had one, and later membership changes still apply.
		team_groups = _user_groups_for(team, members)
		if team_groups:
			groups[team.name] = team_groups[0]
			_grant_group(home, team_groups)
		else:
			_grant_members(home, members)

	_expand_team_rows(groups)
	_drop_obsolete_revoke_rows()


LEVEL_LABEL = {0: "", 1: " (Members)", 2: " (Managers)"}


def _user_groups_for(team, members):
	"""`User Group`s mirroring the team: one holding everyone, plus one per higher
	access level. Returns {access_level: group name}, empty when nobody is left.

	The all-members group is what a `team=1` permission row resolves to, since such
	a row granted the whole team at its own access level.
	"""
	everyone = {m.user for m in members}
	if team.owner and frappe.db.exists("User", team.owner):
		everyone.add(team.owner)
	if not everyone:
		return {}

	buckets = {0: sorted(everyone)}
	for level in (1, 2):
		at_level = sorted(m.user for m in members if (m.access_level or 0) >= level)
		if at_level:
			buckets[level] = at_level

	title = team.title or team.name
	out = {}
	for level, users in buckets.items():
		name = get_new_group_name(title + LEVEL_LABEL[level])
		group = frappe.get_doc({"doctype": "User Group", "__newname": name})
		for user in users:
			group.append("user_group_members", {"user": user})
		group.insert(ignore_permissions=True)
		out[level] = group.name
	return out


def get_new_group_name(title):
	"""User Group names are the primary key, so a title collision needs a suffix."""
	base = (title or "Team").strip()[:100] or "Team"
	if not frappe.db.exists("User Group", base):
		return base
	for n in range(1, 1000):
		candidate = f"{base} ({n})"
		if not frappe.db.exists("User Group", candidate):
			return candidate
	return f"{base} {frappe.generate_hash(length=6)}"


def _grant_group(entity, groups):
	"""One row per access level, never per member — the Frappe team is 114 people,
	and a row each would put 114 rows on every entity it can reach.

	Grants at different levels overlap by design: a manager sits in both the
	all-members group and the managers group, and resolution takes the union of
	same-tier group rows, so the wider grant wins per permission type.
	"""
	for level, group in groups.items():
		_grant(entity, GROUP_PREFIX + group, _access_for(level))


def _access_for(access_level):
	if not access_level:
		return {"read": 1}
	perms = {"read": 1, "comment": 1, "upload": 1}
	if access_level == 2:
		perms.update({"write": 1, "share": 1})
	return perms


def _to_user_folder(home, team):
	frappe.db.set_value(
		"File",
		home,
		{"folder": get_users_folder().name, "file_name": team.owner, "owner": team.owner},
		update_modified=False,
	)
	grant_owner_access(home, team.owner)

	if not frappe.db.exists("Drive Settings", team.owner):
		frappe.get_doc({"doctype": "Drive Settings", "user": team.owner}).insert(ignore_permissions=True)
	frappe.db.set_value(
		"Drive Settings",
		team.owner,
		{"user_folder": home, "quota": team.quota or 0},
		update_modified=False,
	)


def _to_shared_folder(root, home, team, owned):
	values = {
		"folder": root.name,
		"file_name": get_new_file_name(team.title or team.name, root.name),
		"is_folder": 1,
		"file_type": "Folder",
		"status": STATUS_ACTIVE,
	}
	if owned:
		values["owner"] = team.owner
	frappe.db.set_value("File", home, values, update_modified=False)
	if owned:
		grant_owner_access(home, team.owner)


def _grant_members(entity, members):
	for m in members:
		if frappe.db.exists("Drive Permission", {"entity": entity, "user": m.user}):
			continue
		perms = (
			{"read": 1}
			if not m.access_level
			else {
				"read": 1,
				"comment": 1,
				"upload": 1,
				**({"write": 1, "share": 1} if m.access_level == 2 else {}),
			}
		)
		frappe.get_doc({"doctype": "Drive Permission", "entity": entity, "user": m.user, **perms}).insert(
			ignore_permissions=True
		)


def _grant(entity, user, perms):
	if frappe.db.exists("Drive Permission", {"entity": entity, "user": user}):
		return
	frappe.get_doc({"doctype": "Drive Permission", "entity": entity, "user": user, **perms}).insert(
		ignore_permissions=True
	)


def _expand_team_rows(groups):
	"""team=1 rows granted the row's team (stored in `user`) access to an entity.
	The team now has a User Group, so one group row replaces what would otherwise
	be a row per member — a 114-member team fanned out to 114 rows per entity.
	All-zero team rows were revoke attempts, which nothing grants any more."""
	for row in frappe.get_all("Drive Permission", filters={"team": 1}, fields=["*"]):
		perms = {t: row.get(t) or 0 for t in PERMISSION_TYPES}
		if not any(perms.values()):
			continue
		group = groups.get(row.user)
		if group:
			_grant(row.entity, GROUP_PREFIX + group, perms)
			continue
		# a personal team, or one with nobody left in it: no group to grant through
		for m in frappe.get_all(
			"Drive Team Member",
			filters={"parenttype": "Drive Team", "parent": row.user},
			fields=["user"],
		):
			if m.user and frappe.db.exists("User", m.user):
				_grant(row.entity, m.user, perms)
	# nothing links to a Drive Permission, and it has no delete-time logic
	frappe.db.delete("Drive Permission", {"team": 1})


def _drop_obsolete_revoke_rows():
	"""Link rows granting nothing were revoke attempts; nothing grants that way now."""
	frappe.db.delete("Drive Permission", {"user": "", "deny": 0, **dict.fromkeys(PERMISSION_TYPES, 0)})


def _sweep_sidecars(sidecars):
	"""Thumbnails and trashed blobs hang off "the root", which was each team's own
	prefix and is now Drive's. No File row points at either — both locations are
	computed — so moving the objects is the whole fix, with no url to rewrite.

	Flat sites have no trashed blobs to find (`move_to_trash` is a no-op there), so
	that half simply finds nothing. Idempotent: re-copying is harmless, and the
	originals are left alone.
	"""
	if not sidecars:
		return
	manager = FileManager()
	root = storage_key(get_root_folder().file_url).rstrip("/")
	prefix = manager.settings.thumbnail_prefix or "thumbnails"

	trashed = {}
	if frappe.db.has_column("File", "team"):
		for row in frappe.get_all(
			"File",
			filters={"status": STATUS_TRASHED},
			fields=["name", "file_name", "team"],
			limit_page_length=0,
		):
			trashed.setdefault(row.team, {})[row.file_name] = row.name

	moved, failed = Counter(), []
	for team, base in sidecars.items():
		if not base or base == root:
			continue
		for key in _list_prefix(manager, f"{base}/{prefix}/"):
			name = key.rsplit("/", 1)[-1]
			if name:
				_carry(manager, key, f"{root}/{prefix}/{name}", moved, failed)
		for key in _list_prefix(manager, f"{base}/{TRASH_PREFIX}/"):
			entity = trashed.get(team, {}).get(key.rsplit("/", 1)[-1])
			if entity:
				_carry(manager, key, f"{root}/{TRASH_PREFIX}/{entity}", moved, failed)

	for kind, n in sorted(moved.items()):
		print(f"Drive: moved {n} {kind}")
	for key, reason in failed[:20]:
		print(f"Drive: could not move {key}: {reason}")
	if len(failed) > 20:
		print(f"Drive: ... and {len(failed) - 20} more")


def _carry(manager, src, dest, moved, failed):
	kind = "trashed blob(s)" if TRASH_PREFIX in dest else "thumbnail(s)"
	if src == dest or _exists(manager, dest, False):
		return
	try:
		_copy(manager, src, dest)
		moved[kind] += 1
	except Exception as e:
		failed.append((src, f"{type(e).__name__}: {e}"))



def _list_prefix(manager, prefix):
	"""Every object directly under `prefix`, both backends."""
	if manager.s3_enabled:
		out, token = [], None
		while True:
			kwargs = {"Bucket": manager.bucket, "Prefix": prefix}
			if token:
				kwargs["ContinuationToken"] = token
			page = manager.conn.list_objects_v2(**kwargs)
			out += [o["Key"] for o in page.get("Contents", []) if not o["Key"].endswith("/")]
			if not page.get("IsTruncated"):
				return out
			token = page.get("NextContinuationToken")
	folder = _local(manager, prefix)
	if not folder.is_dir():
		return []
	return [f"{prefix.rstrip('/')}/{f.name}" for f in folder.iterdir() if f.is_file()]


def _local(manager, key):
	"""Upgraded sites store `?path=/<team>/<id>`, and `base / "/abs"` discards
	`base` — strip it so a local path can't escape the site folder."""
	return manager.site_folder / key.lstrip("/")


def _copy(manager, src, dest):
	if manager.s3_enabled:
		manager.conn.copy_object(
			Bucket=manager.bucket, CopySource={"Bucket": manager.bucket, "Key": src}, Key=dest
		)
		if _size(manager, dest) != _size(manager, src):
			raise OSError(f"copy of {src} did not verify")
	else:
		src_path = _local(manager, src)
		dest_path = _local(manager, dest)
		dest_path.parent.mkdir(parents=True, exist_ok=True)
		shutil.copy2(src_path, dest_path)
		if dest_path.stat().st_size != src_path.stat().st_size:
			raise OSError(f"copy of {src} did not verify")


def _size(manager, key):
	return manager.conn.head_object(Bucket=manager.bucket, Key=key)["ContentLength"]


def _exists(manager, key, container):
	if not key:
		return False
	if manager.s3_enabled:
		try:
			manager.conn.head_object(Bucket=manager.bucket, Key=key + "/" if container else key)
			return True
		except Exception:
			return False
	return _local(manager, key).exists()


def _blob_size(manager, key):
	try:
		return _size(manager, key) if manager.s3_enabled else _local(manager, key).stat().st_size
	except Exception:
		return 0
