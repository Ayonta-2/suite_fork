import json
import shutil
import time
from collections import Counter
from pathlib import Path

import frappe

from suite.drive.overrides.file import FRAMEWORK_FOLDERS
from suite.drive.utils import (
	GENERAL_USER,
	PERMISSION_TYPES,
	STATUS_ACTIVE,
	STATUS_TRASHED,
	WRITER_CONTENT_DOCTYPE,
	get_new_file_name,
	get_previous_teams_folder,
	get_root_folder,
	get_site_folder,
	get_user_folder,
	get_users_folder,
	grant_owner_access,
)
from suite.drive.utils.files import S3_URL_PREFIX, FileManager, get_s3_url, storage_key

JOURNAL = "drive-relocation.jsonl"
ABORT_WINDOW = 120
MAX_COMPONENT_BYTES = 255
MAX_PATH_BYTES = 4096
S3_COPY_LIMIT = 5 * 1024**3
MAX_DEPTH = 64


def execute():
	"""Collapse Drive Teams into the single site tree, then make storage mirror it.

	Both halves are idempotent and guarded on current state; the team half is
	additionally skipped once the Drive Team tables are gone, so a re-run after
	a failed relocation still finishes the relocation.
	"""
	if frappe.db.exists("DocType", "Drive Team"):
		_collapse_teams()
	_mirror_storage_to_tree()


def _collapse_teams():
	"""Personal team roots become private user folders directly under the site
	root; every other team root moves into "Previous Teams" with its membership
	rewritten as Drive Permission rows, for an admin to reorganise afterwards.
	Nothing is readable without a grant, so private areas need no deny rows —
	only a public team gets an explicit $GENERAL read."""
	root = get_root_folder()
	containers = {get_site_folder().name, get_previous_teams_folder().name, get_users_folder().name}
	previous_teams = get_previous_teams_folder()

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
			_to_shared_folder(previous_teams, home, team)
			if team.public:
				_grant(home, GENERAL_USER, {"read": 1})
		_grant_members(home, members)

	_expand_team_rows()
	_drop_obsolete_revoke_rows()
	_tuck_away_stray_root_children(root, containers)


def _to_user_folder(root, home, team):
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


def _to_shared_folder(root, home, team):
	frappe.db.set_value(
		"File",
		home,
		{
			"folder": root.name,
			"file_name": get_new_file_name(team.title or team.name, root.name),
			"owner": team.owner,
			"is_folder": 1,
			"file_type": "Folder",
			"status": STATUS_ACTIVE,
		},
		update_modified=False,
	)
	grant_owner_access(home, team.owner)


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


def _grant(entity, user, perms):
	if frappe.db.exists("Drive Permission", {"entity": entity, "user": user}):
		return
	frappe.get_doc(
		{"doctype": "Drive Permission", "entity": entity, "user": user, **perms}
	).insert(ignore_permissions=True)


def _expand_team_rows():
	"""team=1 rows granted the row's team (stored in `user`) access to an
	entity; expand them into per-member rows. All-zero team rows were revoke
	attempts, which nothing grants any more — drop them."""
	for row in frappe.get_all("Drive Permission", filters={"team": 1}, fields=["*"]):
		if any(row.get(t) for t in PERMISSION_TYPES):
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


def _drop_obsolete_revoke_rows():
	for row in frappe.get_all("Drive Permission", filters={"user": "", "deny": 0}, fields=["*"]):
		if any(row.get(t) for t in PERMISSION_TYPES):
			continue
		frappe.delete_doc("Drive Permission", row.name, ignore_permissions=True, force=True)


def _tuck_away_stray_root_children(root, containers):
	attachments = frappe.db.exists("File", "Home/Attachments")
	protected = containers | {attachments}

	for f in frappe.get_all(
		"File",
		filters={"folder": root.name, "team": ("is", "not set")},
		fields=["name", "owner"],
	):
		if f.name in protected:
			continue
		target = frappe.db.get_value("Drive Settings", f.owner, "user_folder")
		if not target and frappe.db.exists("User", f.owner):
			target = get_user_folder(f.owner).name
		frappe.db.set_value("File", f.name, "folder", target or attachments, update_modified=False)


def _mirror_storage_to_tree():
	"""`flat` is gone, so every blob has to sit where the folder tree says it does.

	Phase 0 surveys the tree entirely in memory and logs what it would do, so
	quitting during the wait leaves nothing half-done. Phase 1 copies (never
	moves) each blob to its tree position and commits the new file_url only once
	the copy verifies, journalling the original's key. Phase 2 deletes those
	originals, and only runs if phase 1 was flawless — a single failure leaves
	every original in place for a later re-run.
	"""
	manager = FileManager()
	root = get_root_folder()
	plan = frappe._dict(
		manager=manager,
		root_key=storage_key(root.file_url).rstrip("/"),
		actions=[],
		problems=[],
		skipped=Counter(),
		claimed={},
	)
	_survey(plan, root.name, plan.root_key, False, False)

	_announce(plan)
	if not _confirmed():
		print("Drive: quit before any change; storage is untouched and the patch will re-run.")
		return

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

	for child in frappe.get_all(
		"File",
		filters={"folder": parent},
		fields=[
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
		],
	):
		writer = child.content_doctype == WRITER_CONTENT_DOCTYPE
		container = bool(child.is_folder) or writer
		ignored = (
			"link (external url)"
			if child.file_type == "Link"
			else "foreign content doctype (no storage of its own)"
			if child.content_doctype and not writer
			else "framework folder"
			if child.name in FRAMEWORK_FOLDERS
			else None
		)
		if ignored:
			_skip(plan, child, _category(container, writer, embeds), ignored)
			continue

		target = _target_key(parent_key, child.file_name)
		if not target:
			plan.problems.append({"entity": child.name, "reason": f"unusable name {child.file_name!r}"})
			continue

		trashed = in_trash or child.status == STATUS_TRASHED
		placed = _decide(plan, child, target, container, writer, trashed, embeds)
		if container:
			_survey(plan, child.name, placed + "/.embeds" if writer else placed, trashed, writer, depth + 1)


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
				"url": _rewrap(child.file_url, target, container),
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

	excluded = _excluded(child, current, container, embed, plan.root_key)
	if excluded:
		_skip(plan, child, kind, excluded, current)
		return current

	if not container:
		claimant = plan.claimed.get(target)
		if claimant:
			plan.problems.append({"entity": child.name, "reason": f"{target} is also claimed by {claimant}"})
			return current
		plan.claimed[target] = child.name

	if container:
		record("dir")
	elif trashed:
		# the blob sits under .trash; only its restore target moves
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
		return _size(manager, key) if manager.s3_enabled else (manager.site_folder / key).stat().st_size
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


def _confirmed():
	try:
		for left in range(ABORT_WINDOW, 0, -1):
			print(f"\r  Starting relocation in {left:3}s — Ctrl-C to quit ", end="", flush=True)
			time.sleep(1)
		print()
	except KeyboardInterrupt:
		print()
		return False
	return True


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


def _excluded(child, current, container, embed, root_key):
	"""Allowlist: only what Drive itself wrote gets repathed. Framework uploads
	adopted into a user's folder keep their url and privacy — a public one is
	served straight off /files/ by nginx, so relocating it would 404."""
	if not current:
		# flat sites left folders off disk; anything else simply has no blob
		return None if container else "no file_url"
	if current != root_key and not current.startswith(root_key + "/"):
		return "outside the Drive root prefix"
	# team homes predate is_private, so it only disqualifies leaf files
	if not container and not child.is_private:
		return "not private (framework upload)"
	# legacy migrations tag embeds with attached_to_doctype; real attachments
	# belong to their reference document and keep framework semantics
	if child.attached_to_doctype and not embed:
		return "framework attachment"
	return None


def _target_key(parent_key, file_name):
	name = (file_name or "").strip()
	if not name or name in (".", "..") or "/" in name or "\\" in name:
		return None
	key = f"{parent_key}/{name}"
	if len(name.encode()) > MAX_COMPONENT_BYTES or len(key.encode()) > MAX_PATH_BYTES:
		return None
	return key


def _rewrap(old_url, key, container):
	"""Keep the stored url in whatever form this entity already used."""
	if container:
		key += "/"
	old = str(old_url or "")
	if old.startswith(S3_URL_PREFIX):
		return get_s3_url(key)
	if old.startswith("/"):
		return "/" + key
	return key


def _make_dir(manager, key):
	if manager.s3_enabled:
		manager.conn.put_object(Bucket=manager.bucket, Key=key + "/", Body="")
	else:
		(manager.site_folder / key).mkdir(parents=True, exist_ok=True)


def _copy(manager, src, dest):
	if manager.s3_enabled:
		manager.conn.copy_object(
			Bucket=manager.bucket, CopySource={"Bucket": manager.bucket, "Key": src}, Key=dest
		)
		if _size(manager, dest) != _size(manager, src):
			raise OSError(f"copy of {src} did not verify")
	else:
		src_path = manager.site_folder / src
		dest_path = manager.site_folder / dest
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
	return (manager.site_folder / key).exists()


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
				_prune_dir(manager.site_folder / entry["key"])
			else:
				(manager.site_folder / entry["key"]).unlink()
			removed += 1
		except OSError:
			pass

	if not manager.s3_enabled:
		# the flat layout's `embeds/` and friends are left empty behind their files
		leftovers = {str(Path(e["key"]).parent) for e in entries if not e["dir"]}
		for parent in sorted(leftovers - live, key=len, reverse=True):
			try:
				(manager.site_folder / parent).rmdir()
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
