# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import operator
import re
from unittest.mock import patch

# import frappe
from frappe.tests import IntegrationTestCase

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]

# RFC 5231 relational match types.
RELATIONS = {
    "gt": operator.gt,
    "ge": operator.ge,
    "lt": operator.lt,
    "le": operator.le,
    "eq": operator.eq,
    "ne": operator.ne,
}


def render_screening_gate(accepted_emails: list[str]) -> str:
    """Render the Screening gate with the mailbox and identity lookups (JMAP calls) stubbed out."""

    from suite.mail.doctype.sieve_script import sieve_script

    with (
        patch.object(sieve_script, "get_screening_mailbox_path", return_value="Screener"),
        patch.object(sieve_script, "get_inbox_mailbox_path", return_value="INBOX"),
        patch.object(sieve_script, "get_account_emails", return_value=["me@own.example"]),
    ):
        return sieve_script.build_screening_gate("account", accepted_emails)


def route_through_gate(gate: str, sender: str, spamtest: int) -> str | None:
    """Evaluate the rendered gate for one message with RFC 5228/5231/5235 semantics.

    Returns the mailbox the gate files the message into, or None when no branch matches — an
    implicit keep, where the server's own filtering picks the mailbox. Understands only the tests the
    gate emits, and fails on anything else rather than guess.
    """

    def evaluate(test: str) -> bool:
        test = test.strip()
        if test.startswith("anyof"):
            return any(evaluate(t) for t in test[test.index("(") + 1 : test.rindex(")")].split(","))
        if test.startswith("not "):
            return not evaluate(test[4:])
        if match := re.fullmatch(r'address :is "from" "(.+)"', test):
            return sender.lower() == match[1].lower()
        if match := re.fullmatch(r'address :domain :is "from" "(.+)"', test):
            return sender.rpartition("@")[2].lower() == match[1].lower()
        if match := re.fullmatch(r'spamtest :value "(\w+)" :comparator "i;ascii-numeric" "(\d+)"', test):
            return RELATIONS[match[1]](spamtest, int(match[2]))
        raise AssertionError(f"Unrecognised Sieve test: {test}")

    branches = re.findall(
        r'\b(?:if|elsif) (.+?) \{\s*fileinto (?::create )?"([^"]+)";\s*stop;\s*\}', gate, flags=re.DOTALL
    )
    assert branches, f"No branches found in the gate:\n{gate}"

    return next((mailbox for test, mailbox in branches if evaluate(test)), None)


class IntegrationTestSieveScript(IntegrationTestCase):
    """
    Integration tests for SieveScript.
    Use this class for testing interactions between multiple components.
    """

    def test_screening_gate_screens_all_mail_the_server_does_not_call_spam(self):
        """Mail from an unaccepted sender goes to the Screener unless Stalwart calls it spam.

        Stalwart hands the script a spamtest value (RFC 5235) of 0 when it did not score the message,
        1-4 for ham (1 at a score of zero or below, rising towards the spam threshold) and 5-10 for
        spam. Spam is left to the server, which files it into Junk. Ham with a small positive score
        must be screened too: letting it fall through delivered it straight to the Inbox.
        """

        for accepted in ([], ["boss@work.example", "@partner.example"]):
            gate = render_screening_gate(accepted)
            for spamtest in range(11):
                with self.subTest(accepted=accepted, spamtest=spamtest):
                    expected = "Screener" if spamtest < 5 else None
                    self.assertEqual(route_through_gate(gate, "stranger@else.example", spamtest), expected)

    def test_screening_gate_delivers_trusted_senders_to_the_inbox(self):
        gate = render_screening_gate(["boss@work.example", "@partner.example"])

        # Accepted addresses and domains, and the account's own identities, skip the Screener at
        # every spam score.
        for sender in ("boss@work.example", "anyone@partner.example", "me@own.example"):
            for spamtest in range(11):
                with self.subTest(sender=sender, spamtest=spamtest):
                    self.assertEqual(route_through_gate(gate, sender, spamtest), "INBOX")

        # A subdomain of an accepted domain is a different domain.
        self.assertEqual(route_through_gate(gate, "someone@info.partner.example", 1), "Screener")

    def test_screening_gate_recreates_a_missing_screener(self):
        """Stalwart files into the Inbox when a `fileinto` target does not exist, so the gate creates
        the Screener on delivery instead (RFC 5490 `:create`, from the `mailbox` extension)."""

        from suite.mail.doctype.sieve_script.sieve_script import AUTOMATION_SCRIPT_REQUIRE

        self.assertIn('fileinto :create "Screener";', render_screening_gate([]))
        self.assertIn('"mailbox"', AUTOMATION_SCRIPT_REQUIRE)

    def test_sender_match_condition(self):
        from suite.mail.doctype.sieve_script.sieve_script import _sender_match_condition

        # A plain email matches the full From address.
        self.assertEqual(
            _sender_match_condition("john@example.com"),
            'address :is "from" "john@example.com"',
        )
        # A '@domain' entry matches every sender from that domain via the :domain address part.
        self.assertEqual(
            _sender_match_condition("@example.com"),
            'address :domain :is "from" "example.com"',
        )
        # Blank / bare '@' values produce no condition.
        self.assertIsNone(_sender_match_condition(""))
        self.assertIsNone(_sender_match_condition("   "))
        self.assertIsNone(_sender_match_condition("@"))

    def test_build_screening_block_with_domain(self):
        from suite.mail.doctype.sieve_script.sieve_script import _build_screening_block

        # A mix of an address and a domain OR-es both address tests inside a single anyof block.
        block = _build_screening_block(
            "Rejected Emails", ["spammer@bad.com", "@bad-domain.io"], ["  discard;", "  stop;"]
        )
        self.assertIn('address :is "from" "spammer@bad.com"', block)
        self.assertIn('address :domain :is "from" "bad-domain.io"', block)
        self.assertIn("if anyof (", block)
        self.assertIn("# Rejected Emails", block)

    def test_remove_sieve_block_removes_multi_stop_block(self):
        from suite.mail.doctype.sieve_script.sieve_script import remove_sieve_block

        # The Screening gate is an if/elsif block with two `stop;` statements; removal must strip the
        # whole thing, not just up to the first `stop;`.
        script = (
            'require ["fileinto"];\n\n'
            "# Screening\n"
            'if address :is "from" "boss@work.com" {\n'
            '  fileinto "INBOX";\n'
            "  stop;\n"
            "}\n"
            'elsif not spamtest :value "ge" :comparator "i;ascii-numeric" "5" {\n'
            '  fileinto :create "Screener";\n'
            "  stop;\n"
            "}\n"
        )

        result = remove_sieve_block(script, "Screening")

        self.assertNotIn("# Screening", result)
        self.assertNotIn("elsif", result)
        self.assertNotIn("Screener", result)
        self.assertIn('require ["fileinto"];', result)

    def test_remove_sieve_block_preserves_following_block(self):
        from suite.mail.doctype.sieve_script.sieve_script import remove_sieve_block

        script = (
            "# Rejected Emails\n"
            'if address :is "from" "x@bad.com" {\n'
            "  discard;\n"
            "  stop;\n"
            "}\n\n"
            "# Mailbox: Work\n"
            'if address :is "from" "team@work.com" {\n'
            '  fileinto "Work";\n'
            "  stop;\n"
            "}\n"
        )

        result = remove_sieve_block(script, "Rejected Emails")

        self.assertNotIn("# Rejected Emails", result)
        self.assertNotIn("x@bad.com", result)
        self.assertIn("# Mailbox: Work", result)
        self.assertIn("team@work.com", result)
