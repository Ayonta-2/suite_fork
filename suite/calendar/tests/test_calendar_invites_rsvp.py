# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import frappe

from suite.calendar.api import rsvp_calendar_event
from suite.calendar.api.rsvp import (
    build_rsvp_links,
    resolve_rsvp,
    sync_response_to_participant_calendars,
)
from suite.calendar.doctype.calendar_event.calendar_event import add_calendar_event
from suite.calendar.doctype.calendar_event.calendar_event import (
    get_calendar_events as get_events_by_ids,
)
from suite.mail.tests.base import StalwartIntegrationTestCase, unique_name

# NOTE: server-side iMIP scheduling (send_scheduling_messages materializing the event on the
# attendee's server-side calendar) does not deliver on stock Stalwart v0.16.x - the app's
# custom event invites + the mail-invite flow (test_calendar_mail_invites) cover how invites
# actually reach participants. These tests exercise the RSVP machinery itself.


class TestCalendarInvitesRsvp(StalwartIntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.organizer = cls.create_member()
        cls.attendee = cls.create_member()
        cls.organizer_account = cls.personal_account(cls.organizer)
        cls.attendee_account = cls.personal_account(cls.attendee)

    def _create_invite(self, title: str) -> str:
        with self.set_user(self.organizer.email):
            return add_calendar_event(
                self.organizer_account,
                organizer=self.organizer.email,
                title=title,
                start="2026-10-05T14:00:00",
                duration="PT1H",
                time_zone="UTC",
                participants=[
                    {"email": self.organizer.email, "participation_status": "ACCEPTED"},
                    {
                        "email": self.attendee.email,
                        "participation_status": "NEEDS-ACTION",
                        "expect_reply": True,
                    },
                ],
                send_scheduling_messages=True,
            )

    def _participant(self, event_id: str, email: str) -> dict:
        with self.set_user(self.organizer.email):
            detail = get_events_by_ids(self.organizer_account, [event_id])[0]
            return next(p for p in detail["participants"] if p["email"] == email)

    def test_logged_in_rsvp(self):
        title = f"Design review {unique_name('event')}"
        event_id = self._create_invite(title)

        self.assertEqual(
            self._participant(event_id, self.attendee.email)["participation_status"], "NEEDS-ACTION"
        )

        # The organizer is a participant too and can RSVP on their own copy.
        with self.set_user(self.organizer.email):
            rsvp_calendar_event(self.organizer_account, event_id, "tentative")
        self.assertEqual(
            self._participant(event_id, self.organizer.email)["participation_status"], "TENTATIVE"
        )

        # Invalid responses and accounts without a copy of the event are rejected.
        with self.set_user(self.organizer.email):
            self.assertRaisesRegex(
                frappe.ValidationError,
                "Invalid RSVP",
                rsvp_calendar_event,
                self.organizer_account,
                event_id,
                "maybe-later",
            )
        with self.set_user(self.attendee.email):
            self.assertRaises(
                frappe.ValidationError,
                rsvp_calendar_event,
                self.attendee_account,
                event_id,  # organizer-scoped id; the attendee has no such copy
                "accepted",
            )

    def test_signed_rsvp_links(self):
        title = f"Offsite {unique_name('event')}"
        event_id = self._create_invite(title)
        participant = self._participant(event_id, self.attendee.email)

        with self.set_user(self.organizer.email):
            links = build_rsvp_links(
                self.organizer_account,
                event_id,
                participant["uid"],
                self.attendee.email,
                expires_at=int(time.time()) + 3600,
            )
        self.assertEqual(set(links), {"accept", "tentative", "decline"})

        token = parse_qs(urlparse(links["accept"]).query)["token"][0]

        # The guest page records the response (its commit is stubbed to keep test isolation).
        with self.set_user("Guest"), patch.object(frappe.db, "commit"):
            result = resolve_rsvp(token)
        self.assertTrue(result["success"], result)
        self.assertIn(title, result["event_title"])
        self.assertTrue(result["event_when"])

        self.assertEqual(self._participant(event_id, self.attendee.email)["participation_status"], "ACCEPTED")

        # Tampered, expired, and missing-expiry tokens are all rejected.
        with self.set_user("Guest"), patch.object(frappe.db, "commit"):
            self.assertFalse(resolve_rsvp(token[:-4] + "aaaa")["success"])

        with self.set_user(self.organizer.email):
            expired = build_rsvp_links(
                self.organizer_account,
                event_id,
                participant["uid"],
                self.attendee.email,
                expires_at=int(time.time()) - 10,
            )
        expired_token = parse_qs(urlparse(expired["decline"]).query)["token"][0]
        with self.set_user("Guest"), patch.object(frappe.db, "commit"):
            self.assertFalse(resolve_rsvp(expired_token)["success"])

    def test_sync_response_to_participant_calendars(self):
        title = f"All hands {unique_name('event')}"
        event_id = self._create_invite(title)

        with self.set_user(self.organizer.email):
            uid = get_events_by_ids(self.organizer_account, [event_id])[0]["uid"]

        # Simulate the attendee having received the invite: a same-uid copy on their calendar.
        from suite.mail.jmap import get_calendar_event_service

        with self.set_user(self.attendee.email):
            service = get_calendar_event_service(self.attendee_account)
            response = service.create(
                [
                    {
                        "creation_id": "copy",
                        "uid": uid,
                        "title": title,
                        "start": "2026-10-05T14:00:00",
                        "duration": "PT1H",
                        "time_zone": "UTC",
                        "organizer": self.organizer.email,
                        "participants": [
                            {"email": self.organizer.email, "participation_status": "ACCEPTED"},
                            {
                                "email": self.attendee.email,
                                "participation_status": "NEEDS-ACTION",
                                "expect_reply": True,
                            },
                        ],
                    }
                ]
            )
            copy_id = response["created"]["copy"]["id"]

        # Propagate a tentative response recorded on the organizer's copy.
        sync_response_to_participant_calendars(
            self.organizer_account, event_id, self.attendee.email, "tentative"
        )

        def attendee_copy_updated():
            with self.set_user(self.attendee.email):
                events = get_events_by_ids(self.attendee_account, [copy_id])
                if not events:
                    return None
                row = next((p for p in events[0]["participants"] if p["email"] == self.attendee.email), None)
                return (row and row["participation_status"] == "TENTATIVE") or None

        self.wait_until(attendee_copy_updated, message="RSVP did not sync to the attendee's local copy.")
