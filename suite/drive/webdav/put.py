"""PUT: create a file or overwrite one in place.

Unlike Drive's upload endpoint this never auto-renames — an existing target is
overwritten at the same entity, which is what Office/Finder save flows
(LOCK → PUT → UNLOCK) require. (Disk targets keep their storage key too; on S3
each PUT writes a fresh generation key that the commit publishes — see
_stage_s3_generation.) The body spools through a scratch
file with SHA-256 computed on the way (constant memory under the
streaming_request_paths hook), and `X-OC-Mtime` is honored so rclone's
nextcloud vendor round-trips modification times.
"""

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import frappe
import mimemapper
from werkzeug.datastructures import FileStorage
from werkzeug.wrappers import Response

from suite.drive.api.activity import create_new_activity_log
from suite.drive.api.files import get_upload_path
from suite.drive.api.permissions import user_has_permission
from suite.drive.api.storage import acquire_owner_storage_lock, get_storage_usage, validate_quota
from suite.drive.utils import apply_file_size_delta, create_drive_file, get_file_type
from suite.drive.utils.files import get_s3_key, get_s3_url, storage_key, stored_on_disk
from suite.drive.webdav import pathmap, perms
from suite.drive.webdav.conditional import evaluate_preconditions
from suite.drive.webdav.context import DavContext
from suite.drive.webdav.errors import (
    BadRequest,
    Conflict,
    Forbidden,
    InsufficientStorage,
    MethodNotAllowed,
    NotFoundError,
    quota_guard,
)
from suite.drive.webdav.properties import to_site_naive

# 9999-12-31 UTC — the largest epoch datetime.fromtimestamp can represent
MAX_MTIME = 253402300799


def handle(ctx: DavContext) -> Response:
    resolved = pathmap.resolve(ctx.segments, ctx.user)

    if resolved.is_mount or (resolved.root == "virtual"):
        raise MethodNotAllowed("Cannot PUT to a collection.")
    if resolved.missing_intermediate or resolved.root == "unknown":
        raise Conflict("Intermediate collections do not exist.")
    if ctx.request.headers.get("Content-Range"):
        raise BadRequest("Partial PUT is not supported.")

    row = resolved.entity

    # Permission gate FIRST — before any existence- or lock-revealing branch
    # (the 405 collection reply, evaluate_preconditions' 412, locks.enforce's
    # 423), so an unreadable target is indistinguishable from an absent one, as
    # on the other write verbs. It also stops an unauthorized/over-quota client
    # forcing a large body to be spooled before rejection (native upload_file
    # checks permission before writing the temp file too). Create paths gate on
    # the parent's access, overwrite on the row's.
    if row is None:
        access = perms.resolve_entity_access(resolved.parent, ctx.user)
        if not (access["read"] or access["upload"]):
            raise NotFoundError("Resource not found.")
        if not access["upload"]:
            raise Forbidden("Ask the folder owner for upload access.")
        if ctx.had_trailing_slash:
            raise Conflict("Cannot PUT to a collection URL.")
        owner, existing = ctx.user, 0
    else:
        if not perms.resolve_entity_access(row, ctx.user)["read"]:
            raise NotFoundError("Resource not found.")
        if row.is_folder:
            raise MethodNotAllowed("Cannot PUT to a collection.")
        if not user_has_permission(row.name, "write"):
            raise Forbidden("You cannot overwrite this file.")
        owner, existing = row.owner, row.file_size or 0

    evaluate_preconditions(ctx.request, row)

    from suite.drive.webdav import locks

    if row is not None:
        locks.enforce(ctx, entity=row.name)
    else:
        locks.enforce(ctx, membership_parent=resolved.parent.name)

    ceiling = _size_ceiling(owner, existing)
    length = ctx.request.content_length
    if ceiling is not None and length and length > ceiling:
        raise InsufficientStorage("Upload exceeds available storage.")

    # keep the target's extension on the scratch name — mimemapper detects by it
    from werkzeug.utils import secure_filename

    scratch = get_upload_path(f"webdav_{frappe.generate_hash(length=12)}_{secure_filename(ctx.segments[-1])}")
    digest = hashlib.sha256()
    try:
        written = 0
        with scratch.open("wb") as spool:
            for chunk in ctx.body.stream():
                written += len(chunk)
                if ceiling is not None and written > ceiling:
                    raise InsufficientStorage("Upload exceeds available storage.")
                spool.write(chunk)
                digest.update(chunk)
        size = scratch.stat().st_size

        if row is None:
            return _create(ctx, resolved, scratch, size, digest.hexdigest())
        return _overwrite(ctx, row, scratch, size, digest.hexdigest())
    finally:
        scratch.unlink(missing_ok=True)


def _size_ceiling(owner: str, existing_size: int) -> int | None:
    """Largest body this PUT may spool to disk, or None when unbounded. Bounds
    the scratch write by the owner's remaining quota (an overwrite reclaims the
    existing blob) and an optional absolute site cap, so a client can never
    spool far past what could ever be stored."""
    ceilings = []
    usage = get_storage_usage(owner)
    if usage["limit"]:
        ceilings.append(max(0, usage["limit"] - usage["total_size"]) + (existing_size or 0))
    hard = frappe.conf.get("drive_webdav_max_upload_size")
    if hard:
        ceilings.append(int(hard))
    return min(ceilings) if ceilings else None


def _create(ctx: DavContext, resolved, scratch: Path, size: int, sha256: str) -> Response:
    parent = resolved.parent
    name = ctx.segments[-1]

    # upload permission was already verified in handle(), before the body spool
    pathmap.validate_dav_name(name, parent)
    _run_upload_validators(scratch, name, parent.name)

    acquire_owner_storage_lock(ctx.user)
    with quota_guard():
        validate_quota(incoming_size=size)

    mime_type = _detect_mime(ctx, scratch)
    manager = ctx.manager
    drive_file = create_drive_file(
        name,
        parent.name,
        get_file_type(mime_type),
        lambda file: "/" + str(manager.get_disk_path(file)),
        mime_type,
        size,
    )
    # the storage form of the url — disk path and S3 key derive from it, and
    # neither can be recovered from the fetch-url rewrite by get_s3_key
    blob = frappe._dict(name=drive_file.name, file_url=drive_file.file_url, mime_type=mime_type)

    def undo():
        # compensation for a promotion that failed after commit: without the
        # bytes the row must not exist, nor its share of the rollup
        frappe.db.delete("File", {"name": drive_file.name})
        apply_file_size_delta(parent.name, -size)

    def repair():
        # read at drift time, after the stamp landed on the row
        return {
            "file": drive_file.name,
            "stamp_hash": drive_file.content_hash,
            "stamp_modified": drive_file.modified,
            "restore": None,
            "folder": parent.name,
            "delta": size,
        }

    # Stage the byte transfer now, publish at commit (same discipline as
    # _overwrite): the transfer is irreversible while every row write rolls
    # back with the transaction, and the dispatcher commits only after this
    # handler returns — placed at the final disk path any earlier, a failed
    # commit would strand the blob there, unreferenced. On S3 the upload goes
    # straight to the generation key the row will point at: unreachable until
    # the commit publishes the row, deleted if the transaction rolls back.
    # Staging before the remaining row writes also keeps their row locks out
    # of the transfer window, so an S3-sized upload never stalls a concurrent
    # PUT's rollup.
    if manager.s3_enabled:
        generation = _stage_s3_generation(manager, blob, scratch, get_s3_key(blob.file_url), replaces=None)
        drive_file.file_url = get_s3_url(generation)
        drive_file.save()
    else:
        _stage_disk_swap(
            scratch,
            manager.site_folder / storage_key(blob.file_url),
            _Compensation(drive_file, undo, repair),
            manager,
            blob,
        )
    stamped = {"content_hash": sha256}
    if (client_mtime := _client_mtime_datetime(ctx)) is not None:
        # not via create_drive_file: its fromtimestamp() reads the epoch in the
        # OS zone, not the site zone the DB convention expects
        stamped["file_modified"] = client_mtime
    drive_file.db_set(stamped, update_modified=False)
    _bump_folder_size(parent.name, size)
    return _response(ctx, 201, drive_file.name, sha256)


def _overwrite(ctx: DavContext, row: frappe._dict, scratch: Path, size: int, sha256: str) -> Response:
    # write permission was already verified in handle(), before the body spool
    _run_upload_validators(scratch, row.file_name, row.folder)

    # quota stays with the existing owner — an Office save must not shift
    # ownership or billing to whoever pressed Ctrl+S
    acquire_owner_storage_lock(row.owner)
    # a locking read, past MVCC: a concurrent PUT that just committed a new
    # generation key (or size) is visible here, so the swap replaces — and
    # later reaps — the key the row actually points at, not a resolve-time
    # snapshot of it
    doc = frappe.get_doc("File", row.name, for_update=True)
    delta = size - (doc.file_size or 0)
    with quota_guard():
        validate_quota(row.owner, max(0, delta))

    mime_type = _detect_mime(ctx, scratch)
    manager = ctx.manager

    full_name = frappe.db.get_value("User", ctx.user, "full_name")
    activity = create_new_activity_log(
        entity=row.name,
        activity_type="edit",
        activity_message=f"{full_name} updated {row.file_name} via WebDAV",
    )

    fields = ("file_size", "mime_type", "file_type", "file_modified", "content_hash", "modified")
    prior = {field: doc.get(field) for field in fields}

    def undo():
        # compensation for a promotion that failed after commit: the bytes
        # never changed, so the metadata and rollup step back to match them
        frappe.db.set_value("File", row.name, prior, update_modified=False)
        apply_file_size_delta(row.folder, -delta)

    def revoke():
        # our own audit row: the edit it announces never took effect, and
        # that stays true when a newer writer supersedes the metadata
        # restore — the newer PUT logs its own row
        if activity.name:
            frappe.db.delete("Drive Entity Activity Log", {"name": activity.name})

    def repair():
        # read at drift time, after the stamp landed on the row
        return {
            "file": row.name,
            "stamp_hash": doc.content_hash,
            "stamp_modified": doc.modified,
            "restore": prior,
            "folder": row.folder,
            "delta": delta,
            "activity": activity.name,
        }

    # DB writes roll back while byte writes cannot, and the dispatcher commits
    # only after this handler returns — replacing the target here would leave
    # a failed commit serving the new body under the rolled-back size, hash
    # and mtime (wrong GET bodies, stale ETags). So only the fallible byte
    # transfer happens now, away from the target: on disk into a staging file
    # the commit renames over the target, on S3 into the generation key the
    # committed row itself will point at. Any rollback discards the staged
    # bytes without touching the target. Staging before the row writes also
    # keeps their row locks out of the transfer window, so an S3-sized upload
    # never stalls a concurrent PUT's rollup.
    new_file_url = _stage_blob_swap(manager, doc, scratch, _Compensation(doc, undo, repair, revoke))

    stamped = {
        "file_size": size,
        "mime_type": mime_type,
        "file_type": get_file_type(mime_type),
        "file_modified": _client_mtime_datetime(ctx) or frappe.utils.now_datetime(),
        "content_hash": sha256,
    }
    if new_file_url is not None:
        stamped["file_url"] = new_file_url
    doc.db_set(stamped)
    _bump_folder_size(row.folder, delta)
    return _response(ctx, 204, row.name, sha256)


def _stage_blob_swap(manager, doc, scratch: Path, compensation: _Compensation) -> str | None:
    """Stage the new bytes for the commit-time swap. Returns the new file_url
    when they land under a new storage key (an S3 generation), or None when
    the target path itself is swapped in place at commit (disk). The
    compensation only reaches the disk swaps — the S3 path has no fallible
    post-commit step, so its edit always takes effect."""
    if manager.s3_enabled and not stored_on_disk(doc.file_url):
        # storage_key, not get_s3_key: an existing row's file_url is the
        # rewritten fetch url, which only storage_key resolves to the object key
        key = storage_key(doc.file_url)
        return get_s3_url(_stage_s3_generation(manager, doc, scratch, key, replaces=key))
    if manager.s3_enabled:
        # a framework-adopted blob lives on the site disk even under S3; swap
        # it in place — upload_file would write the new body to a stray S3 key
        # that GET (which serves on-disk blobs directly) never reads back. No
        # thumbnail either, matching the native path for adopted blobs.
        _stage_disk_swap(scratch, manager.get_local_path(doc.file_url), compensation)
    else:
        _stage_disk_swap(scratch, manager.site_folder / storage_key(doc.file_url), compensation, manager, doc)
    return None


def _stage_disk_swap(
    scratch: Path, target: Path, compensation: _Compensation, manager=None, doc=None
) -> None:
    """Rename the spooled body next to the target now (.uploads shares the
    target's filesystem — the assumption upload_file's rename already makes),
    so the commit-time swap is a bare same-directory os.replace: atomic, and
    the only mutation the old blob ever sees."""
    staged = target.with_name(f"{target.name}.{frappe.generate_hash(length=12)}.putpart")
    os.rename(scratch, staged)

    def swap():
        try:
            os.replace(staged, target)
        except Exception:
            staged.unlink(missing_ok=True)
            compensation.run()
            raise
        if manager is not None and manager.can_create_thumbnail(doc):
            _enqueue_thumbnail(manager, doc, str(target))

    frappe.db.after_commit.add(swap)
    frappe.db.after_rollback.add(lambda: staged.unlink(missing_ok=True))


# one generation suffix per key: [0-9a-f] is generate_hash's alphabet
_GENERATION_SUFFIX = re.compile(r"\.[0-9a-f]{12}\.putgen$")


def _stage_s3_generation(manager, doc, scratch: Path, key: str, replaces: str | None) -> str:
    """Upload the body to a fresh generation key now — the fallible network
    transfer happens entirely inside the transaction — and let the commit that
    publishes the new metadata publish file_url pointing at it in the same
    instant. Copying into a fixed key at after_commit instead left a window as
    long as the S3 copy in which a GET paired the committed size, hash and
    mtime with the previous bytes. The object this PUT replaces turns to
    garbage at commit and is reaped best-effort; a rollback reaps the new
    generation and never touches the old one."""
    # strip the previous PUT's suffix so repeated saves never stack suffixes
    # into an ever-growing key
    generation = f"{_GENERATION_SUFFIX.sub('', key)}.{frappe.generate_hash(length=12)}.putgen"
    manager.conn.upload_file(str(scratch), manager.bucket, generation)
    thumb_source = None
    if manager.can_create_thumbnail(doc):
        # upload_thumbnail renders from a local file and deletes it when done
        thumb_source = scratch.with_name(scratch.name + ".thumbsrc")
        os.rename(scratch, thumb_source)

    def promote():
        # the inequality guards the freak hash collision where reaping the
        # replaced key would reap the bytes just written
        if replaces is not None and replaces != generation:
            _discard_object(manager, replaces)
        if thumb_source is not None:
            _enqueue_thumbnail(manager, doc, str(thumb_source), discard_source=thumb_source)

    def discard():
        if thumb_source is not None:
            thumb_source.unlink(missing_ok=True)
        _discard_object(manager, generation)

    frappe.db.after_commit.add(promote)
    frappe.db.after_rollback.add(discard)
    return generation


def _enqueue_thumbnail(manager, doc, file_path: str, discard_source: Path | None = None) -> None:
    """Thumbnails are cosmetic, and by this point the bytes and metadata are
    committed and promoted — nothing here may fail the response, or the client
    would retry a PUT that already succeeded. upload_thumbnail swallows its own
    failures; this guards the enqueue machinery around it — and the recovery
    itself (an unlink, an Error Log insert) may not escape either."""
    try:
        frappe.enqueue(manager.upload_thumbnail, now=True, at_front=True, file=doc, file_path=file_path)
    except Exception:
        trace = frappe.get_traceback()
        try:
            if discard_source is not None:
                discard_source.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            frappe.log_error("Drive: could not create WebDAV thumbnail", trace)
        except Exception:
            _file_log(f"File {doc.name}: could not create WebDAV thumbnail\n{trace}")


class _Compensation:
    """Steps a committed PUT back when its disk promotion fails: the row
    already claims bytes the target never received, and the exception the
    failure re-raises turns into the client's 500, whose retry heals
    everything anyway.

    undo restores the shared row state (metadata snapshot, rollup delta) and
    is guarded by the stamp check: a writer that slipped in after our commit
    has already replaced metadata, bytes and rollup, computing its delta
    against our committed size — restoring our snapshot over that would
    clobber the newer write and unbalance the accounting chain. The locking
    read in _carries_stamp blocks until such a writer commits, so the choice
    is race-free. revoke retracts only rows this PUT itself created (its
    audit trail) and runs either way: an edit that never took effect must not
    stay recorded, however the row race went. repair builds the same undo as
    a serializable spec for the queued worker retry."""

    def __init__(self, stamped, undo, repair, revoke=None):
        self.stamped = stamped
        self.undo = undo
        self.repair = repair
        self.revoke = revoke

    def run(self) -> None:
        """Two attempts on fresh transactions — a first failure is often a
        deadlock victim or lock timeout. If both fail, the drift is recorded
        durably and the compensation is handed to a background worker, whose
        queue rides Redis rather than the database connection failing here."""
        try:
            self._attempt()
        except Exception:
            try:
                frappe.db.rollback()
                self._attempt()
            except Exception:
                self._record_drift()

    def _attempt(self) -> None:
        if self.revoke is not None:
            self.revoke()
        if _carries_stamp(self.stamped):
            self.undo()
        frappe.db.commit()

    def _record_drift(self) -> None:
        trace = frappe.get_traceback()
        spec = self.repair()
        # the full spec rides every record, so the handoff can degrade but
        # never vanish: even with the database and the queue both down, the
        # last line below replays verbatim once services return, e.g.
        #   bench execute suite.drive.webdav.put.repair_promotion_drift \
        #       --kwargs '<spec>'
        note = "replay with repair_promotion_drift(**spec); spec follows:\n" + json.dumps(spec, default=str)
        # each rung records independently — the file log needs no services,
        # but it sits on the very disk that may have failed the promotion, so
        # it must not gate the database record or the queued repair either
        _file_log(
            f"File {self.stamped.name}: metadata left ahead of bytes after failed promotion\n{trace}\n{note}"
        )
        try:
            frappe.db.rollback()  # clear any aborted transaction so the log row can commit
            frappe.log_error(
                "Drive: metadata left ahead of bytes after failed promotion",
                f"{trace}\n\n{note}",
                reference_doctype="File",
                reference_name=self.stamped.name,
            )
            frappe.db.commit()
        except Exception:
            pass
        try:
            frappe.enqueue(repair_promotion_drift, queue="short", **spec)
        except Exception:
            _file_log(
                f"File {self.stamped.name}: could not queue the drift repair — "
                f"replay the spec recorded above\n{frappe.get_traceback()}"
            )


def _file_log(message: str) -> None:
    """The service-independent rung of the drift record. Even opening the log
    file can fail (the promotion may have failed because this same disk is
    full or read-only) — swallow that so a broken rung never silences the
    healthier ones."""
    try:
        frappe.logger("drive").error(message)
    except Exception:
        pass


def repair_promotion_drift(file, stamp_hash, stamp_modified, restore, folder, delta, activity=None):
    """Deferred compensation, run by a worker on its own connection after the
    in-request attempts failed. Same rules as the inline path: the restore
    and the rollup reversal apply only while the row still carries the failed
    PUT's stamp (a later successful save reconciles everything itself), and
    the audit row comes off regardless. Idempotent — a repeat run finds the
    stamp gone and changes nothing."""
    stamped = frappe._dict(name=file, content_hash=stamp_hash, modified=stamp_modified)
    if _carries_stamp(stamped):
        if restore is None:
            # a failed create: without the bytes the row must not exist
            frappe.db.delete("File", {"name": file})
        else:
            frappe.db.set_value("File", file, restore, update_modified=False)
        apply_file_size_delta(folder, -delta)
    if activity:
        frappe.db.delete("Drive Entity Activity Log", {"name": activity})
    frappe.db.commit()


def _carries_stamp(stamped) -> bool:
    """Whether the committed row still holds exactly what this PUT wrote —
    the content hash plus the modified clock db_set stamped alongside it."""
    current = frappe.db.get_value(
        "File", stamped.name, ["modified", "content_hash"], as_dict=True, for_update=True
    )
    if current is None:
        return False
    same_clock = frappe.utils.get_datetime(current.modified) == frappe.utils.get_datetime(stamped.modified)
    return same_clock and current.content_hash == stamped.content_hash


def _discard_object(manager, key: str) -> None:
    try:
        manager.conn.delete_object(Bucket=manager.bucket, Key=key)
    except Exception:
        # a stray object is only clutter; the PUT's outcome must not fail over
        # it — not even over the Error Log insert recording the leak
        trace = frappe.get_traceback()
        try:
            frappe.log_error("Drive: could not delete WebDAV object", trace)
        except Exception:
            _file_log(f"could not delete WebDAV object {key}\n{trace}")


def _run_upload_validators(scratch: Path, file_name: str, parent: str) -> None:
    checks = frappe.get_hooks("validate_drive_upload")
    if not checks:
        return
    with scratch.open("rb") as stream:
        wrapper = FileStorage(stream=stream, filename=file_name)
        for check in checks:
            result = frappe.call(check, file=wrapper, parent=parent, embed=0)
            if result is not None and result is not True:
                raise Forbidden(str(result) or "This upload was cancelled by a validation check.")


def _detect_mime(ctx: DavContext, scratch: Path) -> str:
    mime_type = mimemapper.get_mime_type(str(scratch), native_first=False)
    if not mime_type or mime_type == "application/octet-stream":
        declared = (ctx.request.headers.get("Content-Type") or "").split(";")[0].strip()
        if declared and declared != "application/octet-stream":
            mime_type = declared
    return mime_type or "application/octet-stream"


def _client_mtime(ctx: DavContext) -> float | None:
    header = ctx.request.headers.get("X-OC-Mtime")
    if header:
        stamp = header.strip()
        # isdigit() alone let a huge value through and overflowed
        # datetime.fromtimestamp; bound it to what a datetime can represent
        if stamp.isdigit() and int(stamp) <= MAX_MTIME:
            return float(stamp)
    return None


def _client_mtime_datetime(ctx: DavContext) -> datetime | None:
    """X-OC-Mtime is a UTC epoch; the DB stores site-local naive datetimes.
    A zoneless fromtimestamp() would read the epoch in the OS zone instead and
    skew every round-trip (rclone re-syncs) whenever the two zones differ."""
    stamp = _client_mtime(ctx)
    if stamp is None:
        return None
    return to_site_naive(datetime.fromtimestamp(stamp, tz=UTC))


def _bump_folder_size(folder: str, delta: int) -> None:
    """A failed rollup fails the PUT. The atomic delta cannot lose a race, so
    failure means the database itself is in trouble — and suppressed, it would
    commit ancestor sizes that no reconciliation repairs. Raising rolls the
    whole transaction back, staged bytes included, for the client to retry."""
    if not delta:
        return
    apply_file_size_delta(folder, delta)


def _response(ctx: DavContext, status: int, entity_name: str, sha256: str) -> Response:
    headers = {"ETag": f'"sha256-{sha256[:32]}"'}
    if ctx.request.headers.get("X-OC-Mtime"):
        headers["X-OC-Mtime"] = "accepted"
    return Response(status=status, headers=headers)
