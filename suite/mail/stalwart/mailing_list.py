from dataclasses import dataclass

import frappe
from frappe import _

from suite.mail.stalwart.account import EmailAlias
from suite.mail.stalwart.service import ManagementService


@dataclass
class MailingList:
	name: str
	domain_id: str
	recipients: list[str] | None = None
	aliases: list[EmailAlias] | None = None
	description: str | None = None

	def to_dict(self) -> dict:
		"""Serializes the mailing list to the JMAP wire format."""

		return {
			"name": self.name,
			"domainId": self.domain_id,
			# For a mailing list, recipients and aliases are JSON arrays, not id-keyed maps.
			"recipients": list(self.recipients) if self.recipients else [],
			"aliases": [alias.to_dict() for alias in self.aliases] if self.aliases else [],
			"description": self.description,
		}


class MailingListService(ManagementService):
	type = "MailingList"
	default_properties = ["id", "name", "emailAddress", "domainId", "recipients", "aliases", "description"]

	def get_by_name(
		self, name: str, properties: list[str] | None = None, raise_exception: bool = True
	) -> dict | None:
		"""Returns the mailing list with the given name, or ``None`` (throws if ``raise_exception``)."""

		mailing_list = self.find({"name": name}, properties=properties or ["id"])
		if not mailing_list and raise_exception:
			frappe.throw(_("Mailing list {0} not found on the Stalwart server.").format(name))

		return mailing_list
