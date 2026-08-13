# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from suite.writer.api.general import get_drive_file_meta


class IntegrationTestGetDriveFileMeta(IntegrationTestCase):
    """
    get_drive_file_meta caches {name: {title, file_id}} in Redis so repeat
    lookups (e.g. paginated search results) skip the DB.
    """

    def setUp(self):
        self.content_docname = f"test-writer-doc-{frappe.generate_hash(8)}"
        self.file_name = f"test-file-{frappe.generate_hash(8)}"
        self.row = {
            "name": self.file_name,
            "file_name": "Report.docx",
            "content_docname": self.content_docname,
        }

    def tearDown(self):
        frappe.cache().delete_value(f"search:drive_file:{self.file_name}")
        super().tearDown()

    def test_second_lookup_is_served_from_cache(self):
        with patch("suite.writer.api.general.frappe.get_all", return_value=[self.row]) as mock_get_all:
            first = get_drive_file_meta([self.content_docname])
            self.assertEqual(mock_get_all.call_count, 1)

            second = get_drive_file_meta([self.content_docname])

            self.assertEqual(
                mock_get_all.call_count,
                1,
                "second lookup should be served from the Redis cache, not hit the DB again",
            )

        self.assertEqual(first, second)
        self.assertEqual(first[self.content_docname]["title"], "Report.docx")
