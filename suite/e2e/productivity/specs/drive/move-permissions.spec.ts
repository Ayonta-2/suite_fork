import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "../../fixtures/test";
import {
	createFolder,
	getDriveEntity,
	openEntityActions,
	shareCurrentEntity,
	waitForDriveEntity,
} from "../../helpers/drive";

const uploadFixture = resolve(__dirname, "fixtures/drive-upload.txt");

test("moves a file into a nested shared folder with inherited reader access", async ({
	owner,
	collaborator,
	run,
}) => {
	const suffix = `${run.run_id}-${Date.now()}`;
	const parentName = `parent-${suffix}`;
	const childName = `child-${suffix}`;
	const fileName = `nested-${suffix}.txt`;

	await owner.page.goto("/drive");
	const parent = await createFolder(owner.page, parentName);
	await owner.page.getByTestId(`drive-entity-${parent.name}`).click();
	await expect(owner.page).toHaveURL(new RegExp(`/drive/d/${parent.name}`));

	const child = await createFolder(owner.page, childName, parent.name);
	await Promise.all([
		owner.page.waitForResponse(
			(response) => response.url().includes("upload_file") && response.ok(),
		),
		owner.page.getByTestId("drive-file-input").setInputFiles({
			name: fileName,
			mimeType: "text/plain",
			buffer: readFileSync(uploadFixture),
		}),
	]);
	const file = await waitForDriveEntity(owner.page.request, fileName, parent.name);

	await Promise.all([
		owner.page.waitForResponse(
			(response) =>
				response.url().includes("suite.drive.api.files.move") && response.ok(),
		),
		owner.page
			.getByTestId(`drive-entity-${file.name}`)
			.dragTo(owner.page.getByTestId(`drive-entity-${child.name}`)),
	]);
	await expect(owner.page.getByTestId(`drive-entity-${file.name}`)).toBeHidden();

	await owner.page.goto(`/drive/d/${parent.name}`);
	await shareCurrentEntity(owner.page, parentName, collaborator.user.email);

	await collaborator.page.goto(`/drive/d/${child.name}`);
	await expect(collaborator.page.getByTestId(`drive-entity-${file.name}`)).toBeVisible();
	const permissions = await getDriveEntity(collaborator.page.request, file.name);
	expect(Boolean(permissions.read)).toBe(true);
	expect(Boolean(permissions.write)).toBe(false);
	expect(Boolean(permissions.upload)).toBe(false);
	expect(Boolean(permissions.share)).toBe(false);

	await openEntityActions(collaborator.page, file.name);
	await expect(collaborator.page.getByRole("button", { name: "Download" })).toBeVisible();
	await expect(collaborator.page.getByRole("button", { name: "Rename" })).toHaveCount(0);
	await expect(collaborator.page.getByRole("button", { name: "Move" })).toHaveCount(0);
	await expect(collaborator.page.getByRole("button", { name: "Delete" })).toHaveCount(0);
});
