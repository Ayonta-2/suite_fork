from suite.mail.stalwart.service import ManagementService


class LogService(ManagementService):
	"""Read access to server log entries (``x:Log``)."""

	type = "Log"
	default_properties = ["id", "timestamp", "level", "event", "details"]
