import frappe

from suite.drive.api.permissions import get_teams, user_has_permission
from suite.drive.overrides.file import File, content_query_conditions

READ_PTYPES = frozenset({"read", "report", "export", "email", "print", "select"})


def filter_templates(user):
    if user == "Administrator":
        return ""

    owner_clause = f"`tabWriter Template`.`owner` = {frappe.db.escape(user)}"
    teams = ", ".join(frappe.db.escape(team) for team in get_teams(user))
    if not teams:
        return f"({owner_clause})"
    return f"({owner_clause} or `tabWriter Template`.team in ({teams}))"


def template_has_permission(doc, ptype="read", user=None):
    user = user or frappe.session.user
    if ptype == "create" or user == "Administrator":
        return True
    return doc.get("owner") == user or doc.get("team") in get_teams(user)


def document_query_conditions(user):
    """`permission_query_conditions` for Writer Document — delegate to the
    content SDK so list views can't enumerate documents the caller can't read."""
    return content_query_conditions("Writer Document", user)


def version_has_permission(doc, ptype="read", user=None):
    """A Writer Version is readable/writable iff the backing Drive File of its
    parent document is."""
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    parent = doc.get("doc")
    if not parent:
        return False
    file = File.get_for_doc("Writer Document", parent)
    if not file:
        return False
    return bool(user_has_permission(file, "read" if ptype in READ_PTYPES else "write", user))


def version_query_conditions(user):
    """`permission_query_conditions` for Writer Version — scope rows to versions
    whose parent document the caller can read (owned or directly shared)."""
    if user == "Administrator":
        return ""
    doc_predicate = content_query_conditions("Writer Document", user)
    if not doc_predicate:
        return ""
    return (
        "`tabWriter Version`.doc IN ("
        "SELECT `tabWriter Document`.name FROM `tabWriter Document` "
        f"WHERE {doc_predicate})"
    )
