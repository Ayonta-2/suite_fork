# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from werkzeug.exceptions import Forbidden, NotFound

from suite.slides.api.file import validate_media_file
from suite.slides.tests.utils import (
    make_presentation,
    make_private_image,
    make_public,
    unique_image_content,
)
from suite.tests.utils import ensure_user

OWNER = "media-owner@example.com"
OTHER_USER = "media-other@example.com"


class TestMediaFileAccess(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_user(OWNER)
        ensure_user(OTHER_USER)

        with cls.set_user(OWNER):
            cls.presentation = make_presentation("Media Access Test")
            cls.file = make_private_image(cls.presentation.name)

    def test_owner_can_access(self):
        with self.set_user(OWNER):
            self.assertIsNone(validate_media_file(self.file.file_url))

    def test_other_user_forbidden(self):
        with self.set_user(OTHER_USER):
            with self.assertRaises(Forbidden):
                validate_media_file(self.file.file_url)

    def test_guest_forbidden(self):
        with self.set_user("Guest"):
            with self.assertRaises(Forbidden):
                validate_media_file(self.file.file_url)

    def test_guest_can_access_file_of_public_presentation(self):
        # own fixtures: making the shared presentation public would break the deny tests
        with self.set_user(OWNER):
            presentation = make_presentation("Public Media Test")
            file = make_private_image(presentation.name)
            make_public(presentation.name)

        with self.set_user("Guest"):
            self.assertIsNone(validate_media_file(file.file_url))

    def test_guest_can_access_when_a_sibling_row_is_private(self):
        with self.set_user(OWNER):
            files = self.make_shared_url("Sibling Media")
            # the lookup returns rows in name order, so share the one it won't reach first
            first = frappe.db.exists("File", {"file_url": files[0].file_url})
            reachable = next(f for f in files if f.name != first)
            make_public(reachable.attached_to_name)

        with self.set_user("Guest"):
            self.assertIsNone(validate_media_file(files[0].file_url))

    def test_guest_forbidden_when_every_row_is_private(self):
        with self.set_user(OWNER):
            files = self.make_shared_url("Private Sibling Media")

        with self.set_user("Guest"):
            with self.assertRaises(Forbidden):
                validate_media_file(files[0].file_url)

    def test_presentation_arg_narrows_the_lookup(self):
        with self.set_user(OWNER):
            self.assertIsNone(validate_media_file(self.file.file_url, self.presentation.name))

    def test_presentation_arg_grants_nothing_on_its_own(self):
        with self.set_user(OTHER_USER):
            own = make_presentation("Unrelated Presentation")
            with self.assertRaises(Forbidden):
                validate_media_file(self.file.file_url, own.name)

    def test_unknown_url_not_found(self):
        with self.set_user(OWNER):
            with self.assertRaises(NotFound):
                validate_media_file("/private/files/no-such-file.png")

    def make_shared_url(self, title):
        """Two presentations holding the same image, which frappe stores once and
        references from a File row per presentation."""
        content = unique_image_content()
        files = [
            make_private_image(make_presentation(f"{title} {i}").name, content=content) for i in range(2)
        ]
        self.assertEqual(files[0].file_url, files[1].file_url)
        return files
