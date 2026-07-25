import csv
import io
import json
from contextlib import suppress
from typing import Literal

import frappe
from frappe import _
from frappe.query_builder.functions import Max
from frappe.utils import cint, validate_email_address
from pypika import Case, Order

from suite.mail.api.utils import get_avatar_url
from suite.mail.doctype.mail_account_request.mail_account_request import (
	STALWART_DEFAULT_ADMIN_ROLES,
	STALWART_DEFAULT_USER_ROLES,
)
from suite.mail.doctype.user_account.user_account import get_user_personal_jmap_account
from suite.mail.stalwart import (
	add_account_role,
	get_account_service,
	get_dkim_signature_service,
	get_domain_service,
	get_group_service,
	get_mailing_list_service,
	get_oauth_client_service,
	get_role_service,
	remove_account_role,
)
from suite.mail.stalwart import get_domains as get_stalwart_domains
from suite.mail.stalwart.account import CustomRoles, EmailAlias, RoleType, UserRoles
from suite.mail.stalwart.domain import Domain
from suite.mail.stalwart.group import Group
from suite.mail.stalwart.mailing_list import MailingList
from suite.mail.stalwart.oauth import OAuthClient
from suite.mail.stalwart.role import Role
from suite.mail.utils import get_config
from suite.mail.utils.dns import parse_dns_zone_file
from suite.mail.utils.validation import is_subaddressed_email
from suite.utils.rate_limiter import dynamic_rate_limit
from suite.utils import execute_with_logging
from suite.utils.user import is_suite_admin, is_system_manager, is_user_enabled


def check_admin_permission(action: str) -> str:
	"""Ensure the session user is an enabled Suite Admin or System Manager, returning the user.

	The enabled check is defense-in-depth: a disabled admin holding a still-valid session (or an
	API key) must not be able to perform admin actions, e.g. re-enable their own account via
	enable_members. Throws frappe.PermissionError otherwise.
	"""

	user = frappe.session.user
	if (not is_suite_admin(user) and not is_system_manager(user)) or not is_user_enabled(user):
		frappe.throw(_("User {0} does not have permission to {1}.").format(frappe.bold(user), action))

	return user


def _get_stalwart_domain(domain_id: str) -> dict:
	"""Helper function to get a domain by ID from Stalwart, throwing a DoesNotExistError if not found."""

	domains = get_stalwart_domains()
	domain = next((d for d in domains if d["id"] == domain_id), None)

	if not domain:
		frappe.throw(_("Domain not found"), frappe.DoesNotExistError)

	return domain


@frappe.whitelist()
@dynamic_rate_limit()
def add_domain(name: str, description: str | None = None) -> str:
	"""Adds a new domain to Stalwart with the specified name and description, returning the new domain's ID."""

	for domain in get_stalwart_domains():
		if domain["name"].lower() == name.lower():
			frappe.throw(_("Domain {0} already exists.").format(name))

	domain_id = execute_with_logging(
		func=lambda: get_domain_service().create(Domain(name=name, description=description)),
		title=_("Failed to add domain {0}").format(name),
		user_message=_("An error occurred while adding the domain, check error logs for more details."),
		with_context=False,
		module="Mail",
	)

	get_stalwart_domains.clear_cache()
	return domain_id


@frappe.whitelist()
def get_domains(txt: str | None = None, is_enabled: bool | None = None) -> list[dict]:
	"""Returns the list of domains configured in Stalwart, with optional filtering by name/description and enabled status"""

	check_admin_permission("view domains")

	result = []

	with suppress(Exception):
		for domain in get_stalwart_domains():
			if txt and (
				txt.lower() not in domain["name"].lower()
				and txt.lower() not in (domain.get("description") or "").lower()
			):
				continue

			if is_enabled is not None and domain["isEnabled"] != bool(is_enabled):
				continue

			result.append(
				{
					"id": domain["id"],
					"name": domain["name"],
					"description": domain.get("description", ""),
					"is_enabled": domain["isEnabled"],
					"created_at": domain["createdAt"],
				}
			)

	return result


@frappe.whitelist()
def get_domain(domain_id: str) -> dict:
	"""Returns the details of a domain, including its DNS records parsed from the zone file"""

	def infer_category(record: dict) -> str:
		"""Infers the category of the DNS record based on its type and name."""

		t = record["type"]
		name = record["name"]

		if t == "MX":
			return "Receiving"

		if t == "TXT":
			value = record["value"] or ""
			if name.startswith("_dmarc"):
				return "DMARC"
			if "spf1" in value:
				return "Sending"
			if "domainkey" in name:
				return "DKIM"
			if name.startswith("_smtp._tls"):
				return "TLS Reporting"
			return "TXT"

		if t == "CNAME":
			if "autoconfig" in name:
				return "Auto-config"
			if "autodiscover" in name:
				return "Auto-discover"
			return "Alias"

		if t == "SRV":
			if "_imap" in name or "_pop3" in name:
				return "Receiving"
			if "_submission" in name or "_submissions" in name:
				return "Sending"
			return "Server"

		return "Other"

	def is_mandatory(record: dict) -> bool:
		"""Define which DNS records are required."""

		category = record["category"]
		value = record["value"]

		if category == "Sending" and "spf1" in value:
			return True
		if category == "DMARC":
			return True
		if category == "DKIM":
			return True
		if record["type"] == "MX":
			return False

		return False

	domain = _get_stalwart_domain(domain_id)

	default_ttl = get_config("default_dns_ttl")
	dns_records = parse_dns_zone_file(domain["dnsZoneFile"])
	for record in dns_records:
		if not record["ttl"]:
			record["ttl"] = default_ttl
		record["category"] = infer_category(record)
		record["mandatory"] = is_mandatory(record)

	return {
		"id": domain["id"],
		"name": domain["name"],
		"description": domain.get("description", ""),
		"is_enabled": domain["isEnabled"],
		"created_at": domain["createdAt"],
		"dns_records": dns_records,
	}


@frappe.whitelist()
def delete_domain(domain_id: str) -> None:
	"""Deletes a domain identified by Stalwart domain ID."""

	check_admin_permission("delete domains")

	execute_with_logging(
		func=lambda: get_domain_service().delete([domain_id]),
		title=_("Failed to delete domain with ID {0}").format(domain_id),
		user_message=_("An error occurred while deleting the domain, check error logs for more details."),
		with_context=False,
		module="Mail",
	)

	get_stalwart_domains.clear_cache()


@frappe.whitelist()
def get_enabled_domains() -> list[str]:
	"""Returns the list of enabled domains"""

	try:
		return list(set([d["name"] for d in get_stalwart_domains() if d["isEnabled"]]))
	except Exception:
		return []


@frappe.whitelist()
def get_domain_dns_zone(domain_id: str) -> str:
	"""Returns the DNS zone file of the domain"""

	domain = _get_stalwart_domain(domain_id)
	return domain["dnsZoneFile"]


@frappe.whitelist()
def get_domain_dns_csv(domain_id: str) -> str:
	"""Returns the DNS records of the domain as a CSV string"""

	domain = _get_stalwart_domain(domain_id)
	dns_records = parse_dns_zone_file(domain["dnsZoneFile"])

	fieldnames = ["name", "ttl", "class", "type", "value"]

	output = io.StringIO()
	writer = csv.DictWriter(output, fieldnames=fieldnames)
	writer.writeheader()

	for record in dns_records:
		writer.writerow(record)

	return output.getvalue()


@frappe.whitelist()
def get_domain_dns_json(domain_id: str) -> str:
	"""Returns the DNS records of the domain as a JSON object"""

	domain = _get_stalwart_domain(domain_id)
	dns_records = parse_dns_zone_file(domain["dnsZoneFile"])
	return json.dumps(dns_records, indent=4)


@frappe.whitelist()
@dynamic_rate_limit()
def add_member(
	username: str,
	domain: str,
	is_admin: bool,
	send_invite: bool,
	backup_email: str,
	first_name: str | None = None,
	last_name: str | None = None,
	password: str | None = None,
	expires_at: str | None = None,
	aliases: list | None = None,
) -> None:
	"""Create a new Mail Account Request for adding a member.

	``username``/``domain`` are the primary address (becomes the User); ``aliases`` are additional
	full email addresses attached as aliases to the same account.
	"""

	account_request = frappe.new_doc("Mail Account Request")
	account_request.account = f"{username}@{domain}"
	account_request.aliases = "\n".join(_listify(aliases))
	account_request.is_admin = cint(is_admin)
	account_request.invited_by = frappe.session.user
	account_request.backup_email = backup_email
	account_request.send_invite = cint(send_invite)
	account_request.expires_at = expires_at
	account_request.insert()

	if not send_invite:
		account_request.force_verify_and_create_account(first_name, last_name, password)


@frappe.whitelist()
def get_members(
	search: str | None = None, is_admin: bool | None = None, is_enabled: bool | None = None
) -> list:
	check_admin_permission("view members")

	USER = frappe.qb.DocType("User")
	HAS_ROLE = frappe.qb.DocType("Has Role")
	USER_SETTINGS = frappe.qb.DocType("User Settings")

	admin_case = Case().when(HAS_ROLE.role == "Suite Admin", 1).else_(0)
	is_admin_expr = Max(admin_case)

	query = (
		frappe.qb.from_(USER)
		.left_join(HAS_ROLE)
		.on(USER.name == HAS_ROLE.parent)
		.left_join(USER_SETTINGS)
		.on(USER.name == USER_SETTINGS.user)
		.select(
			USER.name,
			USER.full_name,
			USER.user_image,
			USER.last_active,
			USER.enabled,
			is_admin_expr.as_("is_admin"),
		)
		.where(USER_SETTINGS.username.isnotnull())
		.groupby(USER.name)
	)

	if is_enabled is not None:
		query = query.where(USER.enabled == (1 if is_enabled else 0))

	if search:
		query = query.where(USER.name.like(f"%{search}%") | USER.full_name.like(f"%{search}%"))

	if is_admin is not None:
		query = query.having(is_admin_expr == (1 if is_admin else 0))

	users = (
		query.orderby(is_admin_expr, order=Order.desc).orderby(USER.name, order=Order.asc).run(as_dict=True)
	)

	for user in users:
		if not user.get("user_image"):
			user["user_image"] = get_avatar_url(user["name"])

		user["is_admin"] = bool(user.get("is_admin"))
		user["enabled"] = bool(user.get("enabled"))

	return users


def _build_quota_usage(total: int, used: int) -> dict:
	"""Normalizes raw disk-quota byte counts into the shape the member page renders.

	A total of 0 (Stalwart omits maxDiskQuota) means unlimited storage, so percentages and the
	available figure are meaningless and reported as such.
	"""

	total = max(total or 0, 0)
	used = max(used or 0, 0)

	if total <= 0:
		return {
			"total": 0,
			"used": used,
			"available": 0,
			"used_percentage": 0,
			"available_percentage": 0,
			"unlimited": True,
		}

	available = max(total - used, 0)
	used_percentage = min((used / total) * 100, 100)

	return {
		"total": total,
		"used": used,
		"available": available,
		"used_percentage": used_percentage,
		"available_percentage": 100 - used_percentage,
		"unlimited": False,
	}


@frappe.whitelist()
def get_member(member_id: str) -> dict:
	"""Returns a member's profile along with their Stalwart quota usage and email addresses.

	Quota and email addresses are read live from the member's personal Stalwart account via the CLI;
	when the member has no personal account configured, those sections come back empty rather than
	failing the whole page.
	"""

	check_admin_permission("view members")

	user = frappe.db.get_value(
		"User",
		member_id,
		["name", "full_name", "user_image", "last_active", "enabled", "creation"],
		as_dict=True,
	)
	if not user:
		frappe.throw(_("Member not found"), frappe.DoesNotExistError)

	is_admin = bool(frappe.db.exists("Has Role", {"parent": member_id, "role": "Suite Admin"}))

	result = {
		"name": user.name,
		"full_name": user.full_name,
		"user_image": user.user_image or get_avatar_url(user.name),
		"description": user.full_name,
		"last_active": user.last_active,
		"joined_on": user.creation,
		"enabled": bool(user.enabled),
		"is_admin": is_admin,
		"email_addresses": [],
		"groups": [],
		"mailing_lists": [],
		"quota": _build_quota_usage(0, 0),
	}

	account_id = get_user_personal_jmap_account(member_id)
	if not account_id:
		return result

	with suppress(Exception):
		account = get_account_service().get(
			account_id,
			properties=["emailAddress", "aliases", "quotas", "usedDiskQuota", "memberGroupIds", "description"],
		)
		if not account:
			return result

		# Each address carries a description used as its Identity display name: the primary uses the
		# account description, each alias its own.
		email_addresses = []
		if primary := account.get("emailAddress"):
			email_addresses.append(
				{"email": primary, "description": account.get("description"), "is_primary": True}
			)

		aliases = account.get("aliases") or {}
		if aliases:
			domain_names = {d["id"]: d["name"] for d in get_stalwart_domains()}
			for alias in aliases.values():
				name = alias.get("name")
				domain_name = domain_names.get(alias.get("domainId"))
				if name and domain_name:
					email_addresses.append(
						{
							"email": f"{name}@{domain_name}",
							"description": alias.get("description"),
							"is_primary": False,
						}
					)

		emails = [entry["email"] for entry in email_addresses]
		result["email_addresses"] = email_addresses
		result["quota"] = _build_quota_usage(
			(account.get("quotas") or {}).get("maxDiskQuota") or 0,
			account.get("usedDiskQuota") or 0,
		)

		# Groups the account belongs to (membership lives on the account's memberGroupIds).
		group_ids = _keys(account.get("memberGroupIds"))
		if group_ids:
			group_map = {
				g["id"]: g
				for g in get_group_service().get_all_groups(properties=["id", "name", "emailAddress"])
			}
			result["groups"] = [
				{"id": gid, "name": group_map[gid].get("name"), "email": group_map[gid].get("emailAddress")}
				for gid in group_ids
				if gid in group_map
			]

		# Mailing lists that include the member as a recipient. Recipients are email addresses
		# (internal or external), so match against the member's own addresses, not the account id.
		member_emails = {email.lower() for email in emails}
		result["mailing_lists"] = [
			{"id": ml["id"], "name": ml.get("name"), "email": ml.get("emailAddress")}
			for ml in get_mailing_list_service().get_all(
				properties=["id", "name", "emailAddress", "recipients"]
			)
			if member_emails & {recipient.lower() for recipient in _keys(ml.get("recipients"))}
		]

	return result


@frappe.whitelist()
def get_account_requests(
	search: str | None = None, status: Literal["All", "Pending", "Accepted", "Expired"] = "All"
) -> list[dict]:
	"""Returns the list of account invites"""

	check_admin_permission("view account requests")

	ACC_REQ = frappe.qb.DocType("Mail Account Request")
	query = (
		frappe.qb.from_(ACC_REQ)
		.select(
			ACC_REQ.name,
			ACC_REQ.account,
			ACC_REQ.is_admin,
			ACC_REQ.backup_email,
			ACC_REQ.invited_by,
			ACC_REQ.is_verified,
		)
		.orderby(ACC_REQ.creation, order=Order.desc)
	)

	if search:
		query = query.where(ACC_REQ.account.like(f"%{search}%"))

	if status == "Pending":
		query = query.where((ACC_REQ.is_verified == 0) & (ACC_REQ.expires_at > frappe.utils.now()))
	elif status == "Accepted":
		query = query.where(ACC_REQ.is_verified == 1)
	elif status == "Expired":
		query = query.where((ACC_REQ.is_verified == 0) & (ACC_REQ.expires_at <= frappe.utils.now()))

	invites = query.run(as_dict=True)

	return invites


@frappe.whitelist()
def delete_account_requests(names: list) -> None:
	"""Delete Mail Account Requests"""

	check_admin_permission("delete account requests")

	for d in names:
		frappe.delete_doc("Mail Account Request", d)


@frappe.whitelist()
def delete_members(names: list) -> None:
	"""Delete member users. The User on_trash hooks cascade to their Stalwart account and settings."""

	user = check_admin_permission("delete members")

	if user in names:
		frappe.throw(_("You cannot delete your own account."))

	for name in names:
		frappe.delete_doc("User", name)


@frappe.whitelist()
def disable_members(names: list) -> None:
	"""Disable member users. Disabled users can no longer log in and their sessions are cleared."""

	user = check_admin_permission("disable members")

	if user in names:
		frappe.throw(_("You cannot disable your own account."))

	for name in names:
		member = frappe.get_doc("User", name)
		if not member.enabled:
			continue

		member.enabled = 0
		member.save(ignore_permissions=True)


@frappe.whitelist()
def enable_members(names: list) -> None:
	"""Enable member users. The configured disabled account role is removed and the users can log in again."""

	check_admin_permission("enable members")

	for name in names:
		member = frappe.get_doc("User", name)
		if member.enabled:
			continue

		member.enabled = 1
		member.save(ignore_permissions=True)


@frappe.whitelist()
@dynamic_rate_limit()
def change_member_password(member_id: str, new_password: str) -> None:
	"""Set a member's password directly.

	Saving the User with `new_password` set triggers the update_account_password hook, which
	propagates the new password to the member's Stalwart account.
	"""

	check_admin_permission("change member password")

	if not new_password:
		frappe.throw(_("New password is required."))

	member = frappe.get_doc("User", member_id)
	member.new_password = new_password
	member.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Member editing (Frappe User + Stalwart account)
# ---------------------------------------------------------------------------

_GB = 1024**3


def _member_account(member_id: str) -> str | None:
	"""Returns the member's personal Stalwart account id, or None if they have none."""

	return get_user_personal_jmap_account(member_id, raise_exception=False)


def _require_member_account(member_id: str) -> str:
	account_id = _member_account(member_id)
	if not account_id:
		frappe.throw(_("This member does not have a mail account."))

	return account_id


def _alias_emails(account: dict, domain_names: dict) -> list[str]:
	"""Builds the account's alias email addresses from its raw ``aliases`` map."""

	emails = []
	for alias in (account.get("aliases") or {}).values():
		name = alias.get("name")
		domain = domain_names.get(alias.get("domainId"))
		if name and domain:
			emails.append(f"{name}@{domain}")

	return emails


def _rebuild_aliases(account: dict, *, keep: callable) -> list[EmailAlias]:
	"""Rebuilds the account's alias objects, keeping those for which ``keep(email)`` is True."""

	domain_names = {d["id"]: d["name"] for d in get_stalwart_domains()}
	aliases = []
	for alias in (account.get("aliases") or {}).values():
		domain = domain_names.get(alias.get("domainId"))
		email = f"{alias.get('name')}@{domain}" if domain else None
		if email and not keep(email.lower()):
			continue

		aliases.append(
			EmailAlias(
				name=alias["name"],
				domain_id=alias["domainId"],
				enabled=alias.get("enabled", True),
				description=alias.get("description"),
			)
		)

	return aliases


@frappe.whitelist()
def update_member(
	member_id: str,
	role: str | None = None,
	description: str | None = None,
	quota_gb: float | None = None,
) -> None:
	"""Updates a member's role, display name and quota on both Frappe and Stalwart."""

	check_admin_permission("update members")

	member = frappe.get_doc("User", member_id)

	if role is not None:
		if role == "admin":
			member.append_roles("Suite Admin")
		else:
			member.set("roles", [r for r in member.get("roles") if r.role != "Suite Admin"])

	description = (description or "").strip()
	if description:
		first, _sep, last = description.partition(" ")
		member.first_name = first
		member.last_name = last or None

	member.save(ignore_permissions=True)

	account_id = _member_account(member_id)
	account_service = get_account_service()

	# Role: the base "User" Stalwart role always stays; only the admin-only roles are toggled.
	if role is not None:
		extra_roles = list(set(STALWART_DEFAULT_ADMIN_ROLES) - set(STALWART_DEFAULT_USER_ROLES))
		toggle = add_account_role if role == "admin" else remove_account_role
		execute_with_logging(
			func=lambda: [toggle(member_id, r) for r in extra_roles],
			title=_("Failed to update roles for {0}").format(member_id),
			user_message=_("An error occurred while updating the role, check error logs for more details."),
			with_context=False,
			module="Mail",
		)

	if not account_id:
		return

	if description:
		execute_with_logging(
			func=lambda: account_service.update(account_id, {"description": description}),
			title=_("Failed to update description for {0}").format(member_id),
			user_message=_("An error occurred while updating the description, check error logs for more details."),
			with_context=False,
			module="Mail",
		)

	if quota_gb is not None:
		quota_bytes = cint(float(quota_gb) * _GB)
		execute_with_logging(
			func=lambda: account_service.update(account_id, {"quotas/maxDiskQuota": quota_bytes}),
			title=_("Failed to update quota for {0}").format(member_id),
			user_message=_("An error occurred while updating the quota, check error logs for more details."),
			with_context=False,
			module="Mail",
		)


@frappe.whitelist()
def add_member_email(member_id: str, email: str, description: str | None = None) -> None:
	"""Adds an email address to the member's account as an alias with an optional description."""

	check_admin_permission("update members")
	account_id = _require_member_account(member_id)

	email = (email or "").strip().lower()
	validate_email_address(email, throw=True)
	is_subaddressed_email(email, raise_exception=True)

	local, _sep, domain = email.partition("@")
	domain_id = get_domain_service().get_by_name(domain, raise_exception=True)["id"]

	account_service = get_account_service()
	account = account_service.get(account_id, properties=["emailAddress", "aliases"])
	if email == (account.get("emailAddress") or "").lower():
		frappe.throw(_("{0} is already the primary address.").format(email))

	domain_names = {d["id"]: d["name"] for d in get_stalwart_domains()}
	if email in {e.lower() for e in _alias_emails(account, domain_names)}:
		return

	aliases = _rebuild_aliases(account, keep=lambda _e: True)
	aliases.append(EmailAlias(name=local, domain_id=domain_id, description=(description or "").strip() or None))

	execute_with_logging(
		func=lambda: account_service.set_aliases(account_id, aliases),
		title=_("Failed to add email {0}").format(email),
		user_message=_("An error occurred while adding the email, check error logs for more details."),
		with_context=False,
		module="Mail",
	)


@frappe.whitelist()
def remove_member_email(member_id: str, email: str) -> None:
	"""Removes an alias email address from the member's account (the primary cannot be removed)."""

	check_admin_permission("update members")
	account_id = _require_member_account(member_id)

	email = (email or "").strip().lower()
	account_service = get_account_service()
	account = account_service.get(account_id, properties=["emailAddress", "aliases"])
	if email == (account.get("emailAddress") or "").lower():
		frappe.throw(_("The primary address cannot be removed."))

	aliases = _rebuild_aliases(account, keep=lambda e: e != email)

	execute_with_logging(
		func=lambda: account_service.set_aliases(account_id, aliases),
		title=_("Failed to remove email {0}").format(email),
		user_message=_("An error occurred while removing the email, check error logs for more details."),
		with_context=False,
		module="Mail",
	)


@frappe.whitelist()
def add_member_to_groups(member_id: str, group_ids: list) -> None:
	"""Adds the member to the given groups."""

	check_admin_permission("update members")
	account_id = _require_member_account(member_id)

	service = get_group_service()
	for group_id in _listify(group_ids):
		service.add_members(group_id, [account_id])


@frappe.whitelist()
def remove_member_from_group(member_id: str, group_id: str) -> None:
	"""Removes the member from the given group."""

	check_admin_permission("update members")
	account_id = _require_member_account(member_id)
	get_group_service().remove_members(group_id, [account_id])


@frappe.whitelist()
def add_member_to_mailing_lists(member_id: str, list_ids: list) -> None:
	"""Adds the member's primary address as a recipient of the given mailing lists."""

	check_admin_permission("update members")
	account_id = _require_member_account(member_id)

	account_service = get_account_service()
	email = (account_service.get(account_id, properties=["emailAddress"]) or {}).get("emailAddress")
	if not email:
		return

	service = get_mailing_list_service()
	for list_id in _listify(list_ids):
		recipients = dict((service.get(list_id, properties=["recipients"]) or {}).get("recipients") or {})
		recipients[email] = True
		service.update(list_id, {"recipients": recipients})


@frappe.whitelist()
def remove_member_from_mailing_list(member_id: str, list_id: str) -> None:
	"""Removes all of the member's addresses from the given mailing list's recipients."""

	check_admin_permission("update members")
	account_id = _require_member_account(member_id)

	account_service = get_account_service()
	account = account_service.get(account_id, properties=["emailAddress", "aliases"])
	domain_names = {d["id"]: d["name"] for d in get_stalwart_domains()}
	member_emails = {(account.get("emailAddress") or "").lower(), *[e.lower() for e in _alias_emails(account, domain_names)]}

	service = get_mailing_list_service()
	recipients = (service.get(list_id, properties=["recipients"]) or {}).get("recipients") or {}
	remaining = {r: v for r, v in recipients.items() if r.lower() not in member_emails}
	service.update(list_id, {"recipients": remaining})


# ---------------------------------------------------------------------------
# Directory: shared helpers
# ---------------------------------------------------------------------------


def _listify(value) -> list:
	"""Coerces a whitelisted argument (which may arrive as a JSON string) into a list."""

	if value is None:
		return []
	if isinstance(value, str):
		value = frappe.parse_json(value)
	return list(value or [])


def _keys(value) -> list[str]:
	"""Returns the keys of a JMAP id-keyed map, or the list as-is."""

	return list(value.keys()) if isinstance(value, dict) else list(value or [])


def _search(rows: list[dict], search: str | None, fields: tuple[str, ...]) -> list[dict]:
	"""Filters rows whose given fields contain the search text (case-insensitive)."""

	if not search:
		return rows

	needle = search.lower()
	return [r for r in rows if any(needle in (str(r.get(f) or "")).lower() for f in fields)]


@frappe.whitelist()
def get_accounts(search: str | None = None) -> list[dict]:
	"""Returns Stalwart user accounts (id + email) for member/recipient pickers."""

	check_admin_permission("view accounts")

	accounts = get_account_service().get_all(
		filter={"@type": "User"}, properties=["id", "name", "emailAddress"]
	)
	rows = [{"id": a["id"], "name": a.get("name"), "email": a.get("emailAddress")} for a in accounts]
	return _search(rows, search, ("name", "email"))


# ---------------------------------------------------------------------------
# Directory: Groups
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_groups(search: str | None = None) -> list[dict]:
	"""Returns all groups."""

	check_admin_permission("view groups")

	groups = get_group_service().get_all_groups(
		properties=["id", "name", "emailAddress", "description", "createdAt"]
	)
	rows = [
		{
			"id": g["id"],
			"name": g.get("name"),
			"email": g.get("emailAddress"),
			"description": g.get("description"),
			"created_at": g.get("createdAt"),
		}
		for g in groups
	]
	return _search(rows, search, ("name", "email", "description"))


@frappe.whitelist()
def get_group(group_id: str) -> dict:
	"""Returns a group with its members and assigned role ids."""

	check_admin_permission("view groups")

	service = get_group_service()
	group = service.get(group_id)
	if not group:
		frappe.throw(_("Group not found"), frappe.DoesNotExistError)

	members = service.get_members(group_id, properties=["id", "name", "emailAddress"])

	return {
		"id": group["id"],
		"name": group.get("name"),
		"email": group.get("emailAddress"),
		"description": group.get("description"),
		"created_at": group.get("createdAt"),
		"role_ids": _keys((group.get("roles") or {}).get("roleIds")),
		"members": [{"id": m["id"], "name": m.get("name"), "email": m.get("emailAddress")} for m in members],
	}


@frappe.whitelist()
@dynamic_rate_limit()
def add_group(
	name: str,
	domain: str,
	description: str | None = None,
	members: list | None = None,
	roles: list | None = None,
) -> str:
	"""Creates a group and returns its id. ``members`` and ``roles`` are account/role ids."""

	check_admin_permission("add groups")

	member_ids = _listify(members)
	role_ids = _listify(roles)

	def _create() -> str:
		domain_id = get_domain_service().get_by_name(domain, raise_exception=True)["id"]
		service = get_group_service()
		group_id = service.create(
			Group(name=name, domain_id=domain_id, description=description, role_ids=role_ids or None)
		)
		if member_ids:
			service.add_members(group_id, member_ids)
		return group_id

	return execute_with_logging(
		func=_create,
		title=_("Failed to add group {0}").format(name),
		user_message=_("An error occurred while adding the group, check error logs for more details."),
		with_context=False,
		module="Mail",
	)


@frappe.whitelist()
def update_group(
	group_id: str,
	name: str | None = None,
	description: str | None = None,
	members: list | None = None,
	roles: list | None = None,
) -> None:
	"""Updates a group's name/description/members/roles."""

	check_admin_permission("update groups")

	service = get_group_service()

	patch = {}
	if name is not None:
		patch["name"] = name
	if description is not None:
		patch["description"] = description
	if roles is not None:
		role_ids = _listify(roles)
		patch["roles"] = (
			UserRoles(type=RoleType.CUSTOM, roles=CustomRoles(role_ids=role_ids)).to_dict()
			if role_ids
			else {"@type": "Default"}
		)

	if patch:
		service.update(group_id, patch)
	if members is not None:
		service.set_members(group_id, _listify(members))


@frappe.whitelist()
def delete_groups(ids: list) -> None:
	"""Deletes the given groups."""

	check_admin_permission("delete groups")
	get_group_service().delete(_listify(ids))


# ---------------------------------------------------------------------------
# Directory: Mailing Lists
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_mailing_lists(search: str | None = None) -> list[dict]:
	"""Returns all mailing lists."""

	check_admin_permission("view mailing lists")

	lists = get_mailing_list_service().get_all(
		properties=["id", "name", "emailAddress", "description", "createdAt"]
	)
	rows = [
		{
			"id": ml["id"],
			"name": ml.get("name"),
			"email": ml.get("emailAddress"),
			"description": ml.get("description"),
			"created_at": ml.get("createdAt"),
		}
		for ml in lists
	]
	return _search(rows, search, ("name", "email", "description"))


@frappe.whitelist()
def get_mailing_list(list_id: str) -> dict:
	"""Returns a mailing list with its recipients."""

	check_admin_permission("view mailing lists")

	ml = get_mailing_list_service().get(list_id)
	if not ml:
		frappe.throw(_("Mailing list not found"), frappe.DoesNotExistError)

	return {
		"id": ml["id"],
		"name": ml.get("name"),
		"email": ml.get("emailAddress"),
		"description": ml.get("description"),
		"created_at": ml.get("createdAt"),
		# Recipients are email addresses (internal accounts or external).
		"recipients": _keys(ml.get("recipients")),
	}


@frappe.whitelist()
@dynamic_rate_limit()
def add_mailing_list(
	name: str, domain: str, recipients: list | None = None, description: str | None = None
) -> str:
	"""Creates a mailing list and returns its id."""

	check_admin_permission("add mailing lists")

	recipient_list = _listify(recipients)

	def _create() -> str:
		domain_id = get_domain_service().get_by_name(domain, raise_exception=True)["id"]
		return get_mailing_list_service().create(
			MailingList(
				name=name, domain_id=domain_id, recipients=recipient_list or None, description=description
			)
		)

	return execute_with_logging(
		func=_create,
		title=_("Failed to add mailing list {0}").format(name),
		user_message=_("An error occurred while adding the mailing list, check error logs for more details."),
		with_context=False,
		module="Mail",
	)


@frappe.whitelist()
def update_mailing_list(
	list_id: str,
	name: str | None = None,
	description: str | None = None,
	recipients: list | None = None,
) -> None:
	"""Updates a mailing list's name/description/recipients."""

	check_admin_permission("update mailing lists")

	patch = {}
	if name is not None:
		patch["name"] = name
	if description is not None:
		patch["description"] = description
	if recipients is not None:
		patch["recipients"] = {email: True for email in _listify(recipients)}

	if patch:
		get_mailing_list_service().update(list_id, patch)


@frappe.whitelist()
def delete_mailing_lists(ids: list) -> None:
	"""Deletes the given mailing lists."""

	check_admin_permission("delete mailing lists")
	get_mailing_list_service().delete(_listify(ids))


# ---------------------------------------------------------------------------
# Directory: Roles
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_roles_list(search: str | None = None) -> list[dict]:
	"""Returns all roles with permission counts."""

	check_admin_permission("view roles")

	roles = get_role_service().get_all()
	rows = [
		{
			"id": r["id"],
			"description": r.get("description"),
			"enabled_count": len(_keys(r.get("enabledPermissions"))),
			"disabled_count": len(_keys(r.get("disabledPermissions"))),
		}
		for r in roles
	]
	return _search(rows, search, ("description",))


@frappe.whitelist()
def get_role(role_id: str) -> dict:
	"""Returns a role with its permissions and inherited role ids."""

	check_admin_permission("view roles")

	role = get_role_service().get(role_id)
	if not role:
		frappe.throw(_("Role not found"), frappe.DoesNotExistError)

	return {
		"id": role["id"],
		"description": role.get("description"),
		"enabled_permissions": _keys(role.get("enabledPermissions")),
		"disabled_permissions": _keys(role.get("disabledPermissions")),
		"role_ids": _keys(role.get("roleIds")),
	}


@frappe.whitelist()
def get_permissions() -> list[str]:
	"""Returns the assignable permission keys for the role editor."""

	check_admin_permission("view roles")
	return get_role_service().get_permissions()


@frappe.whitelist()
@dynamic_rate_limit()
def add_role(
	description: str,
	enabled_permissions: list | None = None,
	disabled_permissions: list | None = None,
	role_ids: list | None = None,
) -> str:
	"""Creates a role and returns its id."""

	check_admin_permission("add roles")

	def _create() -> str:
		return get_role_service().create(
			Role(
				description=description,
				enabled_permissions=_listify(enabled_permissions),
				disabled_permissions=_listify(disabled_permissions),
				role_ids=_listify(role_ids),
			)
		)

	return execute_with_logging(
		func=_create,
		title=_("Failed to add role {0}").format(description),
		user_message=_("An error occurred while adding the role, check error logs for more details."),
		with_context=False,
		module="Mail",
	)


@frappe.whitelist()
def update_role(
	role_id: str,
	description: str | None = None,
	enabled_permissions: list | None = None,
	disabled_permissions: list | None = None,
	role_ids: list | None = None,
) -> None:
	"""Updates a role's description/permissions/inherited roles."""

	check_admin_permission("update roles")

	patch = {}
	if description is not None:
		patch["description"] = description
	if enabled_permissions is not None:
		patch["enabledPermissions"] = {p: True for p in _listify(enabled_permissions)}
	if disabled_permissions is not None:
		patch["disabledPermissions"] = {p: True for p in _listify(disabled_permissions)}
	if role_ids is not None:
		patch["roleIds"] = {rid: True for rid in _listify(role_ids)}

	if patch:
		get_role_service().update(role_id, patch)


@frappe.whitelist()
def delete_roles(ids: list) -> None:
	"""Deletes the given roles."""

	check_admin_permission("delete roles")
	get_role_service().delete(_listify(ids))


# ---------------------------------------------------------------------------
# Directory: OAuth Clients
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_oauth_clients(search: str | None = None) -> list[dict]:
	"""Returns all OAuth clients."""

	check_admin_permission("view oauth clients")

	clients = get_oauth_client_service().get_all(
		properties=["id", "clientId", "description", "createdAt"]
	)
	rows = [
		{
			"id": c["id"],
			"client_id": c.get("clientId"),
			"description": c.get("description"),
			"created_at": c.get("createdAt"),
		}
		for c in clients
	]
	return _search(rows, search, ("client_id", "description"))


@frappe.whitelist()
def get_oauth_client(client_id: str) -> dict:
	"""Returns an OAuth client with its redirect URIs and contacts."""

	check_admin_permission("view oauth clients")

	client = get_oauth_client_service().get(client_id)
	if not client:
		frappe.throw(_("OAuth client not found"), frappe.DoesNotExistError)

	return {
		"id": client["id"],
		"client_id": client.get("clientId"),
		"description": client.get("description"),
		"created_at": client.get("createdAt"),
		"expires_at": client.get("expiresAt"),
		"redirect_uris": _keys(client.get("redirectUris")),
		"contacts": _keys(client.get("contacts")),
	}


@frappe.whitelist()
@dynamic_rate_limit()
def add_oauth_client(
	client_id: str,
	description: str | None = None,
	redirect_uris: list | None = None,
	contacts: list | None = None,
	expires_at: str | None = None,
) -> str:
	"""Creates an OAuth client and returns its id."""

	check_admin_permission("add oauth clients")

	uris = _listify(redirect_uris)
	contact_list = _listify(contacts)

	def _create() -> str:
		return get_oauth_client_service().create(
			OAuthClient(
				client_id=client_id,
				description=description,
				redirect_uris=uris or None,
				contacts=contact_list or None,
				expires_at=expires_at or None,
			)
		)

	return execute_with_logging(
		func=_create,
		title=_("Failed to add OAuth client {0}").format(client_id),
		user_message=_("An error occurred while adding the OAuth client, check error logs for more details."),
		with_context=False,
		module="Mail",
	)


@frappe.whitelist()
def update_oauth_client(
	oauth_client_id: str,
	description: str | None = None,
	redirect_uris: list | None = None,
	contacts: list | None = None,
) -> None:
	"""Updates an OAuth client's description/redirect URIs/contacts."""

	check_admin_permission("update oauth clients")

	patch = {}
	if description is not None:
		patch["description"] = description
	if redirect_uris is not None:
		patch["redirectUris"] = {uri: True for uri in _listify(redirect_uris)}
	if contacts is not None:
		patch["contacts"] = {contact: True for contact in _listify(contacts)}

	if patch:
		get_oauth_client_service().update(oauth_client_id, patch)


@frappe.whitelist()
def delete_oauth_clients(ids: list) -> None:
	"""Deletes the given OAuth clients."""

	check_admin_permission("delete oauth clients")
	get_oauth_client_service().delete(_listify(ids))


# ---------------------------------------------------------------------------
# Domains: DKIM Signatures
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_dkim_signatures(domain_id: str | None = None) -> list[dict]:
	"""Returns DKIM signatures, optionally scoped to a single domain."""

	check_admin_permission("view dkim signatures")

	service = get_dkim_signature_service()
	signatures = (
		service.get_all_by_domain(domain_id) if domain_id else service.get_all()
	)

	domain_names = {d["id"]: d["name"] for d in get_stalwart_domains()}
	return [
		{
			"id": s["id"],
			"selector": s.get("selector"),
			"domain": domain_names.get(s.get("domainId")),
			"domain_id": s.get("domainId"),
			"stage": s.get("stage"),
		}
		for s in signatures
	]


@frappe.whitelist()
def delete_dkim_signatures(ids: list) -> None:
	"""Deletes the given DKIM signatures."""

	check_admin_permission("delete dkim signatures")
	get_dkim_signature_service().delete(_listify(ids))
