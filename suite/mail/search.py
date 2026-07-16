import re

import frappe
from frappe import _
from frappe.utils import create_batch

from suite.search.base_index import BaseIndex, FieldSpec
from suite.utils import enqueue_job

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

# Cached records processed per index write while rebuilding, bounding memory and commit size.
_REBUILD_BATCH_SIZE = 500

# Accounts rebuilt per long-queue job when rebuilding every account's index.
_ACCOUNTS_PER_REBUILD_BATCH = 25


class EmailAddressIndex(BaseIndex):
	"""Shared, per-account index of email addresses for recipient suggestions.

	Sources (cached messages, contact cards, ...) feed in plain {name, email} dicts, so the index
	knows nothing about where an address came from. Each document is keyed by the lowercased
	address, so re-indexing the same address from any source is an upsert and addresses stay unique
	by construction. The index is cumulative: entries are only added or updated, never removed when
	a source is evicted, so it doubles as an address book of everyone the user has corresponded with.
	"""

	ENTITY = "email_address"
	FIELDS = (
		# Lowercased address; the unique document key, so the same address upserts across sources.
		FieldSpec("id", stored=True, tokenizer="raw"),
		# Original-cased address and display name, returned verbatim in suggestions.
		FieldSpec("email", stored=True, tokenizer="raw"),
		FieldSpec("name", stored=True, tokenizer="raw"),
		# "name email" blob, tokenized so a query can match either part.
		FieldSpec("text"),
	)
	DEFAULT_SEARCH_FIELDS = ("text",)

	def to_document(self, address: dict) -> dict:
		email = (address.get("email") or "").strip()
		name = (address.get("name") or "").strip() or None

		return {
			"id": email.lower(),
			"email": email,
			"name": name,
			"text": " ".join(filter(None, (name, email))),
		}

	def index_addresses(self, addresses: list[dict]) -> int:
		"""Upsert the given {name, email} dicts; skips entries without an email and dedupes the batch."""

		unique = {}
		for address in addresses:
			if email := (address.get("email") or "").strip():
				unique[email.lower()] = address

		return self.index_documents(list(unique.values()))

	def search_email_addresses(self, query: str, limit: int = 10) -> list[dict]:
		"""Return up to `limit` {name, email} addresses matching `query`, most relevant first.

		The query's tokens must appear as a consecutive, in-order phrase in the address's name or
		email, with the last token matched as a prefix. So "saga" matches "sagar", and "sagar.s"
		matches "sagar.s@…" / "Sagar Sharma" but not "sagar@…" or "sagar.v@…". Documents are unique
		per address, so the hits need no further deduping.
		"""

		tokens = _TOKEN_PATTERN.findall(query.lower()) if query else []
		if not tokens:
			return []

		hits, _total_count = self.search_phrase_prefix(tokens, limit=limit)
		return [{"name": hit.get("name"), "email": hit.get("email")} for hit in hits]


def get_email_address_index(account: str) -> EmailAddressIndex:
	"""Get the EmailAddressIndex for the given JMAP account ID."""

	return EmailAddressIndex(account)


def rebuild_email_address_index(account: str, in_background: bool = True) -> None:
	"""Rebuild an account's email-address index from scratch.

	Drops the existing index, then re-indexes every cached mail message and contact card in
	batches (bounding memory and the size of each index commit). Runs in a background job by
	default; pass `in_background=False` to run inline (e.g. from within the job itself).
	"""

	if in_background:
		enqueue_job(
			rebuild_email_address_index,
			job_id=f"rebuild-email-address-index::{account}",
			deduplicate=True,
			queue="long",
			timeout=3600,
			account=account,
			in_background=False,
		)
		return

	# Imported lazily: these modules import this one, so a top-level import would be circular.
	from suite.mail.doctype.contact_card.contact_card import _contact_addresses
	from suite.mail.doctype.mail_message.mail_message import _message_addresses
	from suite.mail.storage import get_data_store
	from suite.mail.storage.data_store import Entity

	# Drop the stale index, then take a fresh handle so its directory is recreated before writing.
	get_email_address_index(account).drop()
	index = get_email_address_index(account)

	store = get_data_store(account)

	messages = list(store.scan(Entity.EMAIL).values())
	for batch in create_batch(messages, _REBUILD_BATCH_SIZE):
		index.index_addresses(_message_addresses(batch))

	contact_cards = list(store.scan(Entity.CONTACT_CARD).values())
	for batch in create_batch(contact_cards, _REBUILD_BATCH_SIZE):
		index.index_addresses(_contact_addresses(batch))


def rebuild_all_email_address_indexes() -> None:
	"""Rebuild the email-address index for every account of a JMAP-configured, enabled user.

	Fans the accounts out into long-queue background jobs of `_ACCOUNTS_PER_REBUILD_BATCH` each;
	every job rebuilds its accounts inline. Safe to run from a scheduler or the console.
	"""

	accounts = frappe.db.get_all("JMAP Account", {}, pluck="name")
	for i, batch in enumerate(create_batch(accounts, _ACCOUNTS_PER_REBUILD_BATCH)):
		enqueue_job(
			_rebuild_email_address_indexes,
			job_id=f"rebuild-email-address-indexes::{i}",
			deduplicate=True,
			queue="long",
			timeout=3600,
			accounts=batch,
		)


def _rebuild_email_address_indexes(accounts: list[str]) -> None:
	"""Rebuild each account's email-address index inline, isolating per-account failures."""

	from suite.mail.utils import log_mail_error

	for account in accounts:
		try:
			rebuild_email_address_index(account, in_background=False)
		except Exception:
			log_mail_error(
				_("Failed to rebuild email address index for account {0}").format(account),
				frappe.get_traceback(with_context=True),
			)
