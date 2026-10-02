# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""What the mail doctypes make of a call the JMAP layer refuses, and of a read it has to split."""

import unittest
from itertools import count
from unittest import mock

import frappe
import httpx
from jmap.auth import BasicAuth
from jmap.core.retry import RetryPolicy
from jmap.testing.fake import FakeJMAPServer

from suite.mail.doctype.address_book import address_book
from suite.mail.doctype.contact_card import contact_card
from suite.mail.doctype.mailbox import mailbox
from suite.mail.doctype.sieve_script import sieve_script
from suite.mail.doctype.vacation_response import vacation_response
from suite.mail.jmap import SuiteJMAPClient

CORE = "urn:ietf:params:jmap:core"
URNS = [
    CORE,
    "urn:ietf:params:jmap:mail",
    "urn:ietf:params:jmap:contacts",
    "urn:ietf:params:jmap:sieve",
    "urn:ietf:params:jmap:blob",
    "urn:ietf:params:jmap:vacationresponse",
]
ACCOUNT = "f7"
USER = "user@example.test"
SCRIPT = 'require ["fileinto"];\nkeep;\n'
DOCTYPES = (address_book, contact_card, mailbox, sieve_script, vacation_response)


def _server(core: dict | None = None, **account) -> FakeJMAPServer:
    capabilities = {**{urn: {} for urn in URNS}, CORE: core or {}}
    return FakeJMAPServer(
        capabilities=capabilities,
        accounts={
            ACCOUNT: {"name": USER, "isPersonal": True, "accountCapabilities": capabilities, **account}
        },
        primary_accounts=dict.fromkeys(URNS, ACCOUNT),
    )


def _client(server: FakeJMAPServer) -> SuiteJMAPClient:
    http = httpx.Client(auth=BasicAuth(USER, "pw"), **server.client_kwargs())
    return SuiteJMAPClient.connect(
        "https://jmap.example.com/.well-known/jmap",
        auth=BasicAuth(USER, "pw"),
        http=http,
        experimental=True,
        retry_policy=RetryPolicy(max_attempts=1),
    )


class _Doctypes(unittest.TestCase):
    """The doctypes, talking to `self.server` instead of the user's mail server."""

    def serve(self, server: FakeJMAPServer) -> None:
        self.server = server
        client = _client(server)
        for module in DOCTYPES:
            patcher = mock.patch.object(module, "get_account_client", return_value=client)
            patcher.start()
            self.addCleanup(patcher.stop)

    def sent(self) -> list[str]:
        return [call[0] for request in self.server.requests for call in request["methodCalls"]]


class ReadOnlyAccount(_Doctypes):
    """An account the session marks read-only - one shared for reading - takes no write."""

    def setUp(self) -> None:
        self.serve(_server(isReadOnly=True))
        # What an update reads before it writes.
        script = {"id": "s1", "name": "bills", "blobId": "B1", "isActive": False}
        self.server.respond("SieveScript/get", {"state": "s", "list": [script], "notFound": []})
        self.server.respond("SieveScript/query", {"queryState": "q", "ids": [], "position": 0, "total": 0})
        self.server.respond(
            "VacationResponse/get",
            {"state": "v", "list": [{"id": "singleton", "isEnabled": False}], "notFound": []},
        )

    def assert_refused(self, write, *args, **kwargs) -> None:
        with self.assertRaises(frappe.ValidationError) as raised:
            write(*args, **kwargs)

        self.assertIn("read-only", str(raised.exception))
        self.assertFalse([name for name in self.sent() if name.endswith(("/set", "/upload"))])

    def test_a_mailbox_is_not_created(self):
        self.assert_refused(mailbox.add_mailbox, ACCOUNT, "Bills")

    def test_a_mailbox_is_not_updated(self):
        self.assert_refused(mailbox.update_mailbox, ACCOUNT, "m1", "Bills", parent="m2")

    def test_mailboxes_are_not_deleted(self):
        self.assert_refused(mailbox.delete_mailboxes, ACCOUNT, ["m1"])

    def test_a_mailbox_is_not_moved(self):
        mailboxes = [
            {"id": id, "name": id, "role": None, "sortOrder": order}
            for id, order in (("m1", 100), ("m2", 200))
        ]
        self.server.respond("Mailbox/get", {"state": "m", "list": mailboxes, "notFound": []})

        self.assert_refused(mailbox.update_mailbox_position, ACCOUNT, "m1", "m2")

    def test_address_books_are_not_deleted(self):
        self.assert_refused(address_book.delete_address_books, ACCOUNT, ["ab1"])

    def test_contact_cards_are_not_added_in_bulk(self):
        card = {"address_book_ids": ["ab1"], "full_name": "Asha Rao"}

        self.assert_refused(contact_card.bulk_add_contact_cards, ACCOUNT, [card])

    def test_contact_cards_are_not_filed_elsewhere(self):
        self.assert_refused(contact_card.contact_card_add_to_address_book, ACCOUNT, ["c1"], "ab1")

    def test_contact_cards_are_not_deleted(self):
        self.assert_refused(contact_card.delete_contact_cards, ACCOUNT, ["c1"])

    def test_an_address_book_is_not_created(self):
        self.assert_refused(address_book.add_address_book, ACCOUNT, "Suppliers")

    def test_an_address_book_is_not_updated(self):
        self.assert_refused(address_book.update_address_book, ACCOUNT, "ab1", "Suppliers")

    def test_a_contact_card_is_not_created(self):
        self.assert_refused(contact_card.add_contact_card, ACCOUNT, ["ab1"], "Asha Rao")

    def test_a_contact_card_is_not_updated(self):
        self.assert_refused(contact_card.update_contact_card, ACCOUNT, "c1", ["ab1"], "Asha Rao")

    def test_a_sieve_script_is_not_created(self):
        self.assert_refused(sieve_script.SieveScript._add_sieve_script, ACCOUNT, "bills", SCRIPT)

    def test_a_sieve_script_is_not_updated(self):
        self.assert_refused(sieve_script.SieveScript._update_sieve_script, ACCOUNT, "s1", "bills", SCRIPT)

    def test_a_sieve_script_is_not_deleted(self):
        self.assert_refused(sieve_script.SieveScript._delete_sieve_scripts, ACCOUNT, ["s1"])

    def test_a_vacation_response_is_not_updated(self):
        self.assert_refused(vacation_response.update_vacation_response, ACCOUNT, True, subject="Away")


class LargeRead(_Doctypes):
    """More ids than the server takes in one /get are read in several, whatever happens between."""

    def test_sieve_scripts_changing_mid_read_are_all_returned(self):
        self.serve(_server(core={"maxObjectsInGet": 2}))
        states = count()

        def get(arguments: dict, _server: FakeJMAPServer) -> dict:
            scripts = [{"id": id, "name": id, "blobId": None, "isActive": False} for id in arguments["ids"]]
            return {"state": f"s{next(states)}", "list": scripts, "notFound": []}

        self.server.handle("SieveScript/get", get)
        ids = ["s1", "s2", "s3", "s4", "s5"]

        scripts = sieve_script.SieveScript._get_sieve_scripts(ACCOUNT, ids)

        self.assertEqual([s["id"] for s in scripts], ids)
        asked = [call[1]["ids"] for request in self.server.requests for call in request["methodCalls"]]
        self.assertTrue(all(len(chunk) <= 2 for chunk in asked), asked)
