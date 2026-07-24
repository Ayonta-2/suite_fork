import { expect, test } from "../../fixtures/test";
import {
	createWriterDocument,
	uniqueWriterTitle,
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
