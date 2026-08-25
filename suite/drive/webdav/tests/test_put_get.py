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
            cls.folder_name = f"Media-{frappe.generate_hash(length=6)}"
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
        # user bytes must come back inert for browsers
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Content-Security-Policy"], "sandbox")

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
        from suite.drive.webdav.tests.utils import enable_user_webdav

        frappe.db.set_single_value("Drive Disk Settings", "webdav_enabled", 1)
        frappe.clear_document_cache("Drive Disk Settings", "Drive Disk Settings")
        enable_user_webdav(OWNER)
        frappe.db.commit()
        try:
            response = dispatch(
                "GET", f"/dav/Home/{self.folder_name}/data.bin", user=OWNER, password=PASSWORD
            )
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
            frappe.db.set_value("Drive Settings", OWNER, "webdav_enabled", 0, update_modified=False)
            frappe.db.commit()


class TestWebDAVPut(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_user_with_password(OWNER, PASSWORD)
        ensure_user(STRANGER)
        with cls.set_user(OWNER):
            cls.home = get_user_folder(OWNER).name

    def setUp(self):
        frappe.set_user(OWNER)
        with self.set_user(OWNER):
            self.base_name = f"Put-{frappe.generate_hash(length=6)}"
            self.base = create_drive_file(
                self.base_name, self.home, "Folder", lambda f: FileManager().create_folder(f)
            )

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _put(self, path: str, data: bytes, user: str = OWNER, headers: dict | None = None):
        from suite.drive.webdav import put as put_module

        return put_module.handle(
            make_ctx("PUT", path, user, data=data, content_type="application/octet-stream", headers=headers)
        )

    def _resolve(self, path: str, user: str = OWNER):
        from suite.drive.webdav import pathmap

        pathmap.reset_memo()
        return pathmap.resolve([segment for segment in path.split("/") if segment], user)

    def test_put_creates_file(self):
        body = b"fresh content here"
        response = self._put(f"/dav/Home/{self.base_name}/new.txt", body)
        self.assertEqual(response.status_code, 201)

        import hashlib

        expected_hash = hashlib.sha256(body).hexdigest()
        self.assertEqual(response.headers["ETag"], f'"sha256-{expected_hash[:32]}"')

        row = self._resolve(f"Home/{self.base_name}/new.txt").entity
        self.assertEqual(row.file_size, len(body))
        self.assertEqual(row.content_hash, expected_hash)
        self.assertEqual(row.mime_type, "text/plain")
        manager = FileManager()
        self.assertEqual(manager.get_local_path(row.file_url).read_bytes(), body)
        # parent rollup grew
        self.assertEqual(frappe.db.get_value("File", self.base.name, "file_size"), len(body))

    def test_put_unreadable_target_hidden_as_404(self):
        # the read-gate must run before preconditions/locks/the 405 collection
        # reply, so an unreadable resource is indistinguishable from an absent one
        from suite.drive.utils import get_root_folder

        with self.set_user(OWNER):
            secret = create_drive_file(
                f"put-secret-{frappe.generate_hash(length=6)}",
                get_root_folder().name,
                "Folder",
                lambda f: FileManager().create_folder(f),
            )
            write_file_fixture(secret.name, "hidden.txt", b"nope")
        frappe.get_doc(
            {"doctype": "Drive Permission", "entity": secret.name, "user": STRANGER, "deny": 1, "read": 1}
        ).insert(ignore_permissions=True)

        path = f"/dav/Everyone/{secret.file_name}/hidden.txt"
        # If-None-Match: * would be a 412 existence oracle on an existing resource
        with self.assertRaises(NotFoundError):
            self._put(path, b"x", user=STRANGER, headers={"If-None-Match": "*"})
        # a plain overwrite attempt is 404, not 403
        with self.assertRaises(NotFoundError):
            self._put(path, b"x", user=STRANGER)

    def test_put_out_of_range_mtime_is_ignored(self):
        # a wildly large X-OC-Mtime must not overflow datetime.fromtimestamp / 500
        response = self._put(
            f"/dav/Home/{self.base_name}/stamped.txt",
            b"data",
            headers={"X-OC-Mtime": "99999999999999999999"},
        )
        self.assertEqual(response.status_code, 201)

    def test_put_overwrites_in_place(self):
        with self.set_user(OWNER):
            target = write_file_fixture(self.base.name, "doc.txt", b"version-one")
        response = self._put(f"/dav/Home/{self.base_name}/doc.txt", b"v2!")
        self.assertEqual(response.status_code, 204)

        row = self._resolve(f"Home/{self.base_name}/doc.txt").entity
        # same entity, no auto-rename
        self.assertEqual(row.name, target.name)
        self.assertEqual(row.file_size, 3)
        manager = FileManager()
        self.assertEqual(manager.get_local_path(row.file_url).read_bytes(), b"v2!")
        # edit activity was logged
        self.assertTrue(
            frappe.db.exists("Drive Entity Activity Log", {"entity": target.name, "action_type": "edit"})
        )

    def test_put_overwrite_failure_leaves_old_bytes(self):
        # the blob swap is irreversible while every DB write rolls back with the
        # transaction, so a failure after the swap would leave new bytes served
        # under the old size/hash/mtime — the swap must come last
        from unittest.mock import patch

        from suite.drive.webdav import put as put_module

        with self.set_user(OWNER):
            target = write_file_fixture(self.base.name, "doc.txt", b"version-one")
        blob_path = FileManager().get_local_path(target.file_url)

        with (
            patch.object(put_module, "create_new_activity_log", side_effect=frappe.ValidationError),
            self.assertRaises(frappe.ValidationError),
        ):
            self._put(f"/dav/Home/{self.base_name}/doc.txt", b"v2!")

        self.assertEqual(blob_path.read_bytes(), b"version-one")

    def test_put_overwrite_by_collaborator_keeps_owner(self):
        from suite.drive.utils import get_root_folder

        with self.set_user("Administrator"):
            shared_folder = create_drive_file(
                f"put-shared-{frappe.generate_hash(length=6)}",
                get_root_folder().name,
                "Folder",
                lambda f: FileManager().create_folder(f),
                owner=OWNER,
            )
        with self.set_user(OWNER):
            target = write_file_fixture(shared_folder.name, "shared.txt", b"mine")
        frappe.get_doc(
            {
                "doctype": "Drive Permission",
                "entity": target.name,
                "user": STRANGER,
                "read": 1,
                "write": 1,
            }
        ).insert(ignore_permissions=True)

        response = self._put(f"/dav/Everyone/{shared_folder.file_name}/shared.txt", b"theirs!", user=STRANGER)
        self.assertEqual(response.status_code, 204)
        # content replaced, but ownership (and quota accounting) stays put
        self.assertEqual(frappe.db.get_value("File", target.name, "owner"), OWNER)
        self.assertEqual(frappe.db.get_value("File", target.name, "file_size"), len(b"theirs!"))

    def test_put_statuses(self):
        from suite.drive.webdav.errors import BadRequest, Conflict, Forbidden, MethodNotAllowed

        with self.assertRaises(Conflict):  # missing intermediate
            self._put(f"/dav/Home/{self.base_name}/nowhere/x.txt", b"x")
        with self.assertRaises(MethodNotAllowed):  # target is a collection
            self._put(f"/dav/Home/{self.base_name}", b"x")
        with self.assertRaises(MethodNotAllowed):  # mount
            self._put("/dav/Home", b"x")
        with self.assertRaises(Conflict):  # trailing slash on a new resource
            self._put(f"/dav/Home/{self.base_name}/dir-ish/", b"x")
        with self.assertRaises(BadRequest):  # partial PUT
            self._put(f"/dav/Home/{self.base_name}/x.txt", b"x", headers={"Content-Range": "bytes 0-0/5"})
        from suite.drive.utils import get_root_folder

        with self.set_user("Administrator"):
            foreign = create_drive_file(
                f"put-ro-{frappe.generate_hash(length=6)}",
                get_root_folder().name,
                "Folder",
                lambda f: FileManager().create_folder(f),
                owner=OWNER,
            )
        with self.assertRaises(Forbidden):  # $GENERAL read on Everyone grants no upload
            self._put(f"/dav/Everyone/{foreign.file_name}/x.txt", b"x", user=STRANGER)

    def test_put_conditionals(self):
        from suite.drive.webdav.errors import PreconditionFailed

        with self.set_user(OWNER):
            write_file_fixture(self.base.name, "locked.txt", b"held")
        with self.assertRaises(PreconditionFailed):
            self._put(f"/dav/Home/{self.base_name}/locked.txt", b"no", headers={"If-None-Match": "*"})
        with self.assertRaises(PreconditionFailed):
            self._put(f"/dav/Home/{self.base_name}/locked.txt", b"no", headers={"If-Match": '"wrong"'})

    def test_put_honors_client_mtime(self):
        response = self._put(
            f"/dav/Home/{self.base_name}/dated.txt", b"x", headers={"X-OC-Mtime": "1700000000"}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["X-OC-Mtime"], "accepted")

        from datetime import UTC, datetime

        from suite.drive.webdav.properties import to_site_naive

        row = self._resolve(f"Home/{self.base_name}/dated.txt").entity
        stored = frappe.db.get_value("File", row.name, "file_modified")
        # the UTC epoch stored in the site zone, not the OS zone
        self.assertEqual(
            frappe.utils.get_datetime(stored), to_site_naive(datetime.fromtimestamp(1700000000, tz=UTC))
        )

    def test_put_empty_body(self):
        response = self._put(f"/dav/Home/{self.base_name}/empty.bin", b"")
        self.assertEqual(response.status_code, 201)
        row = self._resolve(f"Home/{self.base_name}/empty.bin").entity
        self.assertEqual(row.file_size, 0)

    def test_put_quota_is_507_and_cleans_scratch(self):
        from suite.drive.api.files import get_upload_path
        from suite.drive.webdav.errors import InsufficientStorage

        frappe.db.set_value("Drive Settings", OWNER, "quota", 1, update_modified=False)
        try:
            with self.assertRaises(InsufficientStorage):
                self._put(f"/dav/Home/{self.base_name}/big.bin", b"z" * (2 * 1024 * 1024))
        finally:
            frappe.db.set_value("Drive Settings", OWNER, "quota", 0, update_modified=False)

        uploads_dir = get_upload_path("probe").parent
        leftovers = [p for p in uploads_dir.glob("webdav_*")]
        self.assertEqual(leftovers, [])

    def test_put_after_delete_creates_new_entity(self):
        from suite.drive.webdav import structure

        with self.set_user(OWNER):
            original = write_file_fixture(self.base.name, "cycle.txt", b"one")
        structure.handle_delete(make_ctx("DELETE", f"/dav/Home/{self.base_name}/cycle.txt", OWNER))

        response = self._put(f"/dav/Home/{self.base_name}/cycle.txt", b"two")
        self.assertEqual(response.status_code, 201)
        row = self._resolve(f"Home/{self.base_name}/cycle.txt").entity
        self.assertNotEqual(row.name, original.name)
