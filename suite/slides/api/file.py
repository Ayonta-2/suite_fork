import mimetypes
import os

import frappe
from frappe import _
from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.wrappers import Response

from suite.drive.overrides.file import content_has_permission


def get_file_size(file_path: str) -> int:
    """
    Returns the size of the file at the given path.
    """
    return os.path.getsize(file_path)


def get_range(range_header: str, file_size: int) -> tuple[int, int]:
    """
    Extracts the byte range from Range header.
    """
    import re

    range_start, range_end = 0, None
    match = re.search(r"bytes=(\d+)-(\d*)", range_header)

    if match:
        range_start = int(match.group(1))
        if match.group(2):
            range_end = int(match.group(2))

    range_end = range_end or file_size - 1

    return range_start, range_end


def get_file_data(file_path: str, range_start: int = 0, range_end: int = 0) -> bytes:
    """
    Returns specified range of bytes from the file.
    If range_end is None, returns the full file content.
    """
    with open(file_path, "rb") as f:
        f.seek(range_start)

        if range_end == 0:
            # return the full file content in the response
            data = f.read()
        else:
            # read the specified range from the file
            data = f.read(range_end - range_start + 1)

    return data


def get_file_metadata(src: str) -> tuple[str, int, str]:
    """
    Returns file metadata including path, size, and MIME type.
    """
    if src.startswith("/files"):
        src = "/public" + src
    file_path = frappe.get_site_path() + src
    file_size = get_file_size(file_path)
    mimetype = mimetypes.guess_type(file_path)[0] or "video/mp4"

    return file_path, file_size, mimetype


def get_media_response(src: str) -> Response:
    """
    Processes the range header from browser to return valid response.
    """
    file_path, file_size, mimetype = get_file_metadata(src)

    range_header = frappe.request.headers.get("Range", None)
    range_start, range_end = None, None

    # if the request includes a Range header, return a partial content response
    if range_header:
        range_start, range_end = get_range(range_header, file_size)

        file_data = get_file_data(file_path, range_start, range_end)
        status_code = 206  # Partial Content
        content_length = range_end - range_start + 1

    # otherwise, return the full content response
    else:
        file_data = get_file_data(file_path)
        status_code = 200  # Full Content
        content_length = file_size

    response = Response(file_data, status_code, mimetype=mimetype, direct_passthrough=True)
    response.headers["Content-Length"] = str(content_length)
    response.headers["Accept-Ranges"] = "bytes"

    if range_start is not None and range_end is not None:
        response.headers["Content-Range"] = f"bytes {range_start}-{range_end}/{file_size}"
    return response


SCAN_LIMIT = 100


def get_unshared_templates(names: set[str]) -> set[str]:
    """Every user, Guest included, may read a template presentation, so a File row
    attached to one would hand out its url globally. A template that is genuinely
    shared keeps its real Drive grant, which is what gets checked here. Viewing a
    template itself still works, through the `presentation` argument."""
    if not names:
        return set()

    rows = frappe.get_all(
        "Presentation",
        filters={"name": ("in", list(names)), "is_template": 1},
        fields=["name", "owner"],
        order_by=None,
    )

    return {
        row.name
        for row in rows
        if not content_has_permission(
            frappe._dict(doctype="Presentation", name=row.name, owner=row.owner), "read"
        )
    }


def validate_media_file(src: str, presentation: str | None = None) -> None:
    # the presentation being viewed resolves to a single indexed row, so the scan
    # below is left to composite presentations and links made without this argument
    if presentation and frappe.db.exists(
        "File",
        {"file_url": src, "attached_to_doctype": "Presentation", "attached_to_name": presentation},
    ):
        if frappe.has_permission("Presentation", "read", presentation):
            return

    # frappe dedupes file content, so one url can have many File rows attached to
    # different presentations; access is allowed if any one of them is readable
    files = frappe.get_all(
        "File",
        filters={"file_url": src},
        fields=["name", "attached_to_doctype", "attached_to_name"],
        # a widely reused image collects a row per presentation, and guests reach
        # this, so read a bounded slice; the default order would sort the whole
        # set before the limit applies
        order_by=None,
        limit=SCAN_LIMIT,
    )
    if not files:
        raise NotFound

    attached_presentations = {
        file.attached_to_name
        for file in files
        if file.attached_to_doctype == "Presentation" and file.attached_to_name
    }
    templates = get_unshared_templates(attached_presentations)

    # File role perms exclude Guest, so check the attached presentation directly
    for name in attached_presentations - templates:
        if frappe.has_permission("Presentation", "read", name):
            return

    # File permissions fall through to the document a file is attached to, so
    # templates have to stay out of this pass too
    for file in files:
        if file.attached_to_name in templates:
            continue
        if frappe.has_permission("File", "read", file.name):
            return

    if len(files) == SCAN_LIMIT:
        frappe.logger("slides").warning(f"media access check for {src} stopped at {SCAN_LIMIT} rows")

    raise Forbidden(_("You don't have permission to access this file"))


@frappe.whitelist(allow_guest=True)
def get_media_file(src: str, public: str | None = None, presentation: str | None = None) -> Response:
    """
    Fetches permitted video file and returns a response.

    `presentation` is the presentation being viewed; it only narrows the lookup,
    access is granted the same way with or without it.

    `public` is deprecated and ignored; access is determined server-side.
    """
    validate_media_file(src, presentation)

    return get_media_response(src)
