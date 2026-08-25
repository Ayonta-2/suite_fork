import frappe


def global_webdav_enabled() -> bool:
    return bool(frappe.get_cached_doc("Drive Disk Settings").get("webdav_enabled"))


def user_webdav_enabled(user: str) -> bool:
    # opt-in: only an explicit enable grants access, so a lazily-missing
    # Drive Settings row reads as disabled
    return bool(frappe.db.get_value("Drive Settings", user, "webdav_enabled"))
