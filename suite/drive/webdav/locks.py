"""WebDAV write-lock model (RFC 4918 §6-7) and the single enforcement guard.

State lives in the Drive DAV Lock DocType — gunicorn recycles workers and a
Redis flush must not drop a live Office lock mid-edit. Expiry is lazy (purged
before every read) plus an hourly sweep. A lock is satisfied only when its
token is submitted in the If header AND the session user is the lock's owner:
a leaked token grants nothing.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import frappe
from lxml import etree

from suite.drive.utils import get_ancestors_of
from suite.drive.webdav import pathmap
from suite.drive.webdav.context import DavContext
from suite.drive.webdav.errors import BadRequest, Locked, PreconditionFailed
from suite.drive.webdav.ifheader import EMPTY_IF, BadIfHeader, IfHeader, parse_if_header
from suite.drive.webdav.properties import compute_etag
from suite.drive.webdav.xmlutil import _PARSER, dav, dav_element

DEFAULT_LOCK_TIMEOUT = 600
MAX_LOCK_TIMEOUT = 3600
MAX_ACTIVE_LOCKS_PER_USER = 1000

_FIELDS = ["token", "entity", "scope", "depth", "owner_user", "owner_xml", "expires_at", "lock_root"]


@dataclass
class LockInfo:
    token: str
    entity: str
    scope: str  # "Exclusive" | "Shared"
    depth: str  # "0" | "infinity"
    owner_user: str
    owner_xml: str | None
    expires_at: datetime
    lock_root: str

    @property
    def exclusive(self) -> bool:
        return self.scope == "Exclusive"

    @property
    def remaining(self) -> int:
        return max(0, int((self.expires_at - frappe.utils.now_datetime()).total_seconds()))


# --- enforcement (what every mutating handler calls) ---


def enforce(
    ctx: DavContext,
    entity: str | None = None,
    membership_parent: str | None = None,
    check_descendants: bool = False,
) -> None:
    """412 if the If header's conditions fail, then 423 unless every covering
    lock is satisfied by a submitted token from its owner."""
    submitted = parsed_if(ctx)
    if submitted is not EMPTY_IF:
        _conditional_gate(ctx, submitted)

    covering = _coverage(entity, membership_parent, check_descendants)
    if not covering:
        return

    tokens = submitted.all_tokens()

    def satisfied(lock: LockInfo) -> bool:
        return lock.token in tokens and lock.owner_user == ctx.user

    exclusive_blockers = [lock for lock in covering if lock.exclusive and not satisfied(lock)]
    if exclusive_blockers:
        raise Locked("The resource is locked.", lock_root=exclusive_blockers[0].lock_root)

    shared = [lock for lock in covering if not lock.exclusive]
    if shared and not any(satisfied(lock) for lock in shared):
        raise Locked("The resource is locked.", lock_root=shared[0].lock_root)


def parsed_if(ctx: DavContext) -> IfHeader:
    if "ifheader" not in ctx.extras:
        try:
            ctx.extras["ifheader"] = parse_if_header(ctx.request.headers.get("If"))
        except BadIfHeader as e:
            raise BadRequest(str(e)) from e
    return ctx.extras["ifheader"]


def _conditional_gate(ctx: DavContext, submitted: IfHeader) -> None:
    def resolve_href(href: str | None) -> str | None:
        if href is None:
            resolved = pathmap.resolve(ctx.segments, ctx.user)
            return resolved.entity.name if resolved.entity is not None else None
        from urllib.parse import unquote, urlsplit

        path = urlsplit(href).path
        if path != pathmap.DAV_PREFIX and not path.startswith(pathmap.DAV_PREFIX + "/"):
            return None
        segments = [unquote(segment) for segment in path[len(pathmap.DAV_PREFIX) :].split("/") if segment]
        resolved = pathmap.resolve(segments, ctx.user)
        return resolved.entity.name if resolved.entity is not None else None

    def get_etag(entity: str) -> str | None:
        row = pathmap.fetch(entity)
        return compute_etag(row) if row is not None else None

    def get_active_tokens(entity: str) -> frozenset[str]:
        return frozenset(lock.token for lock in covering_locks(entity))

    if not submitted.evaluate(resolve_href, get_etag, get_active_tokens):
        raise PreconditionFailed("If header condition failed.")


def _coverage(
    entity: str | None, membership_parent: str | None, check_descendants: bool
) -> list[LockInfo]:
    locks = _active_locks()
    if not locks:
        return []

    covering: dict[str, LockInfo] = {}

    def add_chain(target: str) -> None:
        ancestors = set(get_ancestors_of(target))
        for lock in locks:
            if lock.entity == target or (lock.entity in ancestors and lock.depth == "infinity"):
                covering[lock.token] = lock

    if entity:
        add_chain(entity)
    if membership_parent:
        # RFC 4918 §7.4: even a depth-0 lock on a collection protects its member list
        add_chain(membership_parent)
    if entity and check_descendants:
        for token in _locks_over_subtree(entity):
            for lock in locks:
                if lock.token == token:
                    covering[lock.token] = lock
    return list(covering.values())


def covering_locks(entity: str) -> list[LockInfo]:
    return _coverage(entity, None, False)


def discovery_map(ancestors_by_entity: dict[str, list[str]]) -> dict[str, list[LockInfo]]:
    """Lockdiscovery for a whole PROPFIND listing from one lock fetch."""
    locks = _active_locks()
    if not locks:
        return {}
    result: dict[str, list[LockInfo]] = {}
    for entity, ancestors in ancestors_by_entity.items():
        ancestor_set = set(ancestors)
        matched = [
            lock
            for lock in locks
            if lock.entity == entity or (lock.entity in ancestor_set and lock.depth == "infinity")
        ]
        if matched:
            result[entity] = matched
    return result


def _locks_over_subtree(subtree_root: str) -> list[str]:
    """Tokens of active locks anywhere under subtree_root — one inverted CTE
    seeded from the (small) lock table, climbing the folder chain upward."""
    rows = frappe.db.sql(
        """WITH RECURSIVE lock_paths AS (
            SELECT l.name AS lock_name, f.name AS node, f.folder
            FROM `tabDrive DAV Lock` l JOIN `tabFile` f ON f.name = l.entity
            WHERE l.expires_at > NOW()
        UNION ALL
            SELECT lp.lock_name, f.name, f.folder
            FROM lock_paths lp JOIN `tabFile` f ON f.name = lp.folder
        )
        SELECT DISTINCT lock_name FROM lock_paths WHERE node = %(root)s""",
        values={"root": subtree_root},
    )
    return [row[0] for row in rows]


# --- lifecycle ---


def create_lock(
    entity: str,
    *,
    scope: str,
    depth: str,
    owner_user: str,
    owner_xml: str | None,
    requested_timeout: int,
    lock_root: str,
) -> LockInfo:
    token = f"urn:uuid:{uuid.uuid4()}"
    frappe.get_doc(
        {
            "doctype": "Drive DAV Lock",
            "token": token,
            "entity": entity,
            "scope": scope,
            "depth": depth,
            "owner_user": owner_user,
            "owner_xml": owner_xml,
            "timeout_seconds": requested_timeout,
            "expires_at": frappe.utils.now_datetime() + timedelta(seconds=requested_timeout),
            "lock_root": lock_root,
        }
    ).insert(ignore_permissions=True)
    return _get(token)


def refresh_lock(token: str, *, requested_timeout: int) -> LockInfo:
    frappe.db.set_value(
        "Drive DAV Lock",
        token,
        {
            "timeout_seconds": requested_timeout,
            "expires_at": frappe.utils.now_datetime() + timedelta(seconds=requested_timeout),
        },
        update_modified=False,
    )
    return _get(token)


def delete_lock(token: str) -> None:
    frappe.db.delete("Drive DAV Lock", {"name": token})


def user_active_lock_count(user: str) -> int:
    """How many unexpired locks this user holds — the per-user creation cap."""
    return frappe.db.count(
        "Drive DAV Lock",
        {"owner_user": user, "expires_at": [">", frappe.utils.now_datetime()]},
    )


def drop_locks_under(entity: str) -> None:
    """DELETE/MOVE cleanup: locks do not survive unmapping or travel (RFC §7.5)."""
    tokens = _locks_over_subtree(entity)
    frappe.db.delete("Drive DAV Lock", {"entity": entity})
    for token in tokens:
        frappe.db.delete("Drive DAV Lock", {"name": token})


def find_lock(token: str) -> LockInfo | None:
    purge_expired_locks(lazy=True)
    row = frappe.db.get_value("Drive DAV Lock", token, _FIELDS, as_dict=True)
    return LockInfo(**row) if row else None


def find_conflicts(entity: str, *, scope: str, depth: str, is_folder: bool) -> list[LockInfo]:
    """LOCK conflict matrix: exclusive conflicts with everything, shared only
    with exclusive. A depth-infinity request on a collection also conflicts
    with any lock inside the subtree."""
    covering = list(covering_locks(entity))
    if is_folder and depth == "infinity":
        tokens = set(_locks_over_subtree(entity))
        known = {lock.token for lock in covering}
        covering += [lock for lock in _active_locks() if lock.token in tokens - known]

    if scope == "Exclusive":
        return covering
    return [lock for lock in covering if lock.exclusive]


def purge_expired_locks(lazy: bool = False) -> None:
    """Hourly scheduler target; also run lazily before every read."""
    threshold = frappe.utils.now_datetime() if lazy else frappe.utils.now_datetime() - timedelta(seconds=60)
    frappe.db.sql("DELETE FROM `tabDrive DAV Lock` WHERE expires_at <= %(cutoff)s", {"cutoff": threshold})


def parse_timeout_header(value: str | None) -> int:
    """First supported entry of the Timeout header, clamped; Office's habitual
    Second-3600 is granted verbatim."""
    if not value:
        return DEFAULT_LOCK_TIMEOUT
    for part in value.split(","):
        part = part.strip()
        if part.lower() == "infinite":
            return MAX_LOCK_TIMEOUT
        if part.lower().startswith("second-"):
            digits = part[len("second-") :]
            if digits.isdigit():
                return max(1, min(int(digits), MAX_LOCK_TIMEOUT))
    return DEFAULT_LOCK_TIMEOUT


# --- XML payloads (shared with PROPFIND) ---


def supportedlock_xml() -> etree._Element:
    supported = dav_element("supportedlock")
    for scope in ("exclusive", "shared"):
        entry = etree.SubElement(supported, dav("lockentry"))
        lockscope = etree.SubElement(entry, dav("lockscope"))
        etree.SubElement(lockscope, dav(scope))
        locktype = etree.SubElement(entry, dav("locktype"))
        etree.SubElement(locktype, dav("write"))
    return supported


def lockdiscovery_xml(locks: list[LockInfo]) -> etree._Element:
    discovery = dav_element("lockdiscovery")
    for lock in locks:
        active = etree.SubElement(discovery, dav("activelock"))
        locktype = etree.SubElement(active, dav("locktype"))
        etree.SubElement(locktype, dav("write"))
        lockscope = etree.SubElement(active, dav("lockscope"))
        etree.SubElement(lockscope, dav(lock.scope.lower()))
        etree.SubElement(active, dav("depth")).text = lock.depth
        if lock.owner_xml:
            try:
                active.append(etree.fromstring(lock.owner_xml.encode("utf-8"), parser=_PARSER))
            except etree.XMLSyntaxError:
                pass
        etree.SubElement(active, dav("timeout")).text = f"Second-{lock.remaining}"
        token = etree.SubElement(active, dav("locktoken"))
        etree.SubElement(token, dav("href")).text = lock.token
        root = etree.SubElement(active, dav("lockroot"))
        etree.SubElement(root, dav("href")).text = lock.lock_root
    return discovery


# --- internals ---


def _active_locks() -> list[LockInfo]:
    # one fetch; the purge DELETE runs only when something actually expired
    rows = frappe.get_all("Drive DAV Lock", fields=_FIELDS)
    now = frappe.utils.now_datetime()
    active = [LockInfo(**row) for row in rows if row.expires_at > now]
    if len(active) != len(rows):
        purge_expired_locks(lazy=True)
    return active


def _get(token: str) -> LockInfo:
    return LockInfo(**frappe.db.get_value("Drive DAV Lock", token, _FIELDS, as_dict=True))
