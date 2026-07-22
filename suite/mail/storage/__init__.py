from enum import Enum

from suite.mail.utils.logger import get_storage_logger
from suite.storage import get_blob_base_path, get_data_base_path
from suite.storage.blob_store import BlobStore
from suite.storage.data_store import DataStore


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


def get_data_store(account: str) -> DataStore:
	"""Factory function to create a DataStore instance for the given JMAP account ID.

	The store is keyed solely by the account ID, so every user with access to a shared
	account reads and writes the same cache. LMDB serves concurrent access natively —
	many lock-free readers via MVCC snapshots and a single serialized writer — so multiple
	users (and worker processes) can hit the same account's store safely.
	"""

	return DataStore(base_path=get_data_base_path(), key=account, logger_factory=get_storage_logger)


def get_blob_store(account: str) -> BlobStore:
	"""Factory function to create a BlobStore instance for the given JMAP account ID.

	Each account's blobs live in their own directory named by the account ID, so the blob
	cache is shared across every user of an account. Writes are atomic (temp file +
	``os.replace``) and reads open the file independently, so concurrent access from multiple
	users/processes is safe.
	"""

	return BlobStore(base_path=get_blob_base_path(), key=account, logger_factory=get_storage_logger)
