import frappe

from suite.drive.utils import STATUS_TRASHED, create_drive_file, get_home_folder


def execute():
	"""Back existing sheets with Drive Files so they show up in Drive, the same
	way sheets created after this change are auto-backed in Sheet.after_insert.

	Only existence/listing is mirrored — sharing stays on the sheet's own
	DocShare model. Idempotent: sheets that already have a backing File are
	skipped, so a re-run (or a sheet created between deploy and patch) is safe.
	"""
	frappe.flags.mute_drive_activity_log = True
	try:
		sheets = frappe.get_all("Sheet", fields=["name", "title", "owner", "trashed"])
		for sheet in sheets:
			if frappe.db.get_value(
				"File", {"content_doctype": "Sheet", "content_docname": sheet.name}, "name"
			):
				continue

			team = frappe.db.get_value("Drive Team", {"owner": sheet.owner, "personal": 1}, "name")
			if not team:
				frappe.log_error(
					title="Sheet left unbacked by Drive File",
					message=(
						f"Sheet {sheet.name} (owner {sheet.owner}) has no personal Drive Team, "
						f"so no Drive File was created; it won't appear in Drive until re-saved."
					),
				)
				continue

			file = create_drive_file(
				team,
				sheet.title or "Untitled Spreadsheet",
				get_home_folder(team).name,
				"Spreadsheet",
				None,
				mime_type="frappe/sheet",
				content_doctype="Sheet",
				content_docname=sheet.name,
				owner=sheet.owner,
			)
			# A trashed sheet's File must land in the trash too, not the listing.
			if sheet.trashed:
				frappe.db.set_value("File", file.name, "status", STATUS_TRASHED, update_modified=False)
	finally:
		frappe.flags.mute_drive_activity_log = False
