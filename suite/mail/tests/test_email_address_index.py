# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
"""The email-address index's normalization contract: display names lose the quotes clients wrap
them in, and only syntactically valid addresses ever reach the index."""

import unittest
from unittest import mock

from suite.mail.store.indexes.email_address import EmailAddressIndex, _sanitize_name


class SanitizeName(unittest.TestCase):
    """``_sanitize_name`` — strip wrapping quote pairs, leave everything else alone."""

    def test_single_quote_pair_is_stripped(self):
        self.assertEqual(_sanitize_name("'Jane Doe'"), "Jane Doe")

    def test_double_quote_pair_is_stripped(self):
        self.assertEqual(_sanitize_name('"Jane Doe"'), "Jane Doe")

    def test_backtick_pair_is_stripped(self):
        self.assertEqual(_sanitize_name("`Jane Doe`"), "Jane Doe")

    def test_nested_quote_pairs_are_stripped(self):
        self.assertEqual(_sanitize_name("\"'Jane Doe'\""), "Jane Doe")

    def test_whitespace_between_nested_pairs_is_stripped(self):
        self.assertEqual(_sanitize_name(" ' \"Jane\" ' "), "Jane")

    def test_unbalanced_quote_is_kept(self):
        self.assertEqual(_sanitize_name("'Jane"), "'Jane")
        self.assertEqual(_sanitize_name("Jane'"), "Jane'")

    def test_mismatched_quotes_are_kept(self):
        self.assertEqual(_sanitize_name("'Jane\""), "'Jane\"")

    def test_interior_apostrophe_is_kept(self):
        self.assertEqual(_sanitize_name("O'Brien"), "O'Brien")

    def test_quotes_only_becomes_none(self):
        self.assertIsNone(_sanitize_name("''"))
        self.assertIsNone(_sanitize_name('" "'))

    def test_blank_becomes_none(self):
        self.assertIsNone(_sanitize_name(None))
        self.assertIsNone(_sanitize_name(""))
        self.assertIsNone(_sanitize_name("   "))


class ToDocument(unittest.TestCase):
    """``to_document`` — lowercased key, original-cased address, sanitized name in the text blob."""

    def to_document(self, address):
        # to_document touches no instance state, so skip SearchStore's on-disk constructor.
        return EmailAddressIndex.to_document(mock.Mock(spec=EmailAddressIndex), address)

    def test_name_is_sanitized_everywhere(self):
        document = self.to_document({"name": "'Jane Doe'", "email": "Jane@Example.com"})
        self.assertEqual(
            document,
            {
                "id": "jane@example.com",
                "email": "Jane@Example.com",
                "name": "Jane Doe",
                "text": "Jane Doe Jane@Example.com",
            },
        )

    def test_missing_name_leaves_email_only_text(self):
        document = self.to_document({"email": "jane@example.com"})
        self.assertIsNone(document["name"])
        self.assertEqual(document["text"], "jane@example.com")


class IndexAddresses(unittest.TestCase):
    """``index_addresses`` — silently drop entries without a syntactically valid email."""

    def index_addresses(self, addresses):
        """Return the addresses that survive filtering and reach ``index_documents``."""

        index = mock.Mock(spec=EmailAddressIndex)
        EmailAddressIndex.index_addresses(index, addresses)
        return index.index_documents.call_args[0][0]

    def test_valid_email_is_indexed(self):
        address = {"name": "Jane", "email": "jane@example.com"}
        self.assertEqual(self.index_addresses([address]), [address])

    def test_missing_email_is_skipped(self):
        self.assertEqual(self.index_addresses([{"name": "Jane"}, {"name": "No Email", "email": ""}]), [])

    def test_malformed_emails_are_skipped(self):
        malformed = [
            {"email": "not-an-email"},
            {"email": "Jane <jane@example.com>"},
            {"email": "jane@example"},  # no TLD
            {"email": "jane @example.com"},
            {"email": "@example.com"},
        ]
        self.assertEqual(self.index_addresses(malformed), [])

    def test_valid_survives_malformed_neighbours(self):
        valid = {"name": "Jane", "email": "jane@example.com"}
        self.assertEqual(self.index_addresses([{"email": "not-an-email"}, valid]), [valid])

    def test_batch_dedupes_case_insensitively(self):
        first = {"name": "Jane", "email": "jane@example.com"}
        second = {"name": "Jane Doe", "email": "Jane@Example.com"}
        self.assertEqual(self.index_addresses([first, second]), [second])


if __name__ == "__main__":
    unittest.main()
