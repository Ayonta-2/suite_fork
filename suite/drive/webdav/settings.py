import frappe


def global_webdav_enabled() -> bool:
    return bool(frappe.get_cached_doc("Drive Disk Settings").get("webdav_enabled"))


def user_webdav_enabled(user: str) -> bool:
    # Drive Settings rows are created lazily, so absence means "never opted out"
    value = frappe.db.get_value("Drive Settings", user, "webdav_enabled")
    return True if value is None else bool(value)
