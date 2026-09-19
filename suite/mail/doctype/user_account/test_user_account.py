# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from frappe.tests import UnitTestCase

from suite.mail.doctype.user_account.user_account import pick_personal_account


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
