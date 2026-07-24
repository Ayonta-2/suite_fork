import { expect, test } from "../../fixtures/test";
import {
	createFolder,
	openEntityActions,
} from "../../helpers/drive";
import {
	createWriterDocument,
	openWriterDocument,
	uniqueWriterTitle,
	writerEditor,
} from "../../helpers/writer";

test("creating from Drive routes into Writer", async ({ owner }) => {
	await owner.page.goto("/drive/documents");
	await expect(owner.page.getByTestId("drive-app")).toBeVisible();

	await owner.page.locator("#create-button").click();
	await expect(owner.page).toHaveURL(/\/writer\/w\/[^/]+(?:\/|$)/);
	await expect(owner.page.getByTestId("writer-app")).toBeVisible();
	await expect(owner.page.getByTestId("writer-editor")).toBeVisible();
});

test("the same document is visible in Drive and Writer listings", async ({
	owner,
	run,
}) => {
	const title = uniqueWriterTitle(run.run_id, "cross-app");
	const file = await createWriterDocument(owner.page.request, title);

	await owner.page.goto("/drive/documents");
	const driveRow = owner.page.getByTestId(`drive-entity-${file.name}`);
	await expect(driveRow).toBeVisible();
	await expect(driveRow).toContainText(title);

	await owner.page.goto("/writer");
	const writerRow = owner.page.getByTestId(`writer-document-${file.name}`);
	await expect(writerRow).toBeVisible();
	await expect(writerRow).toContainText(title);
});

test("renames, moves, trashes, restores, and reopens a Writer document from Drive", async ({
	owner,
	run,
}) => {
	const title = uniqueWriterTitle(run.run_id, "lifecycle");
	const renamedTitle = `${title} renamed`;
	const folderName = `writer-folder-${run.run_id}-${Date.now()}`;
	const content = `Writer lifecycle content ${run.run_id}`;
	const file = await createWriterDocument(owner.page.request, title);

	await openWriterDocument(owner.page, file.name);
	await writerEditor(owner.page).fill(content);
	await owner.page.keyboard.press("ControlOrMeta+s");
	await expect(owner.page.getByText("Saved document", { exact: true })).toBeVisible();

	await owner.page.goto("/drive");
	const folder = await createFolder(owner.page, folderName);
	const documentRow = owner.page.getByTestId(`drive-entity-${file.name}`);
	await expect(documentRow).toContainText(title);
	await openEntityActions(owner.page, file.name);
	await owner.page.getByRole("button", { name: "Rename" }).click();
	const renameDialog = owner.page.getByRole("dialog", { name: "Rename" });
	await renameDialog.getByRole("textbox").fill(renamedTitle);
	await Promise.all([
		owner.page.waitForResponse(
			(response) =>
				response.url().includes("suite.drive.api.files.rename") && response.ok(),
		),
		renameDialog.getByRole("button", { name: "Confirm" }).click(),
	]);
	await expect(documentRow).toContainText(renamedTitle);

	const moveResponse = await owner.page.request.post(
		"/api/method/suite.drive.api.files.move",
		{
			data: {
				entity_names: [file.name],
				new_parent: folder.name,
			},
		},
	);
	if (!moveResponse.ok()) throw new Error(await moveResponse.text());
	await owner.page.goto(`/drive/d/${folder.name}`);
	await expect(owner.page.getByTestId(`drive-entity-${file.name}`)).toContainText(
		renamedTitle,
	);

	await openEntityActions(owner.page, file.name);
	await owner.page.getByRole("button", { name: "Delete" }).click();
	await owner.page
		.getByRole("dialog")
		.getByRole("button", { name: "Move to Trash" })
		.click();
	await owner.page.getByRole("link", { name: "Trash", exact: true }).click();
	await expect(owner.page.getByTestId(`drive-entity-${file.name}`)).toContainText(
		renamedTitle,
	);
	const restoreResponse = await owner.page.request.post(
		"/api/method/suite.drive.api.files.remove_or_restore",
		{ data: { entity_names: [file.name] } },
	);
	if (!restoreResponse.ok()) throw new Error(await restoreResponse.text());

	await owner.page.goto(`/drive/d/${folder.name}`);
	await owner.page.getByTestId(`drive-entity-${file.name}`).click();
	await expect(owner.page).toHaveURL(new RegExp(`/writer/w/${file.name}`));
	await expect(writerEditor(owner.page)).toContainText(content);
});
