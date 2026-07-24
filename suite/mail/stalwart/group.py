from dataclasses import dataclass, field

from suite.mail.stalwart.account import (
	AccountService,
	CustomRoles,
	EmailAlias,
	Permissions,
	RoleType,
	StorageQuota,
	UserRoles,
)


@dataclass
class Group:
	"""A group principal. Groups share the ``x:Account`` object with users but carry no
	credentials and are distinguished by the ``@type: "Group"`` discriminator."""

	name: str
	domain_id: str
	member_group_ids: list[str] | None = None
	role_ids: list[str] | None = None
	permissions: Permissions = field(default_factory=Permissions)
	quotas: StorageQuota = field(default_factory=StorageQuota)
	aliases: list[EmailAlias] | None = None
	description: str | None = None

	def to_dict(self) -> dict:
		"""Serializes the group to the JMAP wire format (an ``x:Account`` with ``@type: Group``)."""

		payload = {
			"@type": "Group",
			"name": self.name,
			"domainId": self.domain_id,
			"memberGroupIds": {group_id: True for group_id in self.member_group_ids}
			if self.member_group_ids
			else {},
			"permissions": self.permissions.to_dict() if self.permissions else {},
			"quotas": self.quotas.to_dict() if self.quotas else {},
			"aliases": {f"{idx}": a.to_dict() for idx, a in enumerate(self.aliases)} if self.aliases else {},
			"description": self.description,
		}

		if self.role_ids:
			payload["roles"] = UserRoles(
				type=RoleType.CUSTOM, roles=CustomRoles(role_ids=self.role_ids)
			).to_dict()

		return payload


class GroupService(AccountService):
	"""Groups live in the same ``x:Account`` collection as users."""

	def get_all_groups(self, properties: list[str] | None = None) -> list[dict]:
		"""Returns every group principal."""

		return self.get_all(filter={"type": "group"}, properties=properties)
