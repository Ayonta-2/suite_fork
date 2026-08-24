from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from werkzeug.datastructures import Headers
from werkzeug.exceptions import NotFound

from suite.drive.webdav.dispatch import handle_before_request
from suite.drive.webdav.tests.utils import dispatch, ensure_user_with_password, set_dav_request

USER = "webdav-dispatch@example.com"
PASSWORD = "webdav-dispatch-pw-9000"


class TestWebDAVDispatch(IntegrationTestCase):
    """The dispatcher commits and rolls back mid-request, so fixtures are
    committed up front and the global toggle is restored explicitly."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_user_with_password(USER, PASSWORD)
        frappe.db.commit()

    def setUp(self):
        self._set_global(1)

    def tearDown(self):
        self._set_global(0, commit=True)
        frappe.set_user("Administrator")
        super().tearDown()

    def _set_global(self, value: int, commit: bool = False):
        frappe.db.set_single_value("Drive Disk Settings", "webdav_enabled", value)
        frappe.clear_document_cache("Drive Disk Settings", "Drive Disk Settings")
        if commit:
            frappe.db.commit()

    def test_non_dav_paths_pass_through(self):
        for path in ("/davsomething", "/drive/home", "/api/method/ping"):
            set_dav_request("PROPFIND", path)
            self.assertIsNone(handle_before_request())

    def test_global_toggle_off_is_stock_404(self):
        self._set_global(0)
        set_dav_request("PROPFIND", "/dav/Home")
        self.assertRaises(NotFound, handle_before_request)

    def test_options_answered_without_auth(self):
        response = dispatch("OPTIONS", "/dav")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["DAV"], "1, 2, 3")
        self.assertEqual(response.headers["MS-Author-Via"], "DAV")
        self.assertIn("PROPFIND", response.headers["Allow"])
        self.assertIn("LOCK", response.headers["Allow"])

    def test_options_on_server_root_advertises_dav(self):
        frappe.local.response_headers = Headers()
        self.assertIsNone(dispatch("OPTIONS", "/"))
        self.assertEqual(frappe.local.response_headers.get("DAV"), "1, 2, 3")

        # feature off: no advertisement
        self._set_global(0)
        frappe.local.response_headers = Headers()
        self.assertIsNone(dispatch("OPTIONS", "/"))
        self.assertIsNone(frappe.local.response_headers.get("DAV"))

    def test_unauthenticated_request_gets_challenge(self):
        response = dispatch("PROPFIND", "/dav/Home")

        self.assertEqual(response.status_code, 401)
        self.assertIn("Basic", response.headers["WWW-Authenticate"])

    def test_unhandled_method_is_405_with_allow(self):
        response = dispatch("POST", "/dav/Home", user=USER, password=PASSWORD)

        self.assertEqual(response.status_code, 405)
        self.assertIn("PROPFIND", response.headers["Allow"])
        self.assertNotIn("POST", response.headers["Allow"])

    def test_user_toggle_off_is_403(self):
        if not frappe.db.exists("Drive Settings", USER):
            frappe.get_doc({"doctype": "Drive Settings", "user": USER}).insert(ignore_permissions=True)
        frappe.db.set_value("Drive Settings", USER, "webdav_enabled", 0)
        frappe.db.commit()
        try:
            response = dispatch("PROPFIND", "/dav/Home", user=USER, password=PASSWORD)
        finally:
            frappe.db.set_value("Drive Settings", USER, "webdav_enabled", 1)
            frappe.db.commit()

        self.assertEqual(response.status_code, 403)
        self.assertIn("disabled for your account", response.get_data(as_text=True))

    def test_success_path_commits_before_raising(self):
        with patch.object(frappe.db, "commit", wraps=frappe.db.commit) as commit:
            response = dispatch("OPTIONS", "/dav")

        self.assertEqual(response.status_code, 200)
        commit.assert_called()

    def test_unexpected_handler_error_maps_to_500(self):
        from suite.drive.webdav import dispatch as dispatch_module

        with patch.dict(dispatch_module._HANDLERS, {"PROPFIND": ("missing_module", "handle")}):
            response = dispatch("PROPFIND", "/dav/Home", user=USER, password=PASSWORD)

        self.assertEqual(response.status_code, 500)
