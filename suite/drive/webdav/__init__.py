# WebDAV server for Frappe Drive (RFC 4918 Class 1, 2, 3).
# Keep this module import-light: the dispatcher's before_request hook runs on
# every request, and non-/dav traffic must not pay for the protocol engine.

DAV_PREFIX = "/dav"
DAV_COMPLIANCE = "1, 2, 3"

ALLOWED_METHODS = (
    "OPTIONS",
    "GET",
    "HEAD",
    "PUT",
    "DELETE",
    "PROPFIND",
    "PROPPATCH",
    "MKCOL",
    "COPY",
    "MOVE",
    "LOCK",
    "UNLOCK",
)
