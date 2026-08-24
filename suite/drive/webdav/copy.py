"""COPY — Drive has no copy primitive, so this builds one.

Recursive DFS over the source subtree with per-level batched permission
checks; children the user cannot read are silently skipped (they are equally
invisible to PROPFIND, and a per-href 403 would leak their existence). New
rows are owned by the requester; a single conservative quota pre-check uses
the source's rolled-up size. Blob duplication is server-side on S3. Everything
runs in the request transaction — on storage failure the created blobs are
best-effort removed and the DB insert rolls back with the request.
"""

from pathlib import Path

import frappe
from werkzeug.wrappers import Response

from suite.drive.api.files import toggle_entity_status
from suite.drive.api.permissions import user_has_permission
from suite.drive.api.storage import acquire_owner_storage_lock, validate_quota
from suite.drive.utils import create_drive_file, generate_upward_path, update_file_size
from suite.drive.utils.files import FileManager, get_s3_key, get_s3_url, storage_key
from suite.drive.webdav import pathmap, perms
from suite.drive.webdav.conditional import evaluate_preconditions
from suite.drive.webdav.context import DavContext
from suite.drive.webdav.errors import BadRequest, Forbidden, NotFoundError, quota_guard
from suite.drive.webdav.structure import _resolve_destination


def handle(ctx: DavContext) -> Response:
    source = pathmap.resolve(ctx.segments, ctx.user)
    if source.is_mount or source.root == "virtual":
        raise Forbidden("Cannot copy this collection.")
    if not source.exists:
        raise NotFoundError("Resource not found.")
    if not perms.resolve_entity_access(source.entity, ctx.user)["read"]:
        raise NotFoundError("Resource not found.")

    depth = ctx.depth if ctx.depth is not None else "infinity"
    if source.entity.is_folder and depth == "1":
        raise BadRequest("COPY on a collection accepts Depth 0 or infinity only.")

    destination, dest_parent, dest_name = _resolve_destination(ctx, source)
    evaluate_preconditions(ctx.request, source.entity)

    if not user_has_permission(dest_parent.name, "upload"):
        raise Forbidden("Ask the destination folder owner for upload access.")
    pathmap.validate_dav_name(dest_name, dest_parent)

    from suite.drive.webdav import locks

    locks.enforce(ctx, membership_parent=dest_parent.name)

    overwrote = False
    if destination.entity is not None:
        if not ctx.overwrite:
            from suite.drive.webdav.errors import PreconditionFailed

            raise PreconditionFailed("Destination exists and Overwrite is F.")
        locks.enforce(
            ctx, entity=destination.entity.name, check_descendants=bool(destination.entity.is_folder)
        )
        toggle_entity_status(frappe.get_doc("File", destination.entity.name), ctx.manager, set())
        locks.drop_locks_under(destination.entity.name)
        overwrote = True

    acquire_owner_storage_lock(ctx.user)
    with quota_guard():
        # the rolled-up folder size is an upper bound of what gets copied
        validate_quota(incoming_size=source.entity.file_size or 0)

    copier = _Copier(ctx.manager, ctx.user, recurse=depth != "0")
    try:
        total = copier.copy(source.entity, dest_parent, dest_name)
    except Exception:
        copier.cleanup()
        raise

    try:
        update_file_size(dest_parent.name, total)
    except Exception:
        pass

    return Response(status=204 if overwrote else 201)


class _Copier:
    def __init__(self, manager: FileManager, user: str, recurse: bool):
        self.manager = manager
        self.user = user
        self.recurse = recurse
        self.created_blobs: list[frappe._dict] = []

    def copy(self, node: frappe._dict, new_parent: frappe._dict, new_name: str) -> int:
        if node.is_folder:
            return self._copy_folder(node, new_parent, new_name)
        return self._copy_file(node, new_parent, new_name)

    def _copy_file(self, node: frappe._dict, new_parent: frappe._dict, new_name: str) -> int:
        manager = self.manager
        target = create_drive_file(
            new_name,
            new_parent.name,
            node.file_type,
            lambda file: "/" + str(manager.get_disk_path(file)),
            node.mime_type,
            node.file_size,
            _timestamp(node.modified),
        )
        manager.copy_file(node, target)
        self.created_blobs.append(frappe._dict(name=target.name, file_url=target.file_url))
        if manager.s3_enabled:
            target.file_url = get_s3_url(get_s3_key(target.file_url))
            target.save()
        if node.get("content_hash"):
            target.db_set("content_hash", node.content_hash, update_modified=False)
        self._copy_dead_props(node.name, target.name)
        return node.file_size or 0

    def _copy_folder(self, node: frappe._dict, new_parent: frappe._dict, new_name: str) -> int:
        manager = self.manager
        path = manager.create_folder(
            frappe._dict(file_name=new_name, parent_path=Path(storage_key(new_parent.file_url or "")))
        )
        target = create_drive_file(new_name, new_parent.name, "Folder", path)
        target_row = frappe._dict(name=target.name, file_url=target.file_url, is_folder=1)

        total = 0
        if self.recurse:
            children = pathmap.list_children(node.name)
            if children:
                parent_path = generate_upward_path(node.name, self.user)
                access = perms.resolve_children_access(parent_path, children, self.user)
                for child in children:
                    if not access[child.name]["read"]:
                        continue  # as invisible here as in PROPFIND
                    total += self.copy(child, target_row, child.file_name)

        if total:
            target.db_set("file_size", total, update_modified=False)
        return total

    def _copy_dead_props(self, source_name: str, target_name: str) -> None:
        from suite.drive.webdav import deadprops

        deadprops.copy_props(source_name, target_name)

    def cleanup(self) -> None:
        for blob in self.created_blobs:
            try:
                self.manager.delete_file(blob)
            except Exception:
                pass


def _timestamp(value) -> float | None:
    value = frappe.utils.get_datetime(value) if value else None
    return value.timestamp() if value else None
