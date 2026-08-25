"""PUT: create a file or overwrite one in place.

Unlike Drive's upload endpoint this never auto-renames — an existing target is
overwritten at the same entity and storage key, which is what Office/Finder
save flows (LOCK → PUT → UNLOCK) require. The body spools through a scratch
file with SHA-256 computed on the way (constant memory under the
streaming_request_paths hook), and `X-OC-Mtime` is honored so rclone's
nextcloud vendor round-trips modification times.
"""

import hashlib
import os
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

    # Stage the byte transfer now, finalize at commit (same discipline as
    # _overwrite): the move is irreversible while every row write rolls back
    # with the transaction, and the dispatcher commits only after this handler
    # returns — placed at the final path any earlier, a failed commit would
    # strand the blob there, unreferenced. Staging before the remaining row
    # writes also keeps their row locks out of the transfer window, so an
    # S3-sized upload never stalls a concurrent PUT's rollup.
    if manager.s3_enabled:
        _stage_s3_swap(manager, blob, scratch, get_s3_key(blob.file_url), undo)
    else:
        _stage_disk_swap(scratch, manager.site_folder / storage_key(blob.file_url), undo, manager, blob)

    if manager.s3_enabled:
        drive_file.file_url = get_s3_url(get_s3_key(blob.file_url))
        drive_file.save()
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
    delta = size - (row.file_size or 0)
    with quota_guard():
        validate_quota(row.owner, max(0, delta))

    mime_type = _detect_mime(ctx, scratch)
    manager = ctx.manager
    doc = frappe.get_doc("File", row.name)

    fields = ("file_size", "mime_type", "file_type", "file_modified", "content_hash", "modified")
    prior = {field: doc.get(field) for field in fields}

    def undo():
        # compensation for a promotion that failed after commit: the bytes
        # never changed, so the metadata and rollup step back to match them
        frappe.db.set_value("File", row.name, prior, update_modified=False)
        apply_file_size_delta(row.folder, -delta)

    # DB writes roll back while byte writes cannot, and the dispatcher commits
    # only after this handler returns — replacing the target here would leave
    # a failed commit serving the new body under the rolled-back size, hash
    # and mtime (wrong GET bodies, stale ETags). So only the fallible byte
    # transfer happens now, into a staging location; the target changes at
    # after_commit through the least fallible primitive available, and any
    # rollback discards the staged bytes without touching the target. Staging
    # before the row writes also keeps their row locks out of the transfer
    # window, so an S3-sized upload never stalls a concurrent PUT's rollup.
    _stage_blob_swap(manager, row, doc, scratch, undo)

    doc.db_set(
        {
            "file_size": size,
            "mime_type": mime_type,
            "file_type": get_file_type(mime_type),
            "file_modified": _client_mtime_datetime(ctx) or frappe.utils.now_datetime(),
            "content_hash": sha256,
        }
    )
    _bump_folder_size(row.folder, delta)

    full_name = frappe.db.get_value("User", ctx.user, "full_name")
    create_new_activity_log(
        entity=row.name,
        activity_type="edit",
        activity_message=f"{full_name} updated {row.file_name} via WebDAV",
    )
    return _response(ctx, 204, row.name, sha256)


def _stage_blob_swap(manager, row: frappe._dict, doc, scratch: Path, undo) -> None:
    if manager.s3_enabled and not stored_on_disk(row.file_url):
        # storage_key, not get_s3_key: an existing row's file_url is the
        # rewritten fetch url, which only storage_key resolves to the object key
        _stage_s3_swap(manager, doc, scratch, storage_key(row.file_url), undo)
    elif manager.s3_enabled:
        # a framework-adopted blob lives on the site disk even under S3; swap
        # it in place — upload_file would write the new body to a stray S3 key
        # that GET (which serves on-disk blobs directly) never reads back. No
        # thumbnail either, matching the native path for adopted blobs.
        _stage_disk_swap(scratch, manager.get_local_path(row.file_url), undo)
    else:
        _stage_disk_swap(scratch, manager.site_folder / storage_key(row.file_url), undo, manager, doc)


def _stage_disk_swap(scratch: Path, target: Path, undo, manager=None, doc=None) -> None:
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
            _compensate_failed_promotion(undo)
            raise
        if manager is not None and manager.can_create_thumbnail(doc):
            frappe.enqueue(manager.upload_thumbnail, now=True, at_front=True, file=doc, file_path=str(target))

    frappe.db.after_commit.add(swap)
    frappe.db.after_rollback.add(lambda: staged.unlink(missing_ok=True))


def _stage_s3_swap(manager, doc, scratch: Path, key: str, undo) -> None:
    """Upload the body to a scratch key now — that is the fallible network
    transfer — and promote it to the real key at commit with a server-side
    managed copy (multipart-sized objects included)."""
    staging_key = f"{key}.{frappe.generate_hash(length=12)}.putpart"
    manager.conn.upload_file(str(scratch), manager.bucket, staging_key)
    thumb_source = None
    if manager.can_create_thumbnail(doc):
        # upload_thumbnail renders from a local file and deletes it when done
        thumb_source = scratch.with_name(scratch.name + ".thumbsrc")
        os.rename(scratch, thumb_source)

    def swap():
        try:
            manager.conn.copy({"Bucket": manager.bucket, "Key": staging_key}, manager.bucket, key)
        except Exception:
            if thumb_source is not None:
                thumb_source.unlink(missing_ok=True)
            _discard_staging_object(manager, staging_key)
            _compensate_failed_promotion(undo)
            raise
        _discard_staging_object(manager, staging_key)
        if thumb_source is not None:
            frappe.enqueue(
                manager.upload_thumbnail, now=True, at_front=True, file=doc, file_path=str(thumb_source)
            )

    def discard():
        if thumb_source is not None:
            thumb_source.unlink(missing_ok=True)
        _discard_staging_object(manager, staging_key)

    frappe.db.after_commit.add(swap)
    frappe.db.after_rollback.add(discard)


def _compensate_failed_promotion(undo) -> None:
    """A promotion fails only after the transaction committed, so the row
    already claims bytes the target never received. Step the metadata back to
    match the unchanged bytes and commit that immediately — the exception this
    failure re-raises makes the framework roll back whatever is uncommitted,
    and the client's 500 prompts a clean retry. Only a second, independent
    failure inside this compensation can leave metadata ahead of bytes; that
    gets the loudest trace available."""
    try:
        undo()
        frappe.db.commit()
    except Exception:
        frappe.log_error("Drive: metadata left ahead of bytes after failed promotion", frappe.get_traceback())


def _discard_staging_object(manager, staging_key: str) -> None:
    try:
        manager.conn.delete_object(Bucket=manager.bucket, Key=staging_key)
    except Exception:
        # a stray scratch object is only clutter; the swap must not fail over it
        frappe.log_error("Drive: could not delete WebDAV staging object", frappe.get_traceback())


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
    if not delta:
        return
    try:
        apply_file_size_delta(folder, delta)
    except Exception:
        # The atomic delta cannot lose a race, so what lands here is real
        # infrastructure trouble — and folder sizes are display metadata
        # (quota sums leaf files directly), never worth failing a finished
        # save over. Log the drift; there is no reconciliation job yet.
        frappe.log_error("Drive: folder size rollup failed", frappe.get_traceback())


def _response(ctx: DavContext, status: int, entity_name: str, sha256: str) -> Response:
    headers = {"ETag": f'"sha256-{sha256[:32]}"'}
    if ctx.request.headers.get("X-OC-Mtime"):
        headers["X-OC-Mtime"] = "accepted"
    return Response(status=status, headers=headers)
