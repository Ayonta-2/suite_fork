# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
"""The email-address index's normalization and ranking contracts: display names lose the quotes
clients wrap them in, only syntactically valid addresses ever reach the index, and suggestions come
back ordered by how well the query matches a name or address rather than in index order."""

import unittest
from unittest import mock

from suite.mail.store.indexes.email_address import (
    EmailAddressIndex,
    _relevance_key,
    _sanitize_name,
    _tokenize,
)


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


class Tokenize(unittest.TestCase):
    """``_tokenize`` — lowercased alphanumeric runs, matching how the index tokenized the text."""

    def test_name_and_address_split_on_punctuation(self):
        self.assertEqual(
            _tokenize("Jane Doe jane.doe@example.com"), ["jane", "doe", "jane", "doe", "example", "com"]
        )

    def test_accented_word_stays_whole(self):
        self.assertEqual(_tokenize("Jörg Müller"), ["jörg", "müller"])

    def test_non_latin_script_stays_whole(self):
        self.assertEqual(_tokenize("山田太郎"), ["山田太郎"])

    def test_underscore_separates_words(self):
        self.assertEqual(_tokenize("jane_doe"), ["jane", "doe"])

    def test_blank_has_no_tokens(self):
        self.assertEqual(_tokenize(None), [])
        self.assertEqual(_tokenize("  -- "), [])


class Relevance(unittest.TestCase):
    """``_relevance_key`` — the order suggestions are presented in, most relevant first."""

    def rank(self, query, addresses):
        """Return `addresses` ordered as the suggestion list would present them."""

        tokens = _tokenize(query)
        ordered = sorted(addresses, key=lambda hit: _relevance_key(tokens, hit))
        return [address["email"] for address in ordered]

    def test_whole_word_beats_longer_word_starting_with_it(self):
        # The reported case: "Doe" is what was typed, "Doeringer" merely starts with it.
        doe = {"name": "John Doe", "email": "john@example.com"}
        doeringer = {"name": "Jane Doeringer", "email": "jane@example.com"}
        self.assertEqual(self.rank("doe", [doeringer, doe]), [doe["email"], doeringer["email"]])

    def test_first_word_beats_later_word(self):
        first = {"name": "Doe Jansen", "email": "dj@example.com"}
        later = {"name": "Ann Doe", "email": "ad@example.com"}
        self.assertEqual(self.rank("doe", [later, first]), [first["email"], later["email"]])

    def test_whole_local_part_beats_name_match(self):
        address = {"name": None, "email": "jane@example.com"}
        named = {"name": "Jane Roe", "email": "jane.roe@example.com"}
        self.assertEqual(self.rank("jane", [named, address]), [address["email"], named["email"]])

    def test_name_match_beats_domain_match(self):
        named = {"name": "Acme Support", "email": "support@example.com"}
        hosted = {"name": "Jane Doe", "email": "jane@acme.test"}
        self.assertEqual(self.rank("acme", [hosted, named]), [named["email"], hosted["email"]])

    def test_adjacent_terms_beat_scattered_ones(self):
        # Addresses run counter to the alphabetical tie-break, so only the ranking can order these.
        adjacent = {"name": "Jane Doe", "email": "c@example.com"}
        interrupted = {"name": "Jane Ann Doe", "email": "b@example.com"}
        reversed_ = {"name": "Doe Jane", "email": "a@example.com"}
        self.assertEqual(
            self.rank("jane doe", [reversed_, interrupted, adjacent]),
            [adjacent["email"], interrupted["email"], reversed_["email"]],
        )

    def test_match_spanning_name_and_address_sorts_last(self):
        # Indexed as one "<name> <email>" blob, so this matches the query without any single
        # field explaining it — it stays a hit, but below every address that does explain one.
        spanning = {"name": "Jane", "email": "doe@example.com"}
        explained = {"name": "Jane Doelan", "email": "jane.doelan@example.com"}
        self.assertEqual(
            self.rank("jane doe", [spanning, explained]), [explained["email"], spanning["email"]]
        )

    def test_equally_good_matches_prefer_named_then_shortest(self):
        named = {"name": "Jane Doe", "email": "jane.doe@example.com"}
        short = {"name": None, "email": "jane.aoe@example.com"}
        long_ = {"name": None, "email": "jane.abercrombie@example.com"}
        self.assertEqual(
            self.rank("jane", [long_, short, named]),
            [named["email"], short["email"], long_["email"]],
        )


class SearchEmailAddresses(unittest.TestCase):
    """``search_email_addresses`` — every match is ranked, however many the index returns."""

    def search(self, query, corpus, limit=10):
        """Search `corpus` — held in index order — through a stand-in for the Tantivy retrieval.

        The stand-in matches the way the real prefix query does (every token present, the last one
        as a prefix), returns hits unscored in index order, and honours `limit` by truncating,
        reporting the full match count alongside as Tantivy does.
        """

        def search_prefix(tokens, limit):
            matched = [
                hit
                for hit in corpus
                if all(
                    any(word.startswith(token) for word in _tokenize(f"{hit['name']} {hit['email']}"))
                    for token in tokens
                )
            ]
            return (matched[:limit], len(matched))

        index = mock.Mock(spec=EmailAddressIndex)
        index.search_prefix.side_effect = search_prefix

        results = EmailAddressIndex.search_email_addresses(index, query, limit=limit)
        return [result["email"] for result in results], index.search_prefix.call_count

    def test_a_better_match_past_the_first_page_still_wins(self):
        # The whole set has to be ranked: retrieval is unscored, so this exact-word match sits
        # wherever it was indexed — here past a pool of longer words that merely start with "jan".
        noise = [{"name": f"Janssen {n}", "email": f"janssen{n}@example.com"} for n in range(6000)]
        exact = {"name": "Jan Novak", "email": "jan@example.org"}

        emails, searches = self.search("jan", [*noise, exact])
        self.assertEqual(emails[0], exact["email"])
        # One search to fill the pool, a second once its count showed the pool had been truncated.
        self.assertEqual(searches, 2)

    def test_a_set_that_fits_the_pool_is_fetched_once(self):
        corpus = [{"name": "Jane Doe", "email": "jane@example.com"}]

        emails, searches = self.search("jane", corpus)
        self.assertEqual(emails, [corpus[0]["email"]])
        self.assertEqual(searches, 1)

    def test_blank_query_searches_for_nothing(self):
        index = mock.Mock(spec=EmailAddressIndex)

        self.assertEqual(EmailAddressIndex.search_email_addresses(index, "  -- "), [])
        index.search_prefix.assert_not_called()


if __name__ == "__main__":
    unittest.main()
