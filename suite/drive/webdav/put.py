"""PUT: create a file or overwrite one in place.

Unlike Drive's upload endpoint this never auto-renames — an existing target is
overwritten at the same entity and storage key, which is what Office/Finder
save flows (LOCK → PUT → UNLOCK) require. The body spools through a scratch
file with SHA-256 computed on the way (constant memory under the
streaming_request_paths hook), and `X-OC-Mtime` is honored so rclone's
nextcloud vendor round-trips modification times.
"""

import hashlib
from datetime import datetime
from pathlib import Path

import frappe
import mimemapper
from werkzeug.datastructures import FileStorage
from werkzeug.wrappers import Response

from suite.drive.api.activity import create_new_activity_log
from suite.drive.api.files import get_upload_path
from suite.drive.api.permissions import user_has_permission
from suite.drive.api.storage import acquire_owner_storage_lock, validate_quota
from suite.drive.utils import create_drive_file, get_file_type, update_file_size
from suite.drive.utils.files import get_s3_key, get_s3_url
from suite.drive.webdav import pathmap
from suite.drive.webdav.conditional import evaluate_preconditions
from suite.drive.webdav.context import DavContext
from suite.drive.webdav.errors import BadRequest, Conflict, Forbidden, MethodNotAllowed, quota_guard


def handle(ctx: DavContext) -> Response:
    resolved = pathmap.resolve(ctx.segments, ctx.user)

    if resolved.is_mount or (resolved.root == "virtual"):
        raise MethodNotAllowed("Cannot PUT to a collection.")
    if resolved.missing_intermediate or resolved.root == "unknown":
        raise Conflict("Intermediate collections do not exist.")
    if ctx.request.headers.get("Content-Range"):
        raise BadRequest("Partial PUT is not supported.")

    row = resolved.entity
    if row is not None and row.is_folder:
        raise MethodNotAllowed("Cannot PUT to a collection.")
    if row is None and ctx.had_trailing_slash:
        raise Conflict("Cannot PUT to a collection URL.")

    evaluate_preconditions(ctx.request, row)

    from suite.drive.webdav import locks

    if row is not None:
        locks.enforce(ctx, entity=row.name)
    else:
        locks.enforce(ctx, membership_parent=resolved.parent.name)

    # keep the target's extension on the scratch name — mimemapper detects by it
    from werkzeug.utils import secure_filename

    scratch = get_upload_path(
        f"webdav_{frappe.generate_hash(length=12)}_{secure_filename(ctx.segments[-1])}"
    )
    digest = hashlib.sha256()
    try:
        with scratch.open("wb") as spool:
            for chunk in ctx.body.stream():
                spool.write(chunk)
                digest.update(chunk)
        size = scratch.stat().st_size

        if row is None:
            return _create(ctx, resolved, scratch, size, digest.hexdigest())
        return _overwrite(ctx, row, scratch, size, digest.hexdigest())
    finally:
        scratch.unlink(missing_ok=True)


def _create(ctx: DavContext, resolved, scratch: Path, size: int, sha256: str) -> Response:
    parent = resolved.parent
    name = ctx.segments[-1]

    if not user_has_permission(parent.name, "upload"):
        raise Forbidden("Ask the folder owner for upload access.")
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
        _client_mtime(ctx),
    )
    manager.upload_file(scratch, drive_file, create_thumbnail=True)
    if manager.s3_enabled:
        drive_file.file_url = get_s3_url(get_s3_key(drive_file.file_url))
        drive_file.save()
    drive_file.db_set("content_hash", sha256, update_modified=False)
    _bump_folder_size(parent.name, size)

    return _response(ctx, 201, drive_file.name, sha256)


def _overwrite(ctx: DavContext, row: frappe._dict, scratch: Path, size: int, sha256: str) -> Response:
    if not user_has_permission(row.name, "write"):
        raise Forbidden("You cannot overwrite this file.")
    _run_upload_validators(scratch, row.file_name, row.folder)

    # quota stays with the existing owner — an Office save must not shift
    # ownership or billing to whoever pressed Ctrl+S
    acquire_owner_storage_lock(row.owner)
    delta = size - (row.file_size or 0)
    with quota_guard():
        validate_quota(row.owner, max(0, delta))

    mime_type = _detect_mime(ctx, scratch)
    doc = frappe.get_doc("File", row.name)
    ctx.manager.upload_file(scratch, doc, create_thumbnail=True)
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
    if header and header.strip().isdigit():
        return float(header.strip())
    return None


def _client_mtime_datetime(ctx: DavContext) -> datetime | None:
    stamp = _client_mtime(ctx)
    return datetime.fromtimestamp(stamp) if stamp else None


def _bump_folder_size(folder: str, delta: int) -> None:
    if not delta:
        return
    try:
        update_file_size(folder, delta)
    except Exception:
        # racy rollups, same stance as upload_file (api/files.py)
        pass


def _response(ctx: DavContext, status: int, entity_name: str, sha256: str) -> Response:
    headers = {"ETag": f'"sha256-{sha256}"'}
    if ctx.request.headers.get("X-OC-Mtime"):
        headers["X-OC-Mtime"] = "accepted"
    return Response(status=status, headers=headers)
