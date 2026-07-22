import os
import shutil

import frappe
from frappe.utils import get_bench_path


def get_data_base_path() -> str:
	"""Base directory holding every LMDB data-store environment for the current site.

	Sits alongside the site's private files, so it is per-site (multi-tenant safe) and never web-served.
	"""

	return os.path.join(get_bench_path(), "sites", frappe.local.site, "private", "files", "data-store")


def get_blob_base_path() -> str:
	"""Base directory holding every blob store for the current site.

	Sits alongside the site's private files, so it is per-site (multi-tenant safe) and never web-served.
	"""

	return os.path.join(get_bench_path(), "sites", frappe.local.site, "private", "files", "blob-store")


@frappe.whitelist()
def destroy_data_store() -> None:
	"""Delete every data store for the current site. System Manager only."""

	from suite.utils.user import is_system_manager

	if not is_system_manager(frappe.session.user):
		frappe.throw(frappe._("Only System Manager can destroy the data store."))

	base_path = get_data_base_path()
	if os.path.exists(base_path):
		shutil.rmtree(base_path)


@frappe.whitelist()
def destroy_blob_store() -> None:
	"""Delete every blob store for the current site. System Manager only."""

	from suite.utils.user import is_system_manager

	if not is_system_manager(frappe.session.user):
		frappe.throw(frappe._("Only System Manager can destroy the blob store."))

	base_path = get_blob_base_path()
	if os.path.exists(base_path):
		shutil.rmtree(base_path)
