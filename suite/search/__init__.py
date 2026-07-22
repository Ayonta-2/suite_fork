import os

import frappe
from frappe.utils import get_bench_path


def get_search_base_path() -> str:
	"""Base directory holding every Tantivy search index for the current site.

	Sits alongside the site's private files, so it is per-site (multi-tenant safe) and never web-served.
	"""

	return os.path.join(get_bench_path(), "sites", frappe.local.site, "private", "files", "search-index")
