import os
import shutil

import frappe
from frappe.utils import get_bench_path

from suite.storage.base_store import Namespace, resolve_namespace_path


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


def destroy_namespace(base_path: str, namespace: Namespace) -> None:
	"""Delete the on-disk directory for `namespace` under `base_path`, if it exists.

	The namespace may be a prefix of the namespaces stores use (e.g. ``"mail"`` removes
	``<base>/mail`` and every ``mail/<account>`` store beneath it).
	"""

	path = resolve_namespace_path(base_path, namespace)
	if os.path.isdir(path):
		shutil.rmtree(path, ignore_errors=True)
