# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
"""``SearchStore``'s deprecated ``search_phrase_prefix``: the pre-rename name still searches for a
phrase rather than quietly becoming the looser search that replaced it."""

import unittest
from unittest import mock

import tantivy

from suite.store.search_store import SearchStore


class SearchPhrasePrefix(unittest.TestCase):
    """``search_phrase_prefix`` — the pre-rename name, still searching for a phrase, still deprecated."""

    def search(self, terms, **kwargs):
        """Return the Tantivy query the deprecated search would run."""

        schema_builder = tantivy.SchemaBuilder()
        schema_builder.add_text_field("text")

        store = mock.Mock(spec=SearchStore)
        store._schema = schema_builder.build()
        store.DEFAULT_SEARCH_FIELDS = ("text",)
        store._build_phrase_prefix_query.side_effect = lambda t, f: SearchStore._build_phrase_prefix_query(
            store, t, f
        )
        store._run_search.side_effect = lambda build_query, *_args: (build_query(None), 0)

        with self.assertWarns(Warning):
            query, _count = SearchStore.search_phrase_prefix(store, terms, **kwargs)

        return query

    def test_terms_are_searched_for_as_a_phrase_not_scattered(self):
        # The contract the name promises, and the reason this isn't a forward to search_prefix:
        # a phrase query matches "Jane Doe" but not "Jane Ann Doe" or "Doe Jane".
        self.assertIn("PhrasePrefixQuery", repr(self.search(["jane", "d"])))

    def test_blank_terms_search_for_nothing(self):
        store = mock.Mock(spec=SearchStore)

        with self.assertWarns(Warning):
            self.assertEqual(SearchStore.search_phrase_prefix(store, ["", None]), ([], 0))

        store._run_search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
