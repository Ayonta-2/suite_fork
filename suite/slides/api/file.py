import mimetypes
import os

import frappe
from frappe import _
from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.wrappers import Response


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


def get_reference_presentations(name: str) -> set[str]:
    """Presentations a composite shows; its media is attached to those, not to it."""
    return set(
        frappe.get_all(
            "Reference Presentation",
            filters={"parent": name, "parenttype": "Presentation"},
            pluck="presentation",
            order_by=None,
        )
    )


def get_attached_presentations(src: str, names: set[str] | None = None) -> set[str]:
    """Presentations holding `src`, deduped: one url collects a File row per upload."""
    filters = {"file_url": src, "attached_to_doctype": "Presentation"}
    limit = SCAN_LIMIT
    if names is not None:
        if not names:
            return set()
        filters["attached_to_name"] = ("in", list(names))
        limit = None

    found = set(
        frappe.get_all(
            "File", filters=filters, pluck="attached_to_name", distinct=True, order_by=None, limit=limit
        )
    )

    if limit and len(found) == limit:
        frappe.logger("slides").warning(f"media access check for {src} stopped at {limit}")

    return found


def can_read_any(names: set[str]) -> bool:
    """Whether the caller may read any of `names`. Templates they don't own don't
    count, since everyone can read a template."""
    if not names:
        return False

    user = frappe.session.user
    candidates = {
        row.name
        for row in frappe.get_all(
            "Presentation",
            filters={"name": ("in", list(names))},
            fields=["name", "owner", "is_template"],
            order_by=None,
        )
        if not row.is_template or row.owner == user
    }
    if not candidates:
        return False

    # a hint that skips the loop in the common case, never a decision
    shortlist = frappe.get_list(
        "Presentation", filters={"name": ("in", list(candidates))}, pluck="name", limit=1
    )
    if shortlist and frappe.has_permission("Presentation", "read", shortlist[0]):
        return True

    return any(frappe.has_permission("Presentation", "read", name) for name in candidates)


def validate_media_file(src: str, presentation: str | None = None) -> None:
    if presentation:
        viewed = get_attached_presentations(src, {presentation} | get_reference_presentations(presentation))
        # everyone can read a template, which is what makes viewing one work
        if presentation in viewed and frappe.has_permission("Presentation", "read", presentation):
            return
        if can_read_any(viewed - {presentation}):
            return

    if not frappe.db.exists("File", {"file_url": src}):
        raise NotFound

    if frappe.db.exists("File", {"file_url": src, "is_private": 0}):
        return

    user = frappe.session.user
    if user != "Guest" and frappe.db.exists("File", {"file_url": src, "owner": user}):
        return

    if can_read_any(get_attached_presentations(src)):
        return

    raise Forbidden(_("You don't have permission to access this file"))


@frappe.whitelist(allow_guest=True)
def get_media_file(src: str, public: str | None = None, presentation: str | None = None) -> Response:
    """
    Fetches permitted video file and returns a response.

    `presentation` narrows the lookup, and is the only way a template's media is served.

    `public` is deprecated and ignored; access is determined server-side.
    """
    validate_media_file(src, presentation)

    return get_media_response(src)
