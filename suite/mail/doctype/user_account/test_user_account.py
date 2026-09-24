# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from frappe.tests import UnitTestCase

from suite.mail.doctype.user_account.user_account import pick_account_user, pick_personal_account


def account(name: str, login: str) -> dict:
    return {"name": name, "_name": login}


class UnitTestPickPersonalAccount(UnitTestCase):
    def test_the_only_personal_account_is_the_users(self):
        self.assertEqual(pick_personal_account([account("ih", "akash@frappe.io")], None), "ih")

    def test_a_colleagues_shared_account_is_not(self):
        accounts = [account("te", "colleague@frappe.io"), account("ih", "akash@frappe.io")]
        self.assertEqual(pick_personal_account(accounts, "akash@frappe.io"), "ih")

    def test_ambiguous_when_none_is_named_after_the_login(self):
        accounts = [account("te", "colleague@frappe.io"), account("ih", "someone@frappe.io")]
        self.assertIsNone(pick_personal_account(accounts, "akash@frappe.io"))
        self.assertIsNone(pick_personal_account(accounts, None))

    def test_none_without_personal_accounts(self):
        self.assertIsNone(pick_personal_account([], "akash@frappe.io"))


class UnitTestPickAccountUser(UnitTestCase):
    """`logins` holds only the linked users who can connect: enabled, with a mail server login."""

    def test_the_owner_whose_login_the_account_is(self):
        users = ["colleague@frappe.io", "akash@frappe.io"]
        logins = {"colleague@frappe.io": "colleague@frappe.io", "akash@frappe.io": "Akash@frappe.io"}
        self.assertEqual(pick_account_user(users, logins, "akash@frappe.io", True), "akash@frappe.io")
        # A team account named after one of its members' logins is theirs as well.
        self.assertEqual(pick_account_user(users, logins, "akash@frappe.io", False), "akash@frappe.io")

    def test_never_a_user_a_personal_account_is_only_shared_with(self):
        # The owner is disabled, or gone; a colleague it is shared with would reach only the share.
        users = ["akash@frappe.io", "colleague@frappe.io"]
        logins = {"colleague@frappe.io": "colleague@frappe.io"}
        self.assertIsNone(pick_account_user(users, logins, "akash@frappe.io", True))
        self.assertIsNone(pick_account_user(["colleague@frappe.io"], logins, "akash@frappe.io", True))

    def test_the_first_member_of_a_team_account_that_can_connect(self):
        # The first member is disabled and the second has no login, so neither is in `logins`.
        users = ["left@frappe.io", "nologin@frappe.io", "akash@frappe.io", "colleague@frappe.io"]
        logins = {"akash@frappe.io": "akash@frappe.io", "colleague@frappe.io": "colleague@frappe.io"}
        self.assertEqual(pick_account_user(users, logins, "support@frappe.io", False), "akash@frappe.io")

    def test_none_when_no_member_can_connect(self):
        self.assertIsNone(pick_account_user(["left@frappe.io"], {}, "support@frappe.io", False))
