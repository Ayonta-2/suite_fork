# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from unittest.mock import patch

from frappe.tests import IntegrationTestCase

from suite.calendar.doctype.calendar_event.calendar_event import add_calendar_event
from suite.calendar.doctype.calendar_event.calendar_event import (
    get_calendar_events as get_events_by_ids,
)
from suite.calendar.doctype.calendar_event.invitations import _attendees
from suite.calendar.doctype.calendar_event.mailing_lists import (
    DEFAULT_MAX_PARTICIPANTS,
    _expansion_enabled,
    _max_participants,
    expand_mailing_list_participants,
)
from suite.calendar.doctype.calendar_exchange.calendar_exchange import jscalendar_to_vevent
from suite.mail.api.admin import add_mailing_list_recipients, get_mailing_list
from suite.mail.stalwart import get_domains, get_mailing_list_index
from suite.mail.tests.base import StalwartIntegrationTestCase, unique_name

MODULE = "suite.calendar.doctype.calendar_event.mailing_lists"

DOMAINS = [{"name": "example.com"}]
INDEX = {
    "team@example.com": ["alice@example.com", "bob@example.com"],
    "team-alias@example.com": ["alice@example.com", "bob@example.com"],
    "everyone@example.com": ["team@example.com", "carol@example.com"],
    "loop-a@example.com": ["loop-b@example.com", "dave@example.com"],
    "loop-b@example.com": ["loop-a@example.com", "erin@example.com"],
}


def participant(email: str, **overrides) -> dict:
    """Builds a participant entry in the shape the calendar event APIs pass around."""

    return {
        "uid": f"uid-{email}",
        "name": None,
        "email": email,
        "kind": "individual",
        "roles": {"attendee": True},
        "schedule_id": f"mailto:{email}",
        "send_to": {"imip": f"mailto:{email}"},
        "participation_status": "needs-action",
        "expect_reply": True,
        "description": None,
        "comment": None,
    } | overrides


def emails(participants: list[dict]) -> list[str]:
    return [p["email"] for p in participants]


class TestMailingListParticipantExpansion(IntegrationTestCase):
    """Mailing list participants are joined by their members before an event is stored.

    The server expands a list only at delivery time, so an ATTENDEE naming the list matches no
    account on ingest and the event lands on nobody's calendar. These cover the expansion that
    adds the members up front, keeping the list itself as an unscheduled group they point back to.
    """

    def expand(self, participants: list[dict], limit: int = 100, index: dict | None = None) -> list[dict]:
        """Runs the expansion against a fixed directory, bypassing Stalwart."""

        with (
            patch(f"{MODULE}._expansion_enabled", return_value=True),
            patch(f"{MODULE}._max_participants", return_value=limit),
            patch(f"{MODULE}._domains", return_value=DOMAINS),
            patch(f"{MODULE}._mailing_list_index", return_value=INDEX if index is None else index),
        ):
            return expand_mailing_list_participants(participants)

    def test_list_is_followed_by_its_members(self):
        expanded = self.expand([participant("team@example.com")])

        self.assertEqual(emails(expanded), ["team@example.com", "alice@example.com", "bob@example.com"])

    def test_the_list_stays_as_a_group_nobody_schedules(self):
        team = self.expand([participant("team@example.com")])[0]

        self.assertEqual(team["kind"], "group")
        self.assertEqual(team["schedule_agent"], "none")
        self.assertIsNone(team["send_to"])
        self.assertIsNone(team["schedule_id"])
        # The organizer's reply expectation is what the members inherit, so it is left alone.
        self.assertTrue(team["expect_reply"])

    def test_members_point_back_at_the_list(self):
        team, alice, bob = self.expand([participant("team@example.com")])

        self.assertEqual(alice["member_of"], {team["uid"]: True})
        self.assertEqual(bob["member_of"], {team["uid"]: True})

    def test_a_list_without_a_uid_is_given_one_up_front(self):
        team, alice, _ = self.expand([participant("team@example.com", uid=None)])

        # The server would mint one, but the members' memberOf has to name it before that.
        self.assertTrue(team["uid"])
        self.assertEqual(alice["member_of"], {team["uid"]: True})

    def test_an_alias_of_the_list_resolves_to_the_same_members(self):
        expanded = self.expand([participant("team-alias@example.com")])

        self.assertEqual(emails(expanded), ["team-alias@example.com", "alice@example.com", "bob@example.com"])

    def test_other_participants_are_untouched_and_order_is_kept(self):
        outsider = participant("someone@example.org")
        expanded = self.expand([outsider, participant("team@example.com")])

        self.assertEqual(
            emails(expanded),
            ["someone@example.org", "team@example.com", "alice@example.com", "bob@example.com"],
        )
        self.assertEqual(expanded[0], outsider)

    def test_a_member_invited_separately_is_not_duplicated(self):
        expanded = self.expand([participant("alice@example.com"), participant("team@example.com")])

        self.assertEqual(emails(expanded), ["alice@example.com", "team@example.com", "bob@example.com"])
        # The explicit entry wins, so a response already recorded against it is not discarded.
        self.assertEqual(expanded[0]["uid"], "uid-alice@example.com")
        self.assertNotIn("member_of", expanded[0])

    def test_nested_lists_are_flattened(self):
        expanded = self.expand([participant("everyone@example.com")])

        self.assertEqual(
            emails(expanded),
            ["everyone@example.com", "alice@example.com", "bob@example.com", "carol@example.com"],
        )
        # Members point at the list the organizer named, not the nested one they sit on.
        self.assertEqual(expanded[1]["member_of"], {expanded[0]["uid"]: True})

    def test_a_membership_cycle_terminates(self):
        expanded = self.expand([participant("loop-a@example.com")])

        # loop-b is expanded where it sits, ahead of dave, and its reference back to loop-a is
        # dropped as already visited.
        self.assertEqual(emails(expanded), ["loop-a@example.com", "erin@example.com", "dave@example.com"])

    def test_members_inherit_the_lists_role_but_get_their_own_identity(self):
        source = participant("team@example.com", roles={"attendee": True, "optional": True})
        alice = self.expand([source])[1]

        self.assertEqual(alice["roles"], {"attendee": True, "optional": True})
        self.assertTrue(alice["expect_reply"])
        self.assertEqual(alice["kind"], "individual")
        # Cleared so the server mints a fresh uid (and RSVP link) and rebuilds routing from the
        # member's own address instead of pointing back at the list.
        self.assertIsNone(alice["uid"])
        self.assertIsNone(alice["send_to"])
        self.assertIsNone(alice["schedule_id"])
        self.assertIsNone(alice["schedule_agent"])

    def test_members_do_not_inherit_the_lists_group_kind(self):
        alice = self.expand([participant("team@example.com", kind="Group")])[1]

        self.assertIsNone(alice["kind"])

    def test_the_size_cap_truncates_and_is_reported(self):
        with patch(f"{MODULE}._report_truncation") as report:
            expanded = self.expand([participant("everyone@example.com")], limit=2)

        self.assertEqual(emails(expanded), ["everyone@example.com", "alice@example.com", "bob@example.com"])
        report.assert_called_once()
        self.assertEqual(report.call_args.args[0], 2)
        self.assertEqual(report.call_args.args[1], ["carol@example.com"])

    def test_the_cap_never_drops_an_explicitly_invited_participant(self):
        # The list fills the cap on its own, so a naive total cap would truncate the attendee the
        # organizer named after it — and on the next update _plan() reads a vanished participant as
        # withdrawn and mails them a cancellation.
        with patch(f"{MODULE}._report_truncation"):
            expanded = self.expand(
                [participant("everyone@example.com"), participant("boss@example.org")], limit=2
            )

        self.assertEqual(
            emails(expanded),
            ["everyone@example.com", "alice@example.com", "bob@example.com", "boss@example.org"],
        )

    def test_explicit_participants_consume_the_cap_before_members(self):
        with patch(f"{MODULE}._report_truncation") as report:
            expanded = self.expand(
                [participant("boss@example.org"), participant("everyone@example.com")], limit=2
            )

        # The cap bounds the invited total, so boss takes one of the two slots and expansion adds
        # one member; the list itself is never mailed and does not use up a slot.
        self.assertEqual(emails(expanded), ["boss@example.org", "everyone@example.com", "alice@example.com"])
        self.assertEqual(report.call_args.args[1], ["bob@example.com", "carol@example.com"])

    def test_an_explicit_participant_wins_even_when_the_list_comes_first(self):
        expanded = self.expand([participant("team@example.com"), participant("alice@example.com")])

        self.assertEqual(emails(expanded), ["team@example.com", "bob@example.com", "alice@example.com"])
        # The explicit uid survives; a member entry would reset the RSVP recorded against it.
        self.assertEqual(expanded[-1]["uid"], "uid-alice@example.com")

    def test_a_later_save_keeps_members_and_drops_those_who_left(self):
        team, alice, bob = self.expand([participant("team@example.com")])
        alice["uid"], alice["participation_status"] = "uid-alice", "accepted"
        bob["uid"] = "uid-bob"

        index = INDEX | {"team@example.com": ["alice@example.com", "carol@example.com"]}
        expanded = self.expand([team, alice, bob], index=index)

        self.assertEqual(emails(expanded), ["team@example.com", "alice@example.com", "carol@example.com"])
        # Alice's entry survives as it is, so her RSVP stays recorded; Carol is new.
        self.assertEqual(expanded[1]["uid"], "uid-alice")
        self.assertEqual(expanded[1]["participation_status"], "accepted")
        self.assertIsNone(expanded[2]["uid"])
        self.assertEqual(expanded[0]["uid"], team["uid"])

    def test_removing_the_list_uninvites_its_members(self):
        _, alice, bob = self.expand([participant("team@example.com")])

        expanded = self.expand([participant("boss@example.org"), alice, bob])

        self.assertEqual(emails(expanded), ["boss@example.org"])

    def test_members_of_a_list_gone_from_the_directory_are_kept(self):
        team, alice, bob = self.expand([participant("team@example.com")])

        index = {k: v for k, v in INDEX.items() if k != "team@example.com"}
        expanded = self.expand([team, alice, bob], index=index)

        # Deleting the list is an admin's doing, not the organizer's; nobody is uninvited over it.
        self.assertEqual(emails(expanded), ["team@example.com", "alice@example.com", "bob@example.com"])
        self.assertEqual(expanded[1], alice)

    def test_expansion_can_be_turned_off(self):
        participants = [participant("team@example.com")]
        with (
            patch(f"{MODULE}._expansion_enabled", return_value=False),
            patch(f"{MODULE}._mailing_list_index") as index,
        ):
            self.assertEqual(expand_mailing_list_participants(participants), participants)

        index.assert_not_called()

    def test_external_only_participants_skip_the_directory_lookup(self):
        participants = [participant("someone@example.org")]
        with (
            patch(f"{MODULE}._expansion_enabled", return_value=True),
            patch(f"{MODULE}._domains", return_value=DOMAINS),
            patch(f"{MODULE}._mailing_list_index") as index,
        ):
            self.assertEqual(expand_mailing_list_participants(participants), participants)

        index.assert_not_called()

    def test_an_unreachable_directory_leaves_participants_alone(self):
        participants = [participant("team@example.com")]
        with (
            patch(f"{MODULE}._expansion_enabled", return_value=True),
            patch(f"{MODULE}._domains", return_value=DOMAINS),
            patch(f"{MODULE}._mailing_list_index", return_value={}),
        ):
            self.assertEqual(expand_mailing_list_participants(participants), participants)

    def test_nothing_to_do_without_participants(self):
        self.assertIsNone(expand_mailing_list_participants(None))
        self.assertEqual(expand_mailing_list_participants([]), [])


def stored_event(**participants: dict) -> dict:
    """Builds an event the way the JMAP server returns it: participants keyed by uid."""

    return {"participants": {uid: {"@type": "Participant", **p} for uid, p in participants.items()}}


class TestMailingListInviteAddressing(IntegrationTestCase):
    """A member is mailed individually, but the mail names the list the way list mail does."""

    ORGANIZER = "org@example.com"

    def event(self) -> dict:
        return stored_event(
            owner={"calendarAddress": f"mailto:{self.ORGANIZER}", "roles": {"owner": True}},
            team={
                "calendarAddress": "mailto:team@example.com",
                "name": "Team",
                "kind": "group",
                "scheduleAgent": "none",
                "expectReply": True,
            },
            alice={
                "calendarAddress": "mailto:alice@example.com",
                "name": "Alice",
                "expectReply": True,
                "memberOf": {"team": True},
            },
            boss={"calendarAddress": "mailto:boss@example.org", "name": "Boss", "expectReply": True},
        )

    def test_the_list_itself_is_never_mailed(self):
        attendees = _attendees(self.event(), self.ORGANIZER)

        self.assertEqual(set(attendees), {"alice@example.com", "boss@example.org"})

    def test_a_member_is_addressed_through_the_list(self):
        attendees = _attendees(self.event(), self.ORGANIZER)

        self.assertEqual(attendees["alice@example.com"]["to"], "Team <team@example.com>")
        self.assertEqual(attendees["boss@example.org"]["to"], "boss@example.org")

    def test_a_list_named_by_its_address_is_not_doubled_up(self):
        event = self.event()
        event["participants"]["team"]["name"] = "team@example.com"

        self.assertEqual(_attendees(event, self.ORGANIZER)["alice@example.com"]["to"], "team@example.com")

    def test_the_itip_attendee_records_the_membership(self):
        event = self.event() | {
            "uid": "abc",
            "title": "Standup",
            "start": "2026-11-09T10:00:00",
            "duration": "PT1H",
            "timeZone": "UTC",
        }

        # Unfolded, so a long ATTENDEE line can be matched whole.
        ics = jscalendar_to_vevent(event).to_ical().decode().replace("\r\n ", "")
        attendees = [line for line in ics.splitlines() if line.startswith("ATTENDEE")]
        team = next(line for line in attendees if line.endswith(":mailto:team@example.com"))
        alice = next(line for line in attendees if line.endswith(":mailto:alice@example.com"))

        self.assertIn('MEMBER="mailto:team@example.com"', alice)
        self.assertIn("CUTYPE=GROUP", team)
        # The list is on the event for display, so it is not asked to reply.
        self.assertIn("RSVP=FALSE", team)
        self.assertIn("RSVP=TRUE", alice)


class TestMailingListExpansionConfig(IntegrationTestCase):
    """The toggle and the cap resolve through ``get_config``, so site config can supply either."""

    def test_the_toggle_is_coerced_to_a_bool(self):
        with patch(f"{MODULE}.get_config", return_value=1):
            self.assertTrue(_expansion_enabled())

        with patch(f"{MODULE}.get_config", return_value=None):
            self.assertFalse(_expansion_enabled())

    def test_the_cap_accepts_a_string_from_site_config(self):
        with patch(f"{MODULE}.get_config", return_value="25"):
            self.assertEqual(_max_participants(), 25)

    def test_the_cap_falls_back_to_the_default_when_unset(self):
        with patch(f"{MODULE}.get_config", return_value=0):
            self.assertEqual(_max_participants(), DEFAULT_MAX_PARTICIPANTS)


class TestMailingListInvite(StalwartIntegrationTestCase):
    """An event invited to a real mailing list is stored against the list's members."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.organizer = cls.create_member()
        cls.first = cls.create_member()
        cls.second = cls.create_member()
        cls.organizer_account = cls.personal_account(cls.organizer)

    def test_the_list_address_is_stored_with_its_members(self):
        list_id = self.create_mailing_list()
        with self.set_user("Administrator"):
            add_mailing_list_recipients(list_id, [self.first.email, self.second.email])
            list_email = get_mailing_list(list_id)["email"]

        # The directory is cached, and the list was created after this run started.
        get_domains.clear_cache()
        get_mailing_list_index.clear_cache()

        with self.set_user(self.organizer.email):
            event_id = add_calendar_event(
                self.organizer_account,
                organizer=self.organizer.email,
                title=f"List invite {unique_name('event')}",
                start="2026-11-09T10:00:00",
                duration="PT1H",
                time_zone="UTC",
                participants=[
                    {"email": self.organizer.email, "participation_status": "ACCEPTED"},
                    {"email": list_email, "participation_status": "NEEDS-ACTION", "expect_reply": True},
                ],
                send_scheduling_messages=True,
            )
            participants = get_events_by_ids(self.organizer_account, [event_id])[0]["participants"]

        by_email = {p["email"]: p for p in participants}
        self.assertEqual(
            set(by_email), {self.organizer.email, list_email, self.first.email, self.second.email}
        )

        # The list stays for display only: a group with scheduling off and no routing.
        team = by_email[list_email]
        self.assertEqual(team["kind"], "Group")
        self.assertEqual(team["schedule_agent"], "none")
        self.assertEqual(team["send_to"], {})

        # A distinct uid per member is what gives each of them their own RSVP link, and the
        # link back to the list is what puts the list in their invitation's To header.
        members = [by_email[self.first.email], by_email[self.second.email]]
        self.assertEqual(len({p["uid"] for p in members}), 2)
        self.assertTrue(all(p["expect_reply"] for p in members))
        self.assertTrue(all(p["member_of"] == {team["uid"]: True} for p in members))
