import click
import frappe

# Moved to the Suite Infra app, child tables included.
MOVED_DOCTYPES = (
    "Mail Cluster",
    "Mail Cluster Store",
    "Mail Cluster Store HTTP Auth",
    "Mail Server",
    "Server Deployment",
    "Server Deployment Service",
    "Server Job",
    "Server Job Command",
    "Server Ansible Play",
    "Server Ansible Play Variable",
    "Server Ansible Play Task",
    "DNS Record",
)

# A row in any of these means the site deployed mail servers through Suite.
DATA_DOCTYPES = ("Mail Cluster", "Mail Server", "DNS Record")


def execute() -> None:
    """Releases the mail server deployment DocTypes to the Suite Infra app.

    With Suite Infra installed its own sync has already retagged them, so there is nothing to do.
    Otherwise the DocType records go, so nothing resolves to controllers Suite no longer ships.
    Tables that hold data stay (clusters carry the SSH keys that reach the servers) and are adopted
    as they are when Suite Infra is installed later; empty ones are dropped.
    """

    if "suite_infra" in frappe.get_installed_apps():
        return

    keep_tables = has_deployment_data()

    for doctype in MOVED_DOCTYPES:
        frappe.delete_doc(
            "DocType",
            doctype,
            force=True,
            ignore_permissions=True,
            ignore_missing=True,
            delete_permanently=True,
        )
        if not keep_tables:
            frappe.db.sql_ddl(f"drop table if exists `tab{doctype}`")

    if keep_tables:
        click.secho(
            "Mail server deployment data (clusters, servers, DNS records) was kept for the Suite Infra app. "
            "Install suite_infra on this site to keep managing it.",
            fg="yellow",
        )


def has_deployment_data() -> bool:
    return any(
        frappe.db.table_exists(doctype) and frappe.db.sql(f"select 1 from `tab{doctype}` limit 1")
        for doctype in DATA_DOCTYPES
    )
