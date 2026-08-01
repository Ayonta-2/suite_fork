import unittest
from unittest import mock

from suite.api import account


class AccountTestBase(unittest.TestCase):
    def setUp(self):
        self.frappe = self.enterContext(mock.patch("suite.api.account.frappe"))
        self.frappe.session.user = "alice@example.com"
        self.enterContext(mock.patch("suite.api.account._", side_effect=lambda s: s))


class MarkOnboarded(AccountTestBase):
    def setUp(self):
        super().setUp()
        self.engine = self.enterContext(
            mock.patch("frappe.desk.page.setup_wizard.setup_wizard.complete_app_setup")
        )
        self.suite_wizard = self.enterContext(
            mock.patch("suite.api.account.uses_suite_setup_wizard", return_value=True)
        )
        self.enterContext(mock.patch("suite.api.account.build_setup_args", return_value={"country": "India"}))
        self.frappe.is_setup_complete.return_value = False

    def test_denies_non_system_manager_before_any_write(self):
        self.frappe.only_for.side_effect = RuntimeError("not allowed")
        with self.assertRaises(RuntimeError):
            account.mark_onboarded()
        self.engine.assert_not_called()
        self.frappe.db.set_single_value.assert_not_called()

    def test_runs_engine_when_suite_is_the_wizard_and_setup_is_open(self):
        account.mark_onboarded(timezone="Asia/Kolkata")
        self.frappe.only_for.assert_called_with("System Manager")
        self.engine.assert_called_once_with(country="India")
        self.frappe.db.set_single_value.assert_called_once_with("Suite Settings", "is_onboarded", 1)

    def test_skips_engine_unless_suite_wizard_and_setup_open(self):
        for suite_wizard, site_setup_complete in ((True, True), (False, False)):
            with self.subTest(suite_wizard=suite_wizard, site_setup_complete=site_setup_complete):
                self.suite_wizard.return_value = suite_wizard
                self.frappe.is_setup_complete.return_value = site_setup_complete
                account.mark_onboarded(timezone="Asia/Kolkata")
                self.engine.assert_not_called()


class UpdateWorkspace(AccountTestBase):
    def test_denies_non_system_manager_before_save(self):
        self.frappe.only_for.side_effect = RuntimeError("not allowed")
        with self.assertRaises(RuntimeError):
            account.update_workspace("Acme")
        self.frappe.get_single.assert_not_called()

    def test_saves_trimmed_name_and_valid_logo(self):
        self.frappe.db.exists.return_value = "FILE-0001"
        settings = mock.Mock(workspace_logo="")
        self.frappe.get_single.return_value = settings

        account.update_workspace("  Acme  ", "/files/logo.png")

        self.assertEqual(settings.workspace_name, "Acme")
        self.assertEqual(settings.workspace_logo, "/files/logo.png")
        settings.save.assert_called_once()
        self.frappe.throw.assert_not_called()


class InviteUsers(AccountTestBase):
    def setUp(self):
        super().setUp()
        self.invite = self.enterContext(mock.patch("frappe.core.api.user_invitation.invite_by_email"))

    def test_denies_non_system_manager_before_inviting(self):
        self.frappe.only_for.side_effect = RuntimeError("not allowed")
        with self.assertRaises(RuntimeError):
            account.invite_users("bob@example.com")
        self.invite.assert_not_called()

    def test_passes_server_derived_roles_and_suite_redirect(self):
        self.frappe.get_hooks.return_value = {"allowed_roles": {"System Manager": ["Suite User"]}}
        self.frappe.get_roles.return_value = ["System Manager"]
        account.invite_users("bob@example.com")
        self.invite.assert_called_once_with(
            emails="bob@example.com",
            roles=["Suite User"],
            redirect_to_path="/suite",
            app_name="suite",
        )
