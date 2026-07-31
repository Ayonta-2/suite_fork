# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from suite.drive.api.notifications import notify_share


class DrivePermission(Document):
    def after_insert(self):
        # `notify_share` runs inline and emails per row; a migration rewriting
        # historical grants would mail everyone about folders they already had.
        if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch:
            return
        if self.user:
            frappe.enqueue(
                notify_share,
                queue="short",
                job_id=f"fdocperm_{self.name}",
                deduplicate=True,
                timeout=None,
                now=True,
                at_front=False,
                entity_name=self.entity,
                docperm_name=self.name,
            )
