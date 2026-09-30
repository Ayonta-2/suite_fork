# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""How a Sieve script's content reaches the server: in the request, or through the upload endpoint."""

import unittest

import httpx
from jmap.auth import BasicAuth
from jmap.core.retry import RetryPolicy
from jmap.testing.fake import FakeJMAPServer

from suite.mail.doctype.sieve_script.sieve_script import SCRIPT_BLOB, _script_blob_id
from suite.mail.jmap import SuiteJMAPClient

CORE = "urn:ietf:params:jmap:core"
MAIL = "urn:ietf:params:jmap:mail"
SIEVE = "urn:ietf:params:jmap:sieve"
BLOB = "urn:ietf:params:jmap:blob"
ACCOUNT = "f7"
USER = "user@example.test"
SCRIPT = 'require ["fileinto"];\nif header :contains "subject" "invoice" { fileinto "Bills"; }\n'


def _server(with_blob: bool) -> FakeJMAPServer:
    urns = [CORE, MAIL, SIEVE] + ([BLOB] if with_blob else [])
    server = FakeJMAPServer(
        capabilities={urn: {} for urn in urns},
        accounts={
            ACCOUNT: {"name": USER, "isPersonal": True, "accountCapabilities": {urn: {} for urn in urns}}
        },
        primary_accounts=dict.fromkeys(urns, ACCOUNT),
    )
    server.respond("SieveScript/set", {"created": {"c1": {"id": "s1", "isActive": False}}})
    server.respond("SieveScript/validate", {"error": None})
    return server


def _client(server: FakeJMAPServer) -> SuiteJMAPClient:
    http = httpx.Client(auth=BasicAuth(USER, "pw"), **server.client_kwargs())
    return SuiteJMAPClient.connect(
        "https://jmap.example.com/.well-known/jmap",
        auth=BasicAuth(USER, "pw"),
        http=http,
        experimental=True,
        retry_policy=RetryPolicy(max_attempts=1),
    )


class ScriptBlobs(unittest.TestCase):
    def test_a_server_with_blob_management_takes_the_script_inside_the_request(self):
        server = _server(with_blob=True)
        client = _client(server)

        with client.batch() as b:
            blob_id = _script_blob_id(client, b, SCRIPT)
            b.sieve.sieve_script.set(create={"c1": {"name": "bills", "blobId": blob_id}})

        # One request: the upload, then the /set naming the blob it is about to create.
        (request,) = server.requests
        upload, create = request["methodCalls"][0], request["methodCalls"][1]
        self.assertEqual(upload[0], "Blob/upload")
        self.assertEqual(
            upload[1]["create"][SCRIPT_BLOB],
            {"data": [{"data:asText": SCRIPT}], "type": "application/sieve"},
        )
        self.assertEqual(create[0], "SieveScript/set")
        self.assertEqual(create[1]["create"]["c1"]["blobId"], f"#{SCRIPT_BLOB}")

    def test_a_method_argument_names_the_uploaded_blob_by_result_reference(self):
        server = _server(with_blob=True)
        client = _client(server)

        with client.batch() as b:
            handle = b.sieve.sieve_script.validate(blob_id=_script_blob_id(client, b, SCRIPT, argument=True))

        (request,) = server.requests
        upload, validate = request["methodCalls"][0], request["methodCalls"][1]
        self.assertEqual(validate[0], "SieveScript/validate")
        self.assertEqual(
            validate[1]["#blobId"],
            {"resultOf": upload[2], "name": "Blob/upload", "path": f"/created/{SCRIPT_BLOB}/id"},
        )
        self.assertIsNone(handle.result.error)

    def test_without_blob_management_the_script_goes_to_the_upload_endpoint_first(self):
        server = _server(with_blob=False)
        client = _client(server)

        with client.batch() as b:
            blob_id = _script_blob_id(client, b, SCRIPT)
            b.sieve.sieve_script.set(create={"c1": {"name": "bills", "blobId": blob_id}})

        # The blob exists before the request is sent, and the /set names its real id.
        (request,) = server.requests
        (create,) = request["methodCalls"]
        self.assertEqual(create[0], "SieveScript/set")
        self.assertEqual(create[1]["create"]["c1"]["blobId"], str(blob_id))
        self.assertFalse(str(blob_id).startswith("#"))
        self.assertEqual(server.blobs[str(blob_id)][0], SCRIPT.encode())
