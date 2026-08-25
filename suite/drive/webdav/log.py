"""Request logging for the WebDAV dispatcher.

Off by default; enable per site with drive_webdav_log_level in
site_config.json — "error" (5xx only), "warning" (adds 4xx), "info" (one line
per request) or "debug" (adds the protocol headers that matter when
reproducing client behavior). Lines land in logs/drive_webdav.log at both the
bench and site level. Credentials are never logged: the Authorization header
is deliberately excluded, and lock tokens are capabilities only in the hands
of their owner.
"""

import logging
import time

import frappe
from werkzeug.wrappers import Request, Response

LEVELS = {
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}

# headers worth having when debugging a client; Authorization deliberately absent
DEBUG_HEADERS = (
    "User-Agent",
    "Depth",
    "Destination",
    "Overwrite",
    "If",
    "If-Match",
    "If-None-Match",
    "Lock-Token",
    "Timeout",
    "Range",
    "Content-Type",
    "Content-Length",
    "X-OC-Mtime",
    "Expect",
)


def configured_level() -> int | None:
    raw = str(frappe.conf.get("drive_webdav_log_level") or "").strip().lower()
    return LEVELS.get(raw)


def start_request(request: Request) -> None:
    level = configured_level()
    frappe.local._webdav_log = (
        None if level is None else {"level": level, "start": time.monotonic(), "user": None, "note": None}
    )


def note_user(user: str) -> None:
    if context := getattr(frappe.local, "_webdav_log", None):
        context["user"] = user


def note(reason: str) -> None:
    if context := getattr(frappe.local, "_webdav_log", None):
        context["note"] = reason


def log_response(request: Request, response: Response) -> None:
    context = getattr(frappe.local, "_webdav_log", None)
    if not context:
        return

    logger = frappe.logger("drive_webdav", file_count=10)
    logger.setLevel(context["level"])

    status = response.status_code
    duration_ms = (time.monotonic() - context["start"]) * 1000
    client = (request.user_agent.string or "-")[:120]
    ip = getattr(frappe.local, "request_ip", None) or request.remote_addr or "-"

    line = (
        f"{request.method} {request.path} -> {status} {duration_ms:.1f}ms "
        f'user={context["user"] or "-"} ip={ip} client="{client}"'
    )
    if context["note"]:
        line += f' note="{context["note"]}"'

    level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
    logger.log(level, line)

    if context["level"] <= logging.DEBUG:
        headers = "; ".join(
            f"{name}: {value}" for name in DEBUG_HEADERS if (value := request.headers.get(name))
        )
        if headers:
            logger.debug(f"{request.method} {request.path} headers: {headers}")
