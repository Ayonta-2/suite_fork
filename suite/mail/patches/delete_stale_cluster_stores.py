import frappe

STORE_FIELDS = ["data_store", "blob_store", "search_store", "in_memory_store"]


def execute() -> None:
    """Delete Mail Cluster Store records left over from the legacy schema.

    The DocType was removed and re-introduced with a new schema, so rows created
    under the old schema must not survive model sync. Sites migrating from the
    standalone mail app, however, arrive with live store records that Mail
    Cluster links to (wiping those fails configure_mail_cluster with a
    LinkValidationError), so only rows no cluster references are deleted.
    """

    if not frappe.db.table_exists("Mail Cluster Store"):
        return

    referenced = set()
    if frappe.db.table_exists("Mail Cluster"):
        for field in STORE_FIELDS:
            if frappe.db.has_column("Mail Cluster", field):
                referenced.update(
                    frappe.db.sql_list(
                        f"select distinct `{field}` from `tabMail Cluster` where ifnull(`{field}`, '') != ''"
                    )
                )

    if referenced:
        frappe.db.delete("Mail Cluster Store", {"name": ("not in", list(referenced))})
    else:
        frappe.db.delete("Mail Cluster Store")
