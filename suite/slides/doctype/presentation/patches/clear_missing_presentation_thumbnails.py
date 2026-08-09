import os

import frappe
from frappe.utils import get_files_path

PRIVATE_PREFIX = "/private/files/"
PUBLIC_PREFIX = "/files/"


def get_disk_path(file_url: str) -> str | None:
    """Resolve a framework file URL to its path on disk, mirroring File.get_full_path()."""
    if file_url.startswith(PRIVATE_PREFIX):
        return get_files_path(*file_url[len(PRIVATE_PREFIX) :].split("/"), is_private=1)
    if file_url.startswith(PUBLIC_PREFIX):
        return get_files_path(*file_url[len(PUBLIC_PREFIX) :].split("/"))
    return None


def is_dangling(file_url: str) -> bool:
    """Nothing can serve this URL any more.

    A File row of any kind means some storage backend still owns the blob, and the
    attach hook only rebuilds a thumbnail it cannot find a File for — so a surviving
    row is reason enough to leave the field alone. Only once no row is left does the
    on-disk check decide, and by then the URL can only be a local framework blob:
    Drive rewrites S3-backed files to the `suite.drive.api.s3.fetch` prefix, which
    get_disk_path() does not resolve.
    """
    if frappe.db.exists("File", {"file_url": file_url}):
        return False

    disk_path = get_disk_path(file_url)
    return bool(disk_path) and not os.path.exists(disk_path)


def execute():
    """Clear deck thumbnails whose blob is gone.

    cleanup_unused_thumbnail_files decided what was unused by scanning Slide rows only,
    so thumbnails that move_slide_thumbnail_to_presentation had already lifted onto
    Presentation.thumbnail were deleted with the field still pointing at them. The
    framework's attach hook then retries the missing blob on every save of those decks
    and logs "Error Attaching File" each time.
    """
    presentations = frappe.get_all(
        "Presentation",
        filters={"thumbnail": ["like", "/%files/%"]},
        fields=["name", "thumbnail"],
    )

    for presentation in presentations:
        if not is_dangling(presentation.thumbnail):
            continue

        frappe.db.set_value(
            "Presentation",
            presentation.name,
            "thumbnail",
            "",
            update_modified=False,
        )
