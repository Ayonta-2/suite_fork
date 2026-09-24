# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from datetime import timedelta

import frappe
from frappe.tests import UnitTestCase

from suite.calendar.api import (
    EVENT_SEARCH_LIMIT,
    MAX_EVENT_SEARCH_LIMIT,
    _search_limit,
    search_calendar_events_with_shared,
)
from suite.calendar.doctype.calendar_event.calendar_event import add_calendar_event
from suite.mail.tests.base import StalwartIntegrationTestCase, unique_name


class TestCalendarEventSearch(StalwartIntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.member = cls.create_member()
        cls.account = cls.personal_account(cls.member)

    def _search(
        self, text: str | None = None, limit: int | None = None, **filters
    ) -> list[dict]:
        with self.set_user(self.member.email):
            kwargs = {"limit": limit} if limit is not None else {}
            if filters:
                kwargs["filters"] = filters
            return search_calendar_events_with_shared(self.account, text, time_zone="UTC", **kwargs)

    def _wait_for_search(self, text: str, count: int, limit: int | None = None) -> list[dict]:
        # Stalwart indexes asynchronously, so a search run the moment an event is written
        # can answer before the event is in the index it searches.
        return self.wait_until(
            lambda: ((found := self._search(text, limit)) and len(found) >= count and found) or None,
            timeout=60,
            message=f"Search for '{text}' did not find {count} event(s).",
        )

    def _add(self, title: str, start: str) -> str:
        with self.set_user(self.member.email):
            return add_calendar_event(
                self.account, title=title, start=start, duration="PT1H", time_zone="UTC"
            )

    def test_finds_an_event_by_a_word_in_its_title(self):
        word = unique_name("kickoff")
        event_id = self._add(f"Project {word} with the team", "2026-05-04T10:00:00")

        found = self._wait_for_search(word, 1)

        self.assertEqual([event["id"] for event in found], [event_id])
        self.assertEqual(found[0]["account"], self.account)

    def test_answers_in_start_order_whoever_the_events_belong_to(self):
        word = unique_name("review")
        # Written out of order, so an answer in start order is the search's doing and not
        # the order they happened to be created in.
        self._add(f"Second {word}", "2026-06-11T09:00:00")
        self._add(f"Third {word}", "2026-06-12T09:00:00")
        self._add(f"First {word}", "2026-06-10T09:00:00")

        found = self._wait_for_search(word, 3)

        self.assertEqual(
            [event["title"].split()[0] for event in found], ["First", "Second", "Third"]
        )

    def test_a_limit_keeps_the_earliest_of_the_matches(self):
        word = unique_name("sprint")
        self._add(f"Late {word}", "2026-07-20T09:00:00")
        self._add(f"Early {word}", "2026-07-06T09:00:00")
        self._add(f"Middle {word}", "2026-07-13T09:00:00")

        self._wait_for_search(word, 3)
        found = self._search(word, limit=2)

        self.assertEqual([event["title"].split()[0] for event in found], ["Early", "Middle"])

    def test_a_search_with_nothing_asked_answers_with_nothing(self):
        # Not "everything": the palette asks on every keystroke, and a blank line is a reader
        # who has not asked yet rather than one asking for their whole calendar.
        self.assertEqual(self._search(), [])
        self.assertEqual(self._search(""), [])

    def test_a_word_in_the_notes_is_found_only_when_the_notes_are_searched(self):
        word = unique_name("parking")
        with self.set_user(self.member.email):
            add_calendar_event(
                self.account,
                title=f"Offsite {unique_name('trip')}",
                start="2026-08-04T10:00:00",
                duration="PT1H",
                time_zone="UTC",
                description=f"Bring the {word} pass",
            )

        found = self.wait_until(
            lambda: self._search(word, scope="text") or None,
            timeout=60,
            message=f"'{word}' was never indexed.",
        )

        self.assertEqual(len(found), 1)
        self.assertEqual(self._search(word, scope="title"), [])

    def test_a_filter_narrows_a_search_that_has_no_words_in_it(self):
        word = unique_name("summit")
        event_id = self._add(f"Annual {word}", "2026-09-15T09:00:00")
        self._wait_for_search(word, 1)

        with self.set_user(self.member.email):
            calendar = search_calendar_events_with_shared(
                self.account, word, time_zone="UTC"
            )[0]["calendars"][0]["calendar"]

        found = self._search(calendar=calendar)

        self.assertIn(event_id, [event["id"] for event in found])


class TestCalendarSearchBoundary(UnitTestCase):
    """What the whitelisted search accepts. Nothing here reaches Stalwart: a search is refused,
    or sized, before any account is asked."""

    def test_a_count_is_answered_within_the_ceiling(self):
        # The service walks the server batch by batch until it has the number it was handed, so
        # the ceiling is what stops one request reading a whole event store.
        self.assertEqual(_search_limit(10), 10)
        self.assertEqual(_search_limit(10_000), MAX_EVENT_SEARCH_LIMIT)
        self.assertEqual(_search_limit("10000"), MAX_EVENT_SEARCH_LIMIT)

    def test_a_count_that_is_no_count_falls_back_to_the_default(self):
        for asked in (None, 0, "", "not a number"):
            with self.subTest(limit=asked):
                self.assertEqual(_search_limit(asked), EVENT_SEARCH_LIMIT)

    def test_a_negative_count_is_not_a_negative_slice(self):
        # `events[:-5]` would drop the last five matches rather than answer with five.
        self.assertEqual(_search_limit(-5), 1)

    def test_filters_of_the_wrong_shape_are_refused_before_the_account_is_asked(self):
        # An account that does not exist: reaching the server at all would fail differently.
        for filters in ('["text"]', {"attendee": ["a@example.com"]}, {"calendar": 7}):
            with (
                self.subTest(filters=filters),
                self.assertRaises(frappe.ValidationError),
            ):
                search_calendar_events_with_shared("no-such-account", "standup", filters=filters)

    def test_a_search_scope_the_server_does_not_index_is_refused(self):
        # Silently searching `text` when `participants` was asked would widen the search while
        # reading as though it had narrowed it.
        with self.assertRaisesRegex(frappe.ValidationError, "scope: Input should be"):
            search_calendar_events_with_shared(
                "no-such-account", "standup", filters={"scope": "participants"}
            )

    def test_a_recurring_event_answers_as_its_next_few_occurrences(self):
        # A weekly series starting next week: with no range asked, a search does not hand back
        # the master dated the week it was entered, but the next three times it runs — each a
        # row of its own, each pointing back at the series it belongs to.
        word = unique_name("standup")
        start = (frappe.utils.now_datetime() + timedelta(days=7)).replace(microsecond=0)
        with self.set_user(self.member.email):
            series_id = add_calendar_event(
                self.account,
                title=f"Weekly {word}",
                start=start.strftime("%Y-%m-%dT%H:%M:%S"),
                duration="PT30M",
                time_zone="UTC",
                recurrence_rule={"frequency": "weekly"},
            )

        found = self.wait_until(
            lambda: ((rows := self._search(word)) and len(rows) >= 3 and rows) or None,
            timeout=60,
            message=f"Series '{word}' did not expand.",
        )

        self.assertEqual(len(found), 3)
        self.assertEqual({row["master_id"] for row in found}, {series_id})
        self.assertEqual(len({row["start"] for row in found}), 3, "three distinct occurrences")
        self.assertTrue(all(row["recurrence_rule"] not in ("", "{}") for row in found))
        # In order, and none of them behind us: these are the times it will run, not has.
        starts = [row["start"] for row in found]
        self.assertEqual(starts, sorted(starts))
        self.assertGreaterEqual(starts[0], frappe.utils.now_datetime().strftime("%Y-%m-%dT%H:%M:%S"))

    def test_a_one_off_event_is_still_one_row(self):
        word = unique_name("offsite")
        event_id = self._add(f"Team {word}", "2026-11-05T10:00:00")

        found = self._wait_for_search(word, 1)

        self.assertEqual([row["id"] for row in found], [event_id])
        self.assertIsNone(found[0].get("master_id"))
