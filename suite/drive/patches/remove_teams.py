import json
import os
import shutil
import time
from collections import Counter
from pathlib import Path

import frappe

from suite.drive.utils import (
	GENERAL_USER,
	GROUP_PREFIX,
	PERMISSION_TYPES,
	STATUS_ACTIVE,
	STATUS_TRASHED,
	WRITER_CONTENT_DOCTYPE,
	_deny_general_read,
	get_new_file_name,
	get_previous_teams_folder,
	get_root_folder,
	get_users_folder,
	grant_owner_access,
)
from suite.drive.utils.files import (
	S3_URL_PREFIX,
	TRASH_PREFIX,
	FileManager,
	get_s3_url,
	storage_key,
)

JOURNAL = "drive-relocation.jsonl"
ABORT_WINDOW = 120
MAX_COMPONENT_BYTES = 255
MAX_PATH_BYTES = 4096
S3_COPY_LIMIT = 5 * 1024**3
MAX_DEPTH = 64


def execute():
	"""Collapse Drive Teams into Drive's tree, then make storage mirror it.

	Both halves are idempotent and guarded on current state; the team half is
	skipped once the Drive Team tables are gone, so a re-run after a failed
	relocation still finishes the relocation.
	"""
	# captured before the collapse rewrites the homes: thumbnails and trashed blobs
	# live in sidecar directories under each team's old prefix, and nothing in the
	# tree walk can find them afterwards
	sidecars = _team_prefixes()
	if frappe.db.exists("DocType", "Drive Team"):
		_collapse_teams()
	_mirror_storage_to_tree(sidecars)


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


def _mirror_storage_to_tree(sidecars=None):
	"""`flat` is gone, so every blob has to sit where the folder tree says it does.

	Phase 0 surveys and prints, then waits. Phase 1 copies (never moves), verifies,
	then commits the new file_url, journalling the original key. Phase 2 deletes
	those originals, only if phase 1 was flawless.

	So an interrupted run costs duplicated storage, never lost storage, and
	re-running resumes off the committed file_urls.
	"""
	manager = FileManager()
	plan = frappe._dict(
		manager=manager,
		# `team` is the only reliable "Drive wrote this blob" test: keys were
		# prefixed per team, so no single path prefix covers the corpus
		team_column=frappe.db.has_column("File", "team"),
		actions=[],
		problems=[],
		skipped=Counter(),
		claimed={},
		renamed=[],
	)
	drive_root = get_root_folder()
	plan.trash_root = f"{storage_key(drive_root.file_url).rstrip('/')}/{TRASH_PREFIX}"
	for root in (drive_root, get_users_folder()):
		plan.root_key = storage_key(root.file_url).rstrip("/")
		_survey(plan, root.name, plan.root_key, False, False)

	plan.root_key = storage_key(drive_root.file_url).rstrip("/")
	plan.trash_root = f"{plan.root_key}/{TRASH_PREFIX}"
	_survey_sidecars(plan, sidecars or {})

	_announce(plan)
	_confirmed()

	journal = Path(frappe.get_site_path("private", "files")) / JOURNAL
	journal.parent.mkdir(parents=True, exist_ok=True)
	problems = list(plan.problems)
	with journal.open("a") as log:
		problems += _apply(plan, log)

	if problems:
		_report_failures(problems, journal)
		return
	print(f"Drive: relocation clean, removed {_drop_originals(manager, journal)} original blob(s)")


# ---------------------------------------------------------------- phase 0


def _survey(plan, parent, parent_key, in_trash, embeds, depth=0):
	"""Read-only: decide what every entity under `parent` should become."""
	if depth > MAX_DEPTH:
		plan.problems.append({"entity": parent, "reason": "tree deeper than expected"})
		return

	fields = [
		"name",
		"file_name",
		"file_url",
		"file_size",
		"file_type",
		"is_folder",
		"is_private",
		"attached_to_doctype",
		"status",
		"content_doctype",
	]
	if plan.team_column:
		fields.append("team")

	# flat storage let siblings share a name; a mirrored tree can't. Oldest keeps it.
	taken = set()
	for child in frappe.get_all("File", filters={"folder": parent}, fields=fields, order_by="creation"):
		writer = child.content_doctype == WRITER_CONTENT_DOCTYPE
		container = bool(child.is_folder) or writer
		ignored = (
			"link (external url)"
			if child.file_type == "Link"
			else "foreign content doctype (no storage of its own)"
			if child.content_doctype and not writer
			else None
		)
		if ignored:
			_skip(plan, child, _category(container, writer, embeds), ignored)
			continue

		trashed = in_trash or child.status == STATUS_TRASHED
		name = _claim_name(plan, child, taken, trashed)
		if not name:
			plan.problems.append({"entity": child.name, "reason": f"unusable name {child.file_name!r}"})
			continue

		target = _target_key(parent_key, name)
		if not target:
			plan.problems.append({"entity": child.name, "reason": f"path too long for {name!r}"})
			continue

		placed = _decide(plan, child, target, container, writer, trashed, embeds)
		if container:
			_survey(plan, child.name, placed + "/.embeds" if writer else placed, trashed, writer, depth + 1)


def _survey_sidecars(plan, sidecars):
	"""Thumbnails and trashed blobs sit beside the files, under each team's own
	prefix, and no tree walk reaches them — the tree has no row for either.

	Thumbnails are named by entity id, so they just move. Trash was keyed by
	file_name per team; one root means two teams could both hold a `readme.md`,
	so `__get_trash_path` now keys by id and these move onto that.
	"""
	prefix = plan.manager.settings.thumbnail_prefix or "thumbnails"
	trashed = {}
	if plan.team_column:
		for row in frappe.get_all(
			"File",
			filters={"status": STATUS_TRASHED},
			fields=["name", "file_name", "team"],
			limit_page_length=0,
		):
			trashed.setdefault(row.team, {})[row.file_name] = row.name

	for team, base in sidecars.items():
		if not base:
			continue
		for key in _list_prefix(plan.manager, f"{base}/{prefix}/"):
			name = key.rsplit("/", 1)[-1]
			if name:
				_sidecar_action(plan, key, f"{plan.root_key}/{prefix}/{name}", "thumbnails")
		for key in _list_prefix(plan.manager, f"{base}/{TRASH_PREFIX}/"):
			name = key.rsplit("/", 1)[-1]
			entity = trashed.get(team, {}).get(name)
			if not entity:
				# nothing in the tree claims it; leave it rather than guess
				_skip_key(plan, key, "trashed blob with no matching row")
				continue
			_sidecar_action(plan, key, f"{plan.root_key}/{TRASH_PREFIX}/{entity}", "trash")


def _sidecar_action(plan, current, target, kind):
	if current == target:
		plan.actions.append({"entity": current, "kind": kind, "action": "unchanged", "old": current, "new": target})
		return
	claimant = plan.claimed.get(target)
	if claimant:
		plan.problems.append({"entity": current, "reason": f"{target} is also claimed by {claimant}"})
		return
	plan.claimed[target] = current
	plan.actions.append(
		{
			"entity": current,
			"file_name": current.rsplit("/", 1)[-1],
			"kind": kind,
			"action": "copy",
			"old": current,
			"new": target,
			"url": None,  # no File row to point anywhere
			"journal": True,
			"bytes": _blob_size(plan.manager, current),
		}
	)


def _skip_key(plan, key, reason):
	plan.skipped[reason] += 1
	plan.actions.append({"entity": key, "kind": "sidecar", "action": "skip", "old": key, "reason": reason})


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


def _claim_name(plan, child, taken, trashed):
	"""Deduped name, persisted when it changes — `get_disk_path` recomputes paths
	from file_name on every later rename/move.

	Trashed entities keep theirs: the blob is at `.trash/<file_name>` and restore
	looks it up by name. They never copy, so a duplicate target is harmless.
	"""
	name = _sanitize(child.file_name)
	if not name:
		return None
	if trashed:
		return name

	stem, ext = os.path.splitext(name)
	candidate, n = name, 0
	while candidate.casefold() in taken:
		n += 1
		candidate = f"{stem} ({n}){ext}"
	taken.add(candidate.casefold())

	if candidate != child.file_name:
		frappe.db.set_value("File", child.name, "file_name", candidate, update_modified=False)
		plan.renamed.append((child.file_name, candidate))
	return candidate


def _sanitize(file_name):
	"""A name has to survive as one path component, on disk and as an S3 key."""
	name = (file_name or "").strip().replace("/", "_").replace("\\", "_").strip(". ")
	while name and len(name.encode()) > MAX_COMPONENT_BYTES:
		name = name[:-1]
	return name or None


def _decide(plan, child, target, container, writer, trashed, embed):
	"""Returns the key this entity will end up under."""
	manager = plan.manager
	current = storage_key(child.file_url).rstrip("/") if child.file_url else ""
	kind = _category(container, writer, embed)

	def record(action, **extra):
		plan.actions.append(
			{
				"entity": child.name,
				"file_name": child.file_name,
				"kind": kind,
				"action": action,
				"old": current,
				"new": target,
				"url": _rewrap(plan, child.file_url, target, container),
				"journal": bool(current) and not trashed,
				**extra,
			}
		)

	if current == target:
		if writer:
			record("dir", journal=False)
		else:
			plan.actions.append(
				{"entity": child.name, "kind": kind, "action": "unchanged", "old": current, "new": target}
			)
		return target

	excluded = _excluded(plan, child, current, container)
	if excluded:
		_skip(plan, child, kind, excluded, current)
		return current

	# names are deduped per parent, so a clash here is a bug, not data
	if not container and not trashed:
		claimant = plan.claimed.get(target)
		if claimant:
			plan.problems.append({"entity": child.name, "reason": f"{target} is also claimed by {claimant}"})
			return current
		plan.claimed[target] = child.name

	if container:
		record("dir")
	elif trashed:
		# Where the blob is depends on how the site stored it: `move_to_trash` was a
		# no-op when `flat` was on, so it is still at `current`; otherwise it sits in
		# the old per-team `.trash`, which _survey_sidecars sweeps. Either way the
		# file_url becomes the tree position, which is where a restore puts it back.
		trash_key = f"{plan.trash_root}/{child.name}"
		if current and current != trash_key and _exists(manager, current, False):
			if plan.claimed.get(trash_key):
				plan.problems.append({"entity": child.name, "reason": f"{trash_key} is already claimed"})
				return current
			plan.claimed[trash_key] = child.name
			plan.actions.append(
				{
					"entity": child.name,
					"file_name": child.file_name,
					"kind": kind,
					"action": "copy",
					"old": current,
					"new": trash_key,
					"url": _rewrap(plan, child.file_url, target, container),
					"journal": True,
					"bytes": _blob_size(manager, current),
				}
			)
		else:
			record("repath")
	elif _exists(manager, target, False):
		if _exists(manager, current, False):
			plan.problems.append({"entity": child.name, "reason": f"{target} is already taken"})
			return current
		# an earlier run copied this but never committed the file_url
		record("repath")
	elif not _exists(manager, current, False):
		# the row outlived its blob; nothing to copy and nothing to reclaim
		_skip(plan, child, kind, "source blob already missing", current)
		return current
	else:
		size = _blob_size(manager, current)
		if manager.s3_enabled and size > S3_COPY_LIMIT:
			plan.problems.append({"entity": child.name, "reason": "over the 5 GB copy_object limit"})
			return current
		record("copy", bytes=size)
	return target


def _skip(plan, child, kind, reason, current=""):
	plan.skipped[reason] += 1
	plan.actions.append(
		{
			"entity": child.name,
			"file_name": child.file_name,
			"kind": kind,
			"action": "skip",
			"old": current or storage_key(child.file_url or ""),
			"reason": reason,
		}
	)


def _blob_size(manager, key):
	try:
		return _size(manager, key) if manager.s3_enabled else _local(manager, key).stat().st_size
	except Exception:
		return 0


def _totals(plan):
	totals = Counter()
	for a in plan.actions:
		if a["action"] not in ("skip", "unchanged"):
			totals[f"{a['kind']} ({a['action']})"] += 1
	totals["bytes to copy"] = sum(a.get("bytes", 0) for a in plan.actions if a["action"] == "copy")
	return dict(totals)


def _announce(plan):
	print("\nDrive storage relocation plan")
	for label, count in sorted(_totals(plan).items()):
		print(f"  {count:>12}  {label}")
	for reason, count in sorted(plan.skipped.items()):
		print(f"  {count:>12}  left alone — {reason}")
	for problem in plan.problems:
		print(f"  BLOCKED  {problem['entity']}: {problem['reason']}")

	if plan.renamed:
		print(f"\n  {len(plan.renamed)} file(s) renamed so siblings stay unique on disk:")
		for before, after in plan.renamed[:20]:
			print(f"    {before!r}  ->  {after!r}")
		if len(plan.renamed) > 20:
			print(f"    ... and {len(plan.renamed) - 20} more")

	sample = _sample(plan.actions)
	if sample:
		print(f"\n  sample of {len(sample)} path change(s):")
		for a in sample:
			print(f"    [{a['kind']}/{a['action']}] {a['old'] or '(none)'}  ->  {a['new']}")


def _sample(actions, size=100):
	"""Round-robin across kind/action buckets so every class shows up, and put
	the entities that actually move ahead of the ones already in place."""
	buckets = {}
	for a in actions:
		if a["action"] == "skip":
			continue
		buckets.setdefault((a["kind"], a["action"]), []).append(a)
	order = sorted(buckets, key=lambda k: (k[1] == "unchanged", k))
	out = []
	while len(out) < size and any(buckets[k] for k in order):
		for key in order:
			if buckets[key] and len(out) < size:
				out.append(buckets[key].pop(0))
	return out


# ---------------------------------------------------------------- phase 1


def _apply(plan, log):
	manager = plan.manager
	problems = []
	for a in plan.actions:
		if a["action"] in ("skip", "unchanged"):
			continue
		try:
			if a["action"] == "dir":
				_make_dir(manager, a["new"])
				if a["kind"] == "writer documents":
					_make_dir(manager, a["new"] + "/.embeds")
				if a["old"] == a["new"]:
					continue
			elif a["action"] == "copy":
				_copy(manager, a["old"], a["new"])
		except Exception as e:
			problems.append({"entity": a["entity"], "reason": f"{type(e).__name__}: {e}"})
			continue

		# sidecars (thumbnails, trash) have no File row — `entity` is their key
		if a.get("url"):
			frappe.db.set_value("File", a["entity"], "file_url", a["url"], update_modified=False)
		if a["journal"] and (a["action"] != "dir" or _exists(manager, a["old"], True)):
			log.write(
				json.dumps({"entity": a["entity"], "key": a["old"], "dir": a["action"] == "dir"}) + "\n"
			)
			log.flush()
	frappe.db.commit()
	return problems


def _category(container, writer, embed):
	if writer:
		return "writer documents"
	if embed:
		return "embeds"
	return "folders" if container else "files"


def _excluded(plan, child, current, container):
	"""Allowlist: only what Drive itself wrote gets repathed. Framework uploads
	adopted into a Drive folder keep their url and privacy — a public one is
	served straight off /files/ by nginx, so relocating it would 404."""
	if not current:
		# flat sites left folders off disk; anything else simply has no blob
		return None if container else "no file_url"
	if plan.team_column and not child.team:
		# a framework upload Drive adopted. Not keyed on attached_to_doctype: legacy
		# migrations tagged Drive's own Writer embeds with it, and those must move.
		return "not a Drive file"
	if not plan.team_column and current != plan.root_key and not current.startswith(plan.root_key + "/"):
		return "outside the Drive root prefix"
	# team homes predate is_private, so it only disqualifies leaf files
	if not container and not child.is_private:
		return "not private (served straight off /files/)"
	return None


def _target_key(parent_key, name):
	key = f"{parent_key}/{name}"
	return key if len(key.encode()) <= MAX_PATH_BYTES else None


def _rewrap(plan, old_url, key, container):
	"""Keep the stored url in whatever form this entity already used, and where
	there is no form to keep — flat sites left folders and writer docs with no
	file_url at all — take the backend's."""
	if container:
		key += "/"
	old = str(old_url or "")
	if old.startswith(S3_URL_PREFIX):
		return get_s3_url(key)
	if old.startswith("/"):
		return "/" + key
	if not old:
		return get_s3_url(key) if plan.manager.s3_enabled else "/" + key
	return key


def _local(manager, key):
	"""Upgraded sites store `?path=/<team>/<id>`, and `base / "/abs"` discards
	`base` — strip it so a local path can't escape the site folder."""
	return manager.site_folder / key.lstrip("/")


def _make_dir(manager, key):
	if manager.s3_enabled:
		manager.conn.put_object(Bucket=manager.bucket, Key=key + "/", Body="")
	else:
		_local(manager, key).mkdir(parents=True, exist_ok=True)


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


# ---------------------------------------------------------------- phase 2


def _drop_originals(manager, journal):
	"""Only reached when phase 1 had zero failures, so every journalled key has
	a verified copy elsewhere."""
	if not journal.exists():
		return 0
	entries = [json.loads(line) for line in journal.read_text().splitlines() if line.strip()]
	live = {storage_key(u).rstrip("/") for u in frappe.get_all("File", pluck="file_url") if u}

	removed = 0
	for entry in sorted(entries, key=lambda e: len(e["key"]), reverse=True):
		if entry["key"] in live:
			continue
		try:
			if manager.s3_enabled:
				manager.conn.delete_object(
					Bucket=manager.bucket, Key=entry["key"] + "/" if entry["dir"] else entry["key"]
				)
			elif entry["dir"]:
				_prune_dir(_local(manager, entry["key"]))
			else:
				_local(manager, entry["key"]).unlink()
			removed += 1
		except OSError:
			pass

	if not manager.s3_enabled:
		# the flat layout's `embeds/` and friends are left empty behind their files
		leftovers = {str(Path(e["key"]).parent) for e in entries if not e["dir"]}
		for parent in sorted(leftovers - live, key=len, reverse=True):
			try:
				_local(manager, parent).rmdir()
			except OSError:
				pass

	stamp = frappe.utils.now().replace(" ", "-").replace(":", "")
	journal.rename(journal.with_name(f"drive-relocation-{stamp}.done.jsonl"))
	return removed


def _prune_dir(path):
	"""Legacy dirs are left as husks by the copy; drop them, and any untracked
	empty scaffolding (.embeds, ...) inside them. Anything holding real data stays."""
	for child in path.iterdir():
		if child.is_dir():
			_prune_dir(child)
	path.rmdir()


def _report_failures(problems, journal):
	pending = (
		len([line for line in journal.read_text().splitlines() if line.strip()]) if journal.exists() else 0
	)
	print(
		f"Drive: {len(problems)} failure(s) during relocation — originals NOT deleted, "
		f"{pending} still journalled in {journal}. Re-run `bench migrate` once resolved."
	)
	for problem in problems[:20]:
		print(f"  - {problem['entity']}: {problem['reason']}")
	frappe.log_error("Drive: storage relocation incomplete", json.dumps(problems, indent=1)[:10000])


def _confirmed():
	"""Must not swallow the interrupt: returning normally lets frappe log the patch
	as done, and the relocation would never be offered again."""
	try:
		for left in range(ABORT_WINDOW, 0, -1):
			print(f"\r  Starting relocation in {left:3}s — Ctrl-C to quit ", end="", flush=True)
			time.sleep(1)
		print()
	except KeyboardInterrupt:
		print("\nDrive: quit before any change; storage is untouched and the patch will re-run.")
		raise
