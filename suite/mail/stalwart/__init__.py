import frappe
from frappe import _
from frappe.utils import random_string
from frappe.utils.caching import redis_cache

from suite.mail.doctype.user_account.user_account import get_user_personal_jmap_account
from suite.mail.stalwart.account import (
	Account,
	AccountService,
	Credential,
	CustomRoles,
	EmailAlias,
	PasswordCredential,
	RoleType,
	StorageQuota,
	UserRoles,
)
from suite.mail.stalwart.app_password import AppPassword, AppPasswordService
from suite.mail.stalwart.connection import get_account_management_connection, get_management_connection
from suite.mail.stalwart.domain import Domain, DomainService
from suite.mail.stalwart.group import Group, GroupService
from suite.mail.stalwart.mailing_list import MailingList, MailingListService
from suite.mail.stalwart.oauth import OAuthClient, OAuthClientService
from suite.mail.stalwart.role import Role, RoleService
from suite.mail.stalwart.service import ManagementService
from suite.utils.dt import utcnow

__all__ = [
	"Account",
	"AccountService",
	"AppPassword",
	"AppPasswordService",
	"Domain",
	"DomainService",
	"Group",
	"GroupService",
	"MailingList",
	"MailingListService",
	"ManagementService",
	"OAuthClient",
	"OAuthClientService",
	"Role",
	"RoleService",
]


# --- service factories -----------------------------------------------------


def get_account_service() -> AccountService:
	"""Returns an AccountService bound to the admin management connection."""

	return AccountService(get_management_connection())


def get_group_service() -> GroupService:
	"""Returns a GroupService bound to the admin management connection."""

	return GroupService(get_management_connection())


def get_domain_service() -> DomainService:
	"""Returns a DomainService bound to the admin management connection."""

	return DomainService(get_management_connection())


def get_role_service() -> RoleService:
	"""Returns a RoleService bound to the admin management connection."""

	return RoleService(get_management_connection())


def get_mailing_list_service() -> MailingListService:
	"""Returns a MailingListService bound to the admin management connection."""

	return MailingListService(get_management_connection())


def get_oauth_client_service() -> OAuthClientService:
	"""Returns an OAuthClientService bound to the admin management connection."""

	return OAuthClientService(get_management_connection())


def get_app_password_service(account: str) -> AppPasswordService:
	"""App passwords are account-scoped, so the returned service authenticates as ``account``."""

	return AppPasswordService(get_account_management_connection(account))


# --- cached lookups + resolvers --------------------------------------------


@redis_cache(ttl=60)
def get_domains() -> list[dict]:
	"""Returns all domains on the server (cached briefly)."""

	return get_domain_service().get_all(
		properties=["id", "name", "description", "isEnabled", "createdAt", "dnsZoneFile"]
	)


@redis_cache(ttl=3600)
def get_roles(description: str | None = None) -> list[dict]:
	"""Returns roles on the server, optionally filtered by description (cached)."""

	filter = {"description": description} if description else None
	return get_role_service().get_all(filter=filter, properties=["id", "description"])


def resolve_domain_id(name: str, raise_exception: bool = True) -> str | None:
	"""Resolves a domain name to its Stalwart id."""

	domain = get_domain_service().get_by_name(name, raise_exception=raise_exception)
	return domain["id"] if domain else None


def resolve_role_ids(descriptions: list[str] | None) -> list[str]:
	if not descriptions:
		return []

	role_map = {r["description"]: r["id"] for r in get_roles()}

	role_ids = []
	for description in descriptions:
		role_id = role_map.get(description)
		if not role_id:
			frappe.throw(_("Role {0} does not exist on the Stalwart server.").format(description))

		role_ids.append(role_id)

	return role_ids


def _resolve_alias(alias: str) -> tuple[str, str]:
	"""Splits a full email address into its local-part and domain."""

	alias = (alias or "").strip()
	name, _, domain = alias.partition("@")
	if not name or not domain:
		frappe.throw(_("Alias must be a complete email address: {0}").format(alias))

	return name, domain


# --- high-level conveniences used by hooks, doctypes and admin APIs --------


def create_account(
	name: str,
	domain: str,
	password: str | None = None,
	description: str | None = None,
	aliases: list[str] | None = None,
	groups: list[str] | None = None,
	roles: list[str] | None = None,
	quota: int | None = None,
	timezone: str | None = None,
) -> str:
	"""Creates a user account, resolving domain/group/role names to ids."""

	account_service = get_account_service()
	domain_service = get_domain_service()

	domain_id = domain_service.get_by_name(domain, raise_exception=True)["id"]

	email_aliases = []
	domain_ids = {domain: domain_id}
	for alias in aliases or []:
		if not alias:
			continue

		alias_name, alias_domain = _resolve_alias(alias)
		if alias_domain not in domain_ids:
			domain_ids[alias_domain] = domain_service.get_by_name(alias_domain, raise_exception=True)["id"]

		email_aliases.append(EmailAlias(name=alias_name, domain_id=domain_ids[alias_domain]))

	member_group_ids = [
		account_service.get_by_name(group, raise_exception=True)["id"] for group in groups or [] if group
	]

	role_ids = resolve_role_ids(roles)
	user_roles = (
		UserRoles(type=RoleType.CUSTOM, roles=CustomRoles(role_ids=role_ids))
		if role_ids
		else UserRoles(type=RoleType.USER)
	)

	account = Account(
		name=name,
		domain_id=domain_id,
		credentials=[Credential(password=PasswordCredential(secret=password or random_string(12)))],
		member_group_ids=member_group_ids or None,
		roles=user_roles,
		quotas=StorageQuota(max_disk_quota=quota) if quota is not None else StorageQuota(),
		aliases=email_aliases or None,
		description=description,
		timezone=timezone,
	)

	return account_service.create(account)


def create_app_password(account: str, description: str | None = None) -> str:
	"""Creates an app password for ``account`` and returns the generated secret."""

	description = description or f"App Password for {frappe.local.site} - {utcnow()}"
	return get_app_password_service(account).create(AppPassword(description=description))


def update_password(user: str | None = None, new_password: str | None = None) -> None:
	"""Sets the password of the user's personal Stalwart account (no-op if they have none)."""

	if not user or not new_password:
		frappe.throw(_("User and new password are required to update the Stalwart password."))

	if account := get_user_personal_jmap_account(user, raise_exception=False):
		get_account_service().set_password(account, new_password)


def delete_account(user: str) -> None:
	"""Deletes the user's personal Stalwart account (no-op if they have none)."""

	if account := get_user_personal_jmap_account(user, raise_exception=False):
		get_account_service().delete(account)


def add_account_role(user: str, role: str) -> None:
	"""Applies a role (by description) to the user's personal account (no-op if they have none)."""

	if account := get_user_personal_jmap_account(user, raise_exception=False):
		role_id = get_role_service().get_by_description(role, raise_exception=True)["id"]
		get_account_service().add_roles(account, [role_id])


def remove_account_role(user: str, role: str) -> None:
	"""Removes a role (by description) from the user's personal account (no-op if they have none)."""

	if account := get_user_personal_jmap_account(user, raise_exception=False):
		role_id = get_role_service().get_by_description(role, raise_exception=True)["id"]
		get_account_service().remove_roles(account, [role_id])
