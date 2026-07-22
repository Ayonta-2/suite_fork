# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import os

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.types.filter import FilterTuple
from frappe.utils import cint, now

from suite.storage import get_blob_base_path, get_data_base_path, list_namespaces
from suite.storage.base_store import resolve_namespace_path
from suite.storage.blob_store import BlobStore
from suite.storage.data_store import DataStore

DATA_STORE = "Data Store"
BLOB_STORE = "Blob Store"

# Cap the rendered value so browsing a huge cached record doesn't ship megabytes to the client.
_VALUE_PREVIEW_LIMIT = 20_000


class StoreEntry(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		entity: DF.Data | None
		key: DF.Data | None
		namespace: DF.Data
		size: DF.Data | None
		store: DF.Literal["Data Store", "Blob Store"]
		value: DF.Code | None
	# end: auto-generated types

	def load_from_db(self) -> None:
		store, namespace, key_part = _parse_name(self.name)

		if store == DATA_STORE:
			entity, _sep, key = key_part.partition(":")
			entry = _data_store(namespace).read(entity, key)
			if entry is None:
				frappe.throw(_("Store entry {0} not found.").format(frappe.bold(self.name)))

			record = _row(store, namespace, entity, key, entry["size"], value=_pretty(entry["value"]))
		else:
			blob = _blob_store(namespace).get(key_part)
			if blob is None:
				frappe.throw(_("Store entry {0} not found.").format(frappe.bold(self.name)))

			record = _row(store, namespace, None, key_part, len(blob), value=_blob_preview(blob))

		super(Document, self).__init__(record)

	# Store Entry is a read-only browser; block all writes.
	def db_insert(self, *args, **kwargs) -> None:
		frappe.throw(_("Store Entry is read-only."))

	def db_update(self, *args, **kwargs) -> None:
		frappe.throw(_("Store Entry is read-only."))

	def delete(self, *args, **kwargs) -> None:
		frappe.throw(_("Store Entry is read-only."))

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list[dict]:
		store = _filter_value(filters, "store") or DATA_STORE
		namespace = _filter_value(filters, "namespace")

		if not namespace:
			available = ["/".join(ns) for ns in list_namespaces(_base_path(store))]
			hint = ", ".join(available) if available else _("none")
			frappe.msgprint(_("Select a namespace to browse. Available: {0}").format(hint), alert=True)
			return []

		if not _namespace_exists(store, namespace):
			frappe.msgprint(_("No {0} found for namespace {1}.").format(store.lower(), namespace), alert=True)
			return []

		rows = _entries(store, namespace, entity=_filter_value(filters, "entity"))

		start = cint(kwargs.get("limit_start"))
		length = cint(kwargs.get("limit_page_length") or page_length) or len(rows)
		return rows[start : start + length]

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		store = _filter_value(filters, "store") or DATA_STORE
		namespace = _filter_value(filters, "namespace")

		if not namespace or not _namespace_exists(store, namespace):
			return 0

		return len(_entries(store, namespace, entity=_filter_value(filters, "entity")))

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}


def _filter_value(filters, fieldname: str):
	"""Return the value a list-view filter sets for `fieldname`.

	Handles both a plain ``{field: value}`` dict and a list of filter conditions, and unwraps a
	``like`` value's surrounding ``%`` so a Data standard filter (which defaults to ``like``)
	still yields the exact value callers expect.
	"""

	if isinstance(filters, dict):
		return filters.get(fieldname)

	for condition in filters or []:
		tup = condition if isinstance(condition, FilterTuple) else FilterTuple(condition)
		if tup.fieldname != fieldname:
			continue

		value = tup.value
		if isinstance(value, str) and tup.operator in ("like", "not like"):
			value = value.strip("%")
		return value

	return None


def _base_path(store: str) -> str:
	"""Return the base directory for the given store."""

	return get_data_base_path() if store == DATA_STORE else get_blob_base_path()


def _data_store(namespace: str) -> DataStore:
	return DataStore(base_path=get_data_base_path(), namespace=namespace)


def _blob_store(namespace: str) -> BlobStore:
	return BlobStore(base_path=get_blob_base_path(), namespace=namespace)


def _namespace_exists(store: str, namespace: str) -> bool:
	"""Return True when the namespace directory exists (so browsing never creates empty stores)."""

	return os.path.isdir(resolve_namespace_path(_base_path(store), namespace))


def _entries(store: str, namespace: str, entity: str | None = None) -> list[dict]:
	"""Return the browsable rows for a namespace, sorted by entity then key."""

	if store == DATA_STORE:
		rows = [
			_row(store, namespace, item["entity"], item["key"], item["size"])
			for item in _data_store(namespace).browse()
			if not entity or item["entity"] == entity
		]
	else:
		rows = [
			_row(store, namespace, None, item["key"], item["size"])
			for item in _blob_store(namespace).browse()
		]

	rows.sort(key=lambda row: (row.get("entity") or "", row["key"]))
	return rows


def _row(
	store: str,
	namespace: str,
	entity: str | None,
	key: str,
	size: int,
	value: str | None = None,
) -> dict:
	"""Build a Store Entry record dict for either store."""

	key_part = f"{entity}:{key}" if store == DATA_STORE else key
	stamp = now()

	return {
		"name": _make_name(store, namespace, key_part),
		"store": store,
		"namespace": namespace,
		"entity": entity,
		"key": key,
		"size": size,
		"value": value,
		"creation": stamp,
		"modified": stamp,
	}


def _make_name(store: str, namespace: str, key_part: str) -> str:
	"""Encode a stable, parseable record name: ``<data|blob>|<namespace>|<key_part>``."""

	return f"{'data' if store == DATA_STORE else 'blob'}|{namespace}|{key_part}"


def _parse_name(name: str) -> tuple[str, str, str]:
	"""Split a record name back into (store, namespace, key_part)."""

	code, namespace, key_part = name.split("|", 2)
	return (DATA_STORE if code == "data" else BLOB_STORE), namespace, key_part


def _pretty(value) -> str:
	"""Render a deserialized data-store value as pretty JSON, truncated for display."""

	text = json.dumps(value, indent=2, ensure_ascii=False, default=str)
	return _truncate(text)


def _blob_preview(blob: bytes) -> str:
	"""Render a blob as text when it decodes as UTF-8, otherwise note its binary size."""

	try:
		return _truncate(blob.decode("utf-8"))
	except UnicodeDecodeError:
		return _("<binary blob: {0} bytes>").format(len(blob))


def _truncate(text: str) -> str:
	"""Clip an overly long value preview so the browser stays responsive."""

	if len(text) > _VALUE_PREVIEW_LIMIT:
		return text[:_VALUE_PREVIEW_LIMIT] + "\n… (truncated)"

	return text
