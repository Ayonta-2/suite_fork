from enum import Enum

import frappe

from suite.storage import destroy_namespace, get_blob_base_path, get_data_base_path
from suite.storage.blob_store import BlobStore
from suite.storage.data_store import DataStore

# Root namespace segment under which all of mail's stores live, e.g. ``mail/<account>``.
# Destroying this segment clears every mail store while leaving other apps' stores intact.
MAIL_NAMESPACE = "mail"


class Entity(Enum):
	"""Defines the different types of entities that can be stored in the DataStore."""

	STATE = "state"

	IDENTITY = "identity"
	MAILBOX = "mailbox"
	EMAIL = "email"

	PARTICIPANT_IDENTITY = "participant_identity"
	CALENDAR = "calendar"
	EVENT = "event"

	ADDRESS_BOOK = "address_book"
	CONTACT_CARD = "contact_card"


def get_account_namespace(account: str) -> tuple[str, str]:
	"""Return the namespace for a JMAP account: ``("mail", <account>)``.

	Each account's data store, blob store and search indexes live at ``mail/<account>`` under
	their respective base paths, so accounts are isolated from one another and from other apps.
	"""

	return (MAIL_NAMESPACE, account)


def get_data_store(account: str) -> DataStore:
	"""Factory function to create a DataStore instance for the given JMAP account ID.

	The store is keyed solely by the account, so every user with access to a shared account
	reads and writes the same cache. LMDB serves concurrent access natively — many lock-free
	readers via MVCC snapshots and a single serialized writer — so multiple users (and worker
	processes) can hit the same account's store safely.
	"""

	return DataStore(base_path=get_data_base_path(), namespace=get_account_namespace(account))


def get_blob_store(account: str) -> BlobStore:
	"""Factory function to create a BlobStore instance for the given JMAP account ID.

	Each account's blobs live in their own directory, so the blob cache is shared across every
	user of an account. Writes are atomic (temp file + ``os.replace``) and reads open the file
	independently, so concurrent access from multiple users/processes is safe.
	"""

	return BlobStore(base_path=get_blob_base_path(), namespace=get_account_namespace(account))


@frappe.whitelist()
def destroy_data_store() -> None:
	"""Delete every mail data store for the current site. System Manager only.

	Removes only the ``mail`` namespace, leaving any other apps' data stores intact.
	"""

	from suite.utils.user import is_system_manager

	if not is_system_manager(frappe.session.user):
		frappe.throw(frappe._("Only System Manager can destroy the data store."))

	destroy_namespace(get_data_base_path(), MAIL_NAMESPACE)


@frappe.whitelist()
def destroy_blob_store() -> None:
	"""Delete every mail blob store for the current site. System Manager only.

	Removes only the ``mail`` namespace, leaving any other apps' blob stores intact.
	"""

	from suite.utils.user import is_system_manager

	if not is_system_manager(frappe.session.user):
		frappe.throw(frappe._("Only System Manager can destroy the blob store."))

	destroy_namespace(get_blob_base_path(), MAIL_NAMESPACE)
