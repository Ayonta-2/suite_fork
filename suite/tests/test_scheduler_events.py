import unittest

import frappe

from suite import hooks


class TestSchedulerEvents(unittest.TestCase):
    def test_registered_methods_resolve(self):
        methods = []
        for event, entries in hooks.scheduler_events.items():
            if event == "cron":
                methods.extend(method for cron_entries in entries.values() for method in cron_entries)
            else:
                methods.extend(entries)

        for method in methods:
            with self.subTest(method=method):
                self.assertTrue(callable(frappe.get_attr(method)))
