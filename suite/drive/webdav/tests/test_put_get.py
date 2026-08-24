import frappe
from frappe.tests import IntegrationTestCase

from suite.drive.utils import create_drive_file, get_user_folder
from suite.drive.utils.files import FileManager
from suite.drive.webdav import get as get_module
from suite.drive.webdav.errors import NotFoundError
from suite.drive.webdav.properties import compute_etag
from suite.drive.webdav.tests.utils import (
    dispatch,
    ensure_user_with_password,
    make_ctx,
    write_file_fixture,
)
from suite.tests.utils import ensure_user

OWNER = "webdav-content-owner@example.com"
STRANGER = "webdav-content-stranger@example.com"
PASSWORD = "webdav-content-pw"
DATA = b"0123456789abcdefghij"


class TestWebDAVContent(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_user_with_password(OWNER, PASSWORD)
        ensure_user(STRANGER)
        with cls.set_user(OWNER):
            cls.home = get_user_folder(OWNER).name
            manager = FileManager()
            # committed fixtures survive across runs, so names must be unique
            cls.folder_name = f"Media-{frappe.generate_hash(6)}"
            cls.media = create_drive_file(
                cls.folder_name, cls.home, "Folder", lambda f: manager.create_folder(f)
            )
            cls.blob = write_file_fixture(cls.media.name, "data.bin", DATA, "application/octet-stream")
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _get(self, path: str, user: str = OWNER, method: str = "GET", headers: dict | None = None):
        return get_module.handle(make_ctx(method, path, user, headers=headers))

    @staticmethod
    def _body(response) -> bytes:
        if response.direct_passthrough:
            return b"".join(response.response)
        return response.get_data()

    def test_get_streams_content_with_etag(self):
        response = self._get(f"/dav/Home/{self.folder_name}/data.bin")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._body(response), DATA)
        self.assertEqual(response.headers["Content-Type"], "application/octet-stream")
        self.assertEqual(response.headers["Accept-Ranges"], "bytes")
        self.assertTrue(response.headers["ETag"])
        self.assertTrue(response.headers["Last-Modified"].endswith(" GMT"))
        self.assertNotIn("Content-Disposition", response.headers)

    def test_range_request_yields_206(self):
        response = self._get(f"/dav/Home/{self.folder_name}/data.bin", headers={"Range": "bytes=0-4"})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(self._body(response), DATA[:5])
        self.assertIn("bytes 0-4/", response.headers["Content-Range"])

    def test_if_none_match_yields_304(self):
        row = frappe._dict(
            name=self.blob.name,
            file_size=len(DATA),
            content_hash=None,
            modified=self.blob.file_modified or self.blob.modified,
        )
        etag = compute_etag(row)
        response = self._get(f"/dav/Home/{self.folder_name}/data.bin", headers={"If-None-Match": etag})
        self.assertEqual(response.status_code, 304)

    def test_head_reports_length_without_disposition(self):
        response = self._get(f"/dav/Home/{self.folder_name}/data.bin", method="HEAD")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Length"], str(len(DATA)))

    def test_collection_get_redirects_to_spa(self):
        response = self._get(f"/dav/Home/{self.folder_name}")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], f"/drive/d/{self.media.name}")

        response = self._get("/dav")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/drive")

        response = self._get(f"/dav/Home/{self.folder_name}", method="HEAD")
        self.assertEqual(response.status_code, 200)

    def test_missing_and_unreadable_are_404(self):
        with self.assertRaises(NotFoundError):
            self._get(f"/dav/Home/{self.folder_name}/absent.bin")
        home_name = frappe.db.get_value("File", self.home, "file_name")
        with self.assertRaises(NotFoundError):
            self._get(f"/dav/Everyone/{home_name}/{self.folder_name}/data.bin", user=STRANGER)

    def test_end_to_end_get_through_dispatcher(self):
        frappe.db.set_single_value("Drive Disk Settings", "webdav_enabled", 1)
        frappe.clear_document_cache("Drive Disk Settings", "Drive Disk Settings")
        frappe.db.commit()
        try:
            response = dispatch("GET", f"/dav/Home/{self.folder_name}/data.bin", user=OWNER, password=PASSWORD)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self._body(response), DATA)

            response = dispatch(
                "PROPFIND",
                f"/dav/Home/{self.folder_name}",
                user=OWNER,
                password=PASSWORD,
                headers={"Depth": "1"},
            )
            self.assertEqual(response.status_code, 207)
            self.assertIn(b"data.bin", response.get_data())
        finally:
            frappe.db.set_single_value("Drive Disk Settings", "webdav_enabled", 0)
            frappe.clear_document_cache("Drive Disk Settings", "Drive Disk Settings")
            frappe.db.commit()
