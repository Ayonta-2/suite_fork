# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


from uuid import uuid7

import frappe
from frappe import Any, _
from frappe.model.document import Document
from frappe.utils import (
	add_to_date,
	cint,
	get_datetime,
	get_url,
	now,
	now_datetime,
	random_string,
	validate_email_address,
)

from suite.mail.stalwart import create_account, create_app_password, get_roles
from suite.mail.utils import get_config, is_stalwart_configured
from suite.mail.utils.validation import is_subaddressed_email
from suite.utils import execute_with_logging
from suite.utils.user import is_suite_admin, is_system_manager

STALWART_DEFAULT_USER_ROLES = ["User"]
STALWART_DEFAULT_ADMIN_ROLES = ["User", "Tenant Administrator"]


class MailAccountRequest(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		account: DF.Data
		aliases: DF.SmallText | None
		backup_email: DF.Data
		expires_at: DF.Datetime | None
		invited_by: DF.Link
		ip_address: DF.Data | None
		is_admin: DF.Check
		is_verified: DF.Check
		request_key: DF.Data | None
		roles: DF.SmallText | None
		send_invite: DF.Check
	# end: auto-generated types

	def autoname(self) -> None:
		self.name = str(uuid7())

	@property
	def is_expired(self) -> bool:
		return self.expires_at and get_datetime(self.expires_at) < now_datetime()

	@property
	def _roles(self) -> list[str]:
		"""Returns the list of roles for the account request."""

		roles = []

		if self.roles:
			roles = [r.strip() for r in self.roles.split("\n")]

		else:
			if self.is_admin:
				roles = STALWART_DEFAULT_ADMIN_ROLES
			else:
				roles = STALWART_DEFAULT_USER_ROLES

		return list(set(roles))

	@property
	def domain(self) -> str:
		"""Returns the domain of the primary account."""

		return self.account.split("@", 1)[1] if self.account and "@" in self.account else ""

	@property
	def _aliases(self) -> list[str]:
		"""Returns the additional email addresses to attach as aliases to the account."""

		if not self.aliases:
			return []

		return [alias.strip() for alias in self.aliases.split("\n") if alias.strip()]

	def before_insert(self) -> None:
		is_stalwart_configured(raise_exception=True)
		self.validate_backup_email()
		self.set_request_key()
		self.set_expires_at()
		self.set_ip_address()
		self.validate_invited_by()
		self.validate_account()
		self.validate_aliases()
		self.validate_roles()

	def after_insert(self) -> None:
		if self.send_invite:
			self.send_verification_email()

	def validate_backup_email(self) -> None:
		"""Validates the backup email."""

		if not self.backup_email:
			frappe.throw(_("Backup Email is required."))

		self.backup_email = self.backup_email.strip().lower()
		validate_email_address(self.backup_email, throw=True)

	def set_request_key(self) -> None:
		"""Sets a random key for the request."""

		self.request_key = random_string(32)

	def set_expires_at(self) -> None:
		"""Sets the expiry date of the account request."""

		if not self.expires_at:
			self.expires_at = add_to_date(now(), days=1)

	def set_ip_address(self) -> None:
		"""Sets the IP address of the request."""

		self.ip_address = frappe.local.request_ip

	def validate_invited_by(self) -> None:
		"""Validates the invited_by."""

		user = frappe.session.user

		if is_system_manager(user):
			self.invited_by = self.invited_by or user
		else:
			self.invited_by = user

	def validate_account(self) -> None:
		"""Validates the primary account email."""

		self.account = self.account.strip().lower()
		validate_email_address(self.account, throw=True)
		is_subaddressed_email(self.account, raise_exception=True)

		if frappe.db.exists("User", {"email": self.account}):
			frappe.throw(_("User with email {0} already exists.").format(frappe.bold(self.account)))

	def validate_aliases(self) -> None:
		"""Validates the additional email aliases and normalizes them.

		Each alias must be a valid, non-subaddressed email on a domain that exists on the server.
		Blanks, duplicates and any alias equal to the primary account are dropped.
		"""

		if not self.aliases:
			return

		from suite.mail.stalwart import get_domains

		server_domains = {domain["name"] for domain in get_domains()}

		seen = set()
		cleaned = []
		for alias in self.aliases.split("\n"):
			alias = alias.strip().lower()
			if not alias or alias == self.account or alias in seen:
				continue

			validate_email_address(alias, throw=True)
			is_subaddressed_email(alias, raise_exception=True)

			domain = alias.split("@", 1)[1]
			if domain not in server_domains:
				frappe.throw(_("Alias domain {0} does not exist on the server.").format(frappe.bold(domain)))

			seen.add(alias)
			cleaned.append(alias)

		self.aliases = "\n".join(cleaned)

	def validate_roles(self) -> None:
		"""Validates the roles."""

		roles_to_assign = self._roles
		server_roles_map = {r["description"]: r["id"] for r in get_roles()}

		for role in roles_to_assign:
			if role not in server_roles_map:
				frappe.throw(_("Role {0} does not exists on the server.").format(frappe.bold(role)))

		self.roles = "\n".join(roles_to_assign)

	def validate_expired(self) -> None:
		"""Forbids action if the request has expired."""

		if self.is_expired:
			frappe.throw(_("This request has expired. Please create a new one."))

	@frappe.whitelist()
	def send_verification_email(self) -> None:
		"""Send verification email to the user."""

		self.validate_expired()
		self.validate_backup_email()

		if self.invited_by:
			subject = _("You have been invited by {0} to join Frappe Mail").format(self.invited_by)
			template = "generic"
			args = {
				"title": _("You have been invited by {0} to join Frappe Mail.").format(self.invited_by),
				"description": _("Please confirm your email address by clicking the button below."),
				"button": _("Verify Account"),
				"link": get_url("/mail/signup/" + self.request_key),
			}

			frappe.sendmail(
				recipients=self.backup_email,
				subject=subject,
				template=template,
				args=args,
				now=True,
			)
			frappe.msgprint(_("Verification email sent successfully."), indicator="green", alert=True)

	@frappe.whitelist()
	def force_verify_and_create_account(self, first_name: str, last_name: str, password: str) -> None:
		"""Force verify and create account for invited user."""

		user = frappe.session.user
		if not is_system_manager(user) and not is_suite_admin(user):
			frappe.throw(_("You are not authorized to perform this action."))

		if self.is_verified:
			frappe.throw(_("This account request is already verified."))

		self.db_set("is_verified", 1)
		self.create_account(first_name, last_name, password)

	def create_account(self, first_name: str, last_name: str, password: str) -> None:
		"""Create mail account for the user."""

		if not self.is_verified:
			frappe.throw(_("Account request is not verified. Please verify your email first."))

		if not password:
			frappe.throw(_("Password is required to create account."))

		self.validate_expired()

		is_stalwart_configured(raise_exception=True)
		self.validate_account()

		# Step - 1: Create Account on Stalwart
		execute_with_logging(
			func=lambda: create_account(
				name=self.account.split("@")[0],
				domain=self.domain,
				password=password,
				description=f"{first_name} {last_name}" if last_name else first_name,
				aliases=self._aliases,
				groups=[],
				roles=self._roles,
				quota=cint(get_config("default_disk_quota_gb")) * 1024**3,
				timezone=None,
			),
			title="Failed to create account on Stalwart",
			user_message=_("Failed to create account on the server, check error log for details."),
			module="Mail",
		)

		# Step - 2: Create App Password on Stalwart
		app_password = execute_with_logging(
			func=lambda: create_app_password(self.account),
			title="Failed to create app password on Stalwart",
			user_message=_("Failed to create app password on the server, check error log for details."),
			module="Mail",
		)

		# Step - 3: Create User
		user = execute_with_logging(
			func=lambda: create_user(
				self.account,
				first_name,
				last_name,
				password,
				["Suite User", "Suite Admin"] if self.is_admin else ["Suite User"],
			),
			title="Failed to create user",
			user_message=_("Failed to create user, check error log for details."),
			module="Mail",
		)

		# Step - 4: Update User Settings
		execute_with_logging(
			func=lambda: self._update_user_settings(user, app_password),
			title="Failed to update user settings",
			user_message=_("Failed to update user settings, check error log for details."),
			module="Mail",
		)

		# Step - 5: Create Push Subscription
		if frappe.utils.get_url().startswith("https"):
			execute_with_logging(
				func=lambda: self._create_push_subscription(user),
				title="Failed to create push subscription",
				module="Mail",
			)

	def _update_user_settings(self, user: str, app_password: str) -> None:
		"""Updates the user settings with the app password and backup email."""

		user_settings = frappe.get_doc("User Settings", {"user": user})
		user_settings.username = self.account
		user_settings.app_password = app_password
		user_settings.backup_email = self.backup_email
		user_settings.save(ignore_permissions=True)

	def _create_push_subscription(self, user: str) -> None:
		"""Creates a push subscription for the user."""

		ps = frappe.new_doc("Push Subscription")
		ps.user = user
		ps.insert(ignore_permissions=True)


def create_user(
	email: str,
	first_name: str,
	last_name: str | None = None,
	password: str | None = None,
	roles: list[str] | None = None,
) -> str:
	"""Creates a User document"""

	if frappe.db.exists("User", {"email": email}):
		frappe.throw(_("User with email {0} already exists.").format(frappe.bold(email)))

	user = frappe.new_doc("User")
	user.first_name = first_name
	user.last_name = last_name
	user.username = email
	user.email = email
	user.owner = email
	user.send_welcome_email = 0
	if roles:
		user.append_roles(*roles)
	if password:
		user.new_password = password
	user.insert(ignore_permissions=True)

	return user.name
