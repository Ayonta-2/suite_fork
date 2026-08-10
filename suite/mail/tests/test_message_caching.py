# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
"""``_cache_messages``'s contract with the address index: a message is indexed the once, when the
cache first takes it, and only stays cached if that indexing got through — so a failure costs a
re-fetch rather than leaving the people on that message out of suggestions for good."""

import unittest
from unittest import mock

from suite.mail.doctype.mail_message import mail_message
from suite.mail.store import Entity


class CacheMessages(unittest.TestCase):
    """``_cache_messages`` — index what the cache had never held, and keep only what indexed."""

    def cache(self, messages, new_ids=None, index_error=None, rollback_error=None):
        """Cache `messages`; returns the store, the index and the error log, all mocked."""

        store = mock.Mock()
        # Whatever the store reports as new is what the batch is judged by.
        store.set_many.return_value = set(messages) if new_ids is None else new_ids
        store.delete_many.side_effect = rollback_error

        index = mock.Mock()
        index.index_addresses.side_effect = index_error

        with (
            mock.patch.object(mail_message, "get_data_store", return_value=store),
            mock.patch.object(mail_message, "get_email_address_index", return_value=index),
            mock.patch.object(mail_message, "log_mail_error") as log_error,
        ):
            mail_message._cache_messages("account", messages)

        return store, index, log_error

    def message(self, id, email):
        return {"id": id, "from_name": "Jane Doe", "from_email": email, "recipients": []}

    def test_a_new_message_has_its_addresses_indexed(self):
        message = self.message("m1", "jane@example.com")
        _store, index, _log = self.cache({"m1": message})

        addresses = index.index_addresses.call_args.args[0]
        self.assertEqual(addresses, [{"name": "Jane Doe", "email": "jane@example.com"}])

    def test_a_message_the_cache_already_held_is_not_indexed_again(self):
        # The re-cache a flag change causes: counting it would score sync churn as correspondence.
        _store, index, _log = self.cache({"m1": self.message("m1", "jane@example.com")}, new_ids=set())

        index.index_addresses.assert_not_called()

    def test_only_the_new_messages_of_a_mixed_batch_are_indexed(self):
        messages = {
            "m1": self.message("m1", "jane@example.com"),
            "m2": self.message("m2", "john@example.com"),
        }
        _store, index, _log = self.cache(messages, new_ids={"m2"})

        addresses = index.index_addresses.call_args.args[0]
        self.assertEqual([address["email"] for address in addresses], ["john@example.com"])

    def test_a_message_that_indexed_stays_cached(self):
        _store, _index, _log = self.cache({"m1": self.message("m1", "jane@example.com")})

        _store.delete_many.assert_not_called()

    def test_a_message_that_failed_to_index_is_uncached(self):
        # Being cached is what marks a message indexed. Left cached, it would never be offered as
        # new again and jane@example.com would be missing from suggestions until a manual rebuild.
        store, _index, log_error = self.cache(
            {"m1": self.message("m1", "jane@example.com")}, index_error=RuntimeError("index is down")
        )

        store.delete_many.assert_called_once_with(Entity.EMAIL, keys=["m1"])
        log_error.assert_called_once()

    def test_only_the_messages_that_went_unindexed_are_uncached(self):
        messages = {
            "m1": self.message("m1", "jane@example.com"),
            "m2": self.message("m2", "john@example.com"),
        }
        store, _index, _log = self.cache(messages, new_ids={"m2"}, index_error=RuntimeError("boom"))

        store.delete_many.assert_called_once_with(Entity.EMAIL, keys=["m2"])

    def test_indexing_failure_never_reaches_the_caller(self):
        # Caching is the caller's business; a search index that is down is not their problem.
        _store, _index, log_error = self.cache(
            {"m1": self.message("m1", "jane@example.com")}, index_error=RuntimeError("boom")
        )

        log_error.assert_called_once()

    def test_a_rollback_that_fails_is_swallowed_too(self):
        # Same reason: whatever the store does here, caching must not raise at the caller.
        _store, _index, log_error = self.cache(
            {"m1": self.message("m1", "jane@example.com")},
            index_error=RuntimeError("boom"),
            rollback_error=RuntimeError("store is down"),
        )

        log_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
