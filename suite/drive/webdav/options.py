"""OPTIONS responses.

Answered before authentication: the headers are static, and Windows' WebClient
probes OPTIONS before it is willing to send credentials.
"""

import frappe
from werkzeug.wrappers import Request, Response

from suite.drive.webdav import ALLOWED_METHODS, DAV_COMPLIANCE

_ALLOW = ", ".join(ALLOWED_METHODS)


def handle(request: Request) -> Response:
    return Response(
        status=200,
        headers={
            "DAV": DAV_COMPLIANCE,
            "Allow": _ALLOW,
            "MS-Author-Via": "DAV",
            "Content-Length": "0",
            "Cache-Control": "no-cache",
        },
    )


def advertise_on_root() -> None:
    """Windows probes OPTIONS / before mounting /dav — add the DAV headers to
    frappe's stock empty 200 without short-circuiting the request."""
    frappe.local.response_headers["DAV"] = DAV_COMPLIANCE
    frappe.local.response_headers["MS-Author-Via"] = "DAV"
