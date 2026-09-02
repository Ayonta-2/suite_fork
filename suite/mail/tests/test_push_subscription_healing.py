# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
"""``ensure_push_subscription`` — the self-healing check that (re)creates this site's push
subscription on the mail server. A subscription lost to a failed creation, an unrenewed
expiry or a server-side delete silently ends the user's webhooks, so presence must be
verifiable and recoverable without any locally stored record."""

import unittest
from datetime import timedelta
from unittest import mock

from frappe.utils.file_lock import LockTimeoutError

from suite.mail.doctype.push_subscription import push_subscription
from suite.utils.dt import get_utc_now

USER = "user@example.test"


class EnsurePushSubscription(unittest.TestCase):
    def _run(
        self,
        subscriptions: list[dict],
        url: str = "https://mail.example.test",
        disabled: bool = False,
        delete_error: Exception | None = None,
    ) -> tuple[mock.Mock, mock.Mock]:
        with (
            mock.patch.object(push_subscription.frappe.utils, "get_url", return_value=url),
            mock.patch.object(push_subscription, "is_push_subscription_disabled", return_value=disabled),
            mock.patch.object(push_subscription, "get_site_device_client_id", return_value="site-device"),
            mock.patch.object(push_subscription, "get_push_subscription_service") as service,
            mock.patch.object(push_subscription, "_add_push_subscription") as add,
        ):
            service.return_value.get.return_value = subscriptions
            if delete_error:
                service.return_value.delete.side_effect = delete_error
            push_subscription.ensure_push_subscription(USER)

        return add, service

    def test_creates_when_no_subscription_exists(self):
        add, _ = self._run([])

        add.assert_called_once_with(USER, ignore_permissions=True)

    def test_skips_when_live_subscription_exists(self):
        add, _ = self._run([{"deviceClientId": "site-device", "expires": "2999-01-01T00:00:00Z"}])

        add.assert_not_called()

    def test_skips_when_subscription_never_expires(self):
        add, _ = self._run([{"deviceClientId": "site-device", "expires": None}])

        add.assert_not_called()

    def test_other_devices_subscriptions_do_not_count(self):
        add, _ = self._run([{"deviceClientId": "other-device", "expires": "2999-01-01T00:00:00Z"}])

        add.assert_called_once_with(USER, ignore_permissions=True)

    def test_recreates_when_subscription_expired(self):
        add, service = self._run(
            [{"id": "sub-old", "deviceClientId": "site-device", "expires": "2000-01-01T00:00:00Z"}]
        )

        add.assert_called_once_with(USER, ignore_permissions=True)
        service.return_value.delete.assert_called_once_with(["sub-old"])

    def test_expired_duplicate_is_deleted_even_when_live_exists(self):
        add, service = self._run(
            [
                {"id": "sub-old", "deviceClientId": "site-device", "expires": "2000-01-01T00:00:00Z"},
                {"deviceClientId": "site-device", "expires": "2999-01-01T00:00:00Z"},
            ]
        )

        add.assert_not_called()
        service.return_value.delete.assert_called_once_with(["sub-old"])

    def test_delete_failure_does_not_block_recreation(self):
        add, _ = self._run(
            [{"id": "sub-old", "deviceClientId": "site-device", "expires": "2000-01-01T00:00:00Z"}],
            delete_error=RuntimeError("boom"),
        )

        add.assert_called_once_with(USER, ignore_permissions=True)

    def test_skips_on_non_https_site(self):
        add, service = self._run([], url="http://site.localhost:8001")

        add.assert_not_called()
        service.assert_not_called()

    def test_skips_when_user_disabled_push(self):
        add, service = self._run([], disabled=True)

        add.assert_not_called()
        service.assert_not_called()

    def test_skips_when_concurrent_run_holds_the_lock(self):
        with (
            mock.patch.object(
                push_subscription.frappe.utils, "get_url", return_value="https://mail.example.test"
            ),
            mock.patch.object(push_subscription, "is_push_subscription_disabled", return_value=False),
            mock.patch.object(push_subscription, "filelock", side_effect=LockTimeoutError),
            mock.patch.object(push_subscription, "get_push_subscription_service") as service,
            mock.patch.object(push_subscription, "_add_push_subscription") as add,
        ):
            push_subscription.ensure_push_subscription(USER)

        service.assert_not_called()
        add.assert_not_called()


class RenewExpiringPushSubscriptions(unittest.TestCase):
    """``renew_expiring_push_subscriptions`` — healing and the expiry scan share one fetch."""

    def _run(self, subscriptions: list[dict]) -> tuple[mock.Mock, mock.Mock]:
        with (
            mock.patch.object(
                push_subscription.frappe.utils, "get_url", return_value="https://mail.example.test"
            ),
            mock.patch.object(push_subscription, "get_jmap_configured_users", return_value=[USER]),
            mock.patch.object(push_subscription, "is_push_subscription_disabled", return_value=False),
            mock.patch.object(push_subscription, "get_site_device_client_id", return_value="site-device"),
            mock.patch.object(push_subscription, "get_push_subscription_service") as service_factory,
            mock.patch.object(push_subscription, "_add_push_subscription") as add,
            mock.patch.object(push_subscription, "log_mail_error") as log_mail_error,
        ):
            service = service_factory.return_value
            service.get.return_value = subscriptions
            service.update.return_value = {"updated": {}}
            push_subscription.renew_expiring_push_subscriptions()

        self.assertEqual(service.get.call_count, 1)
        log_mail_error.assert_not_called()
        return service, add

    def test_expiring_subscription_is_renewed_from_the_shared_fetch(self):
        expiring = (get_utc_now() + timedelta(days=1)).isoformat()
        service, add = self._run(
            [
                {"id": "site-sub", "deviceClientId": "site-device", "expires": "2999-01-01T00:00:00Z"},
                {"id": "exp-1", "deviceClientId": "other-device", "expires": expiring},
            ]
        )

        service.update.assert_called_once_with([{"id": "exp-1"}])
        add.assert_not_called()

    def test_deleted_expired_subscription_is_not_renewed(self):
        service, add = self._run(
            [{"id": "sub-old", "deviceClientId": "site-device", "expires": "2000-01-01T00:00:00Z"}]
        )

        service.delete.assert_called_once_with(["sub-old"])
        add.assert_called_once_with(USER, ignore_permissions=True)
        service.update.assert_not_called()


class OnLogin(unittest.TestCase):
    def _run(self, user: str, jmap_configured: bool = True) -> mock.Mock:
        login_manager = mock.MagicMock()
        login_manager.user = user
        with (
            mock.patch.object(push_subscription, "is_jmap_configured", return_value=jmap_configured),
            mock.patch.object(push_subscription, "enqueue_job") as enqueue_job,
        ):
            push_subscription.on_login(login_manager)

        return enqueue_job

    def test_enqueues_healing_for_jmap_user(self):
        enqueue_job = self._run(USER)

        enqueue_job.assert_called_once()
        self.assertIs(enqueue_job.call_args.args[0], push_subscription.ensure_push_subscription)
        self.assertEqual(enqueue_job.call_args.kwargs["user"], USER)

    def test_skips_guest_and_administrator(self):
        self._run("Guest").assert_not_called()
        self._run("Administrator").assert_not_called()

    def test_skips_users_without_jmap(self):
        self._run(USER, jmap_configured=False).assert_not_called()
