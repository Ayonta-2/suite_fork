import frappe


def execute():
    """One row per (entity, ns, prop_name) — PROPPATCH upserts assume it."""
    if not frappe.db.table_exists("Drive DAV Property"):
        return
    if not frappe.db.sql("""SHOW INDEX FROM `tabDrive DAV Property` WHERE Key_name = 'unique_entity_prop'"""):
        frappe.db.sql_ddl(
            """ALTER TABLE `tabDrive DAV Property`
            ADD UNIQUE INDEX `unique_entity_prop` (`entity`, `ns`(100), `prop_name`)"""
        )
