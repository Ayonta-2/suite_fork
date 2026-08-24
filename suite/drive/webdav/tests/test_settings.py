from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from suite.drive.api.product import set_settings, set_webdav_enabled, webdav_config
from suite.drive.webdav.settings import global_webdav_enabled, user_webdav_enabled
from suite.tests.utils import ensure_user

USER = "webdav-settings-user@example.com"
FRESH = "webdav-settings-fresh@example.com"


class TestWebDAVSettings(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_user(USER)
        ensure_user(FRESH)

    def setUp(self):
        self._set_global(0)

    def tearDown(self):
        self._set_global(0)
        frappe.set_user("Administrator")
        super().tearDown()

    def _set_global(self, value: int):
        frappe.db.set_single_value("Drive Disk Settings", "webdav_enabled", value)
        frappe.clear_document_cache("Drive Disk Settings", "Drive Disk Settings")

    def test_config_is_empty_for_users_while_disabled(self):
        with self.set_user(USER):
            self.assertEqual(webdav_config(), {})

    def test_config_shows_admin_the_toggle_while_disabled(self):
        config = webdav_config()  # Administrator
        self.assertEqual(config, {"globally_enabled": False, "is_admin": True})

    def test_config_for_enabled_user(self):
        self._set_global(1)
        with self.set_user(USER):
            config = webdav_config()
        self.assertTrue(config["globally_enabled"])
        self.assertFalse(config["is_admin"])
        self.assertTrue(config["server_url"].endswith("/dav/"))
        self.assertEqual(config["username"], USER)
        self.assertTrue(config["enabled_for_user"])
        self.assertFalse(config["two_factor_blocked"])

    def test_config_flags_two_factor(self):
        self._set_global(1)
        with patch("frappe.twofactor.should_run_2fa", return_value=True), self.set_user(USER):
            self.assertTrue(webdav_config()["two_factor_blocked"])

    def test_set_webdav_enabled_is_admin_only(self):
        with self.set_user(USER), self.assertRaises(frappe.PermissionError):
            set_webdav_enabled(True)
        self.assertFalse(global_webdav_enabled())

        set_webdav_enabled(True)  # Administrator
        self.assertTrue(global_webdav_enabled())
        set_webdav_enabled(False)
        self.assertFalse(global_webdav_enabled())

    def test_user_opt_out_via_set_settings(self):
        with self.set_user(USER):
            set_settings({"webdav_enabled": 0})
            self.assertFalse(user_webdav_enabled(USER))
            set_settings({"webdav_enabled": 1})
            self.assertTrue(user_webdav_enabled(USER))

    def test_missing_settings_row_defaults_to_enabled(self):
        frappe.db.delete("Drive Settings", {"user": FRESH})
        self.assertTrue(user_webdav_enabled(FRESH))
