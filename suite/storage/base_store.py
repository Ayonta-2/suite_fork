import os
from collections.abc import Callable
from threading import RLock
from typing import Any, ClassVar

import frappe
from frappe.utils import random_string


class _DefaultLogger:
	"""Minimal structured logger used when no `logger_factory` is injected.

	Matches the interface the stores call (each level takes an event name plus optional
	fields, and tolerates a pre-built dict as the event) and emits one record per event to
	the ``suite.storage`` frappe logger. Callers that want configurable levels/rotation
	(e.g. mail) inject their own logger via `logger_factory` instead.
	"""

	def __init__(self, ctx: dict) -> None:
		self.ctx = ctx
		self.logger = frappe.logger("suite.storage", allow_site=True)

	def _record(self, event: Any, fields: dict) -> dict:
		if isinstance(event, dict):
			return {**self.ctx, **event}
		return {**self.ctx, **fields, "event": event}

	def debug(self, event: Any, **fields: Any) -> None:
		self.logger.debug(self._record(event, fields))

	def info(self, event: Any, **fields: Any) -> None:
		self.logger.info(self._record(event, fields))

	def warning(self, event: Any, **fields: Any) -> None:
		self.logger.warning(self._record(event, fields))

	def error(self, event: Any, **fields: Any) -> None:
		self.logger.error(self._record(event, fields))

	def exception(self, event: Any, **fields: Any) -> None:
		self.logger.exception(self._record(event, fields))


class BaseStore:
	SEPARATOR: ClassVar[str] = ":"
	_PROCESS_LOCKS: ClassVar[dict[str, RLock]] = {}
	_PROCESS_LOCKS_GUARD: ClassVar[RLock] = RLock()

	def __init__(
		self,
		base_path: str,
		key: str,
		logger_factory: Callable[[dict], Any] | None = None,
	) -> None:
		"""Initialize the storage with the base path and key.

		`logger_factory` is called with this store's context dict (bound by reference, so
		subclasses can keep adding fields to `self.logger_context`) and must return a logger
		exposing debug/info/warning/error/exception. When omitted, a minimal logger writing
		to the ``suite.storage`` frappe channel is used.
		"""

		self.base_path = base_path
		self.key = key

		self.logger_context = {"req_id": random_string(10), "key": self.key}
		self.logger = (logger_factory or _DefaultLogger)(self.logger_context)

		self.path = self._get_storage_path()
		os.makedirs(self.path, exist_ok=True)

		self._prefix = f"{self.key}{self.SEPARATOR}"

	def _get_storage_path(self) -> str:
		"""Return the storage path for this store; subclasses scope it per key."""

		return self.base_path

	def _get_process_lock(self, path: str | None = None) -> RLock:
		"""Return a process-local lock shared by all storage instances for the same path."""

		path = path or self.path

		self.logger.debug("acquiring-rlock", path=path)

		with self._PROCESS_LOCKS_GUARD:
			lock = self._PROCESS_LOCKS.get(path)
			if lock is None:
				lock = RLock()
				self._PROCESS_LOCKS[path] = lock

			self.logger.debug("rlock-acquired", path=path)
			return lock

	def _get_prefix(self) -> str:
		"""Return the prefix for keys in this storage instance."""

		return self._prefix

	def _make_key(self, subkey: str) -> str:
		"""Construct the full key with prefix for storage."""

		return f"{self._get_prefix()}{subkey}"

	def _normalize_scan_key(self, key: str) -> str:
		"""Normalize a key returned from a scan by removing the prefix."""

		return key.removeprefix(self._get_prefix())
