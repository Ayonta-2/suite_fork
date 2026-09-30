# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""The client glue over jmaplib, against jmap.testing.FakeJMAPServer."""

import unittest
from unittest import mock

import httpx
from jmap import client as jmap_client
from jmap.auth import BasicAuth
from jmap.core.retry import RetryPolicy
from jmap.testing.fake import FakeJMAPServer

from suite.mail.jmap import SuiteJMAPClient, account_view

CORE = "urn:ietf:params:jmap:core"
MAIL = "urn:ietf:params:jmap:mail"
PERSONAL = "f7"
SHARED = "s2"
USER = "user@example.test"


def _server() -> FakeJMAPServer:
    server = FakeJMAPServer(
        capabilities={CORE: {}, MAIL: {}},
        accounts={
            PERSONAL: {"name": USER, "isPersonal": True, "accountCapabilities": {MAIL: {}}},
            SHARED: {"name": "team@example.test", "isPersonal": False, "accountCapabilities": {MAIL: {}}},
        },
        primary_accounts={CORE: PERSONAL, MAIL: PERSONAL},
    )
    server.respond("Mailbox/get", {"state": "m1", "list": [], "notFound": []})
    return server


def _client(server: FakeJMAPServer) -> SuiteJMAPClient:
    http = httpx.Client(auth=BasicAuth(USER, "pw"), **server.client_kwargs())
    client = SuiteJMAPClient.connect(
        "https://jmap.example.com/.well-known/jmap",
        auth=BasicAuth(USER, "pw"),
        http=http,
        experimental=True,
        retry_policy=RetryPolicy(max_attempts=1),
    )
    client.peers = [client]
    return client


def _mailboxes(client: SuiteJMAPClient) -> None:
    with client.batch() as b:
        b.mail.mailbox.get()


class SessionRefresh(unittest.TestCase):
    """A client and the account views made from it share one session."""

    def test_a_changed_session_is_fetched_once_for_every_view(self):
        server = _server()
        client = _client(server)
        personal, shared = account_view(client, PERSONAL), account_view(client, SHARED)
        _mailboxes(personal)

        server.session_state = "changed"
        with mock.patch.object(jmap_client, "_fetch_session", wraps=jmap_client._fetch_session) as fetch:
            _mailboxes(personal)  # notices the change and refreshes
            _mailboxes(shared)  # already moved on: no second fetch
            _mailboxes(client)

        self.assertEqual(fetch.call_count, 1)
        self.assertEqual({c.session.state for c in (client, personal, shared)}, {"changed"})
        self.assertFalse(any(c.session_stale for c in (client, personal, shared)))

    def test_a_view_keeps_its_own_account_after_a_refresh(self):
        server = _server()
        client = _client(server)
        shared = account_view(client, SHARED)

        server.session_state = "changed"
        _mailboxes(client)

        self.assertEqual(str(shared.default_account), SHARED)
        self.assertEqual(str(client.default_account), PERSONAL)
        with client.batch() as b:
            handle = b.mail.mailbox.get()
        self.assertEqual(server.requests[-1]["methodCalls"][0][1]["accountId"], PERSONAL)
        self.assertIsNotNone(handle.result)
