import type { APIRequestContext, Page } from "@playwright/test";

import { expect, test } from "../../fixtures/test";
import { frappeData } from "../../../shared/frappe";

/**
 * The Attachments section is a three-level tree of virtual nodes - doctype >
 * document > files - that only exists in the listing. The nodes look like
 * folders but aren't Drive entities, so navigating them takes its own path.
 */

interface Attached {
	todo: string;
	fileName: string;
}

/** A ToDo owned by the caller, with one file attached to it. */
async function attachFile(
	request: APIRequestContext,
	label: string,
): Promise<Attached> {
	const created = await request.post("/api/resource/ToDo", {
		data: { description: label },
	});
	const todo = (await frappeData<{ name: string }>(created)).name;

	const fileName = `${label}.txt`;
	const uploaded = await request.post("/api/method/upload_file", {
		multipart: {
			doctype: "ToDo",
			docname: todo,
			is_private: "1",
			file: {
				name: fileName,
				mimeType: "text/plain",
				buffer: Buffer.from(`attachment for ${label}`),
			},
		},
	});
	if (!uploaded.ok()) {
		throw new Error(`Attaching the file failed: ${await uploaded.text()}`);
	}
	return { todo, fileName };
}

async function deleteTodo(
	request: APIRequestContext,
	todo: string,
): Promise<void> {
	// Best effort: leftover test data must never fail the test it belongs to.
	await request.delete(`/api/resource/ToDo/${todo}`).catch(() => undefined);
}

/** The breadcrumb trail in the navbar, outermost first. */
async function trail(page: Page): Promise<string[]> {
	const crumbs = page.getByTestId("breadcrumbs");
	await expect(crumbs).toBeVisible();
	await expect(page.getByTestId("breadcrumbs-loading")).toHaveCount(0);
	return (await crumbs.innerText())
		.split("/")
		.map((part: string) => part.trim())
		.filter(Boolean);
}

async function openRow(page: Page, name: string): Promise<void> {
	const row = page.getByTestId(`drive-entity-${name}`);
	await expect(row).toBeVisible();
	await row.click();
}

test("drilling from doctype to document to file, and back up the trail", async ({
	owner,
	run,
}) => {
	const page = owner.page;
	const { todo, fileName } = await attachFile(
		page.request,
		`attach-${run.run_id}-${Date.now()}`,
	);

	await page.goto("/drive/attachments");
	await expect.poll(() => trail(page)).toEqual(["Attachments"]);

	// The doctype node routes into its own bucket, not to /drive/d/ToDo.
	await openRow(page, "ToDo");
	await expect(page).toHaveURL(/\/drive\/attachments\/ToDo$/);
	await expect.poll(() => trail(page)).toEqual(["Attachments", "ToDo"]);

	await openRow(page, todo);
	await expect(page).toHaveURL(new RegExp(`/drive/attachments/ToDo/${todo}$`));
	await expect.poll(() => trail(page)).toEqual(["Attachments", "ToDo", todo]);
	await expect(page.getByText(fileName, { exact: true })).toBeVisible();

	// An ancestor crumb walks back out.
	await page.locator("#navbar").getByRole("link", { name: "ToDo" }).click();
	await expect(page).toHaveURL(/\/drive\/attachments\/ToDo$/);
	await expect(page.getByTestId(`drive-entity-${todo}`)).toBeVisible();

	await page.locator("#navbar").getByRole("link", { name: "Attachments" }).click();
	await expect(page).toHaveURL(/\/drive\/attachments$/);
	await expect(page.getByTestId("drive-entity-ToDo")).toBeVisible();

	await deleteTodo(page.request, todo);
});

test("a deep link lands on the document's attachments", async ({
	owner,
	run,
}) => {
	const page = owner.page;
	const { todo, fileName } = await attachFile(
		page.request,
		`deep-${run.run_id}-${Date.now()}`,
	);

	await page.goto(`/drive/attachments/ToDo/${todo}`);
	await expect(page.getByText(fileName, { exact: true })).toBeVisible();
	await expect.poll(() => trail(page)).toEqual(["Attachments", "ToDo", todo]);

	await deleteTodo(page.request, todo);
});

test("virtual nodes offer no folder tree to expand", async ({ owner, run }) => {
	const page = owner.page;
	const { todo } = await attachFile(
		page.request,
		`expand-${run.run_id}-${Date.now()}`,
	);

	await page.goto("/drive/attachments");
	await expect(page.getByTestId("drive-entity-ToDo")).toBeVisible();
	// They have no Drive children to fetch, so they carry no expand control.
	await expect(page.getByTestId("drive-expand-ToDo")).toHaveCount(0);

	await page.goto("/drive/attachments/ToDo");
	await expect(page.getByTestId(`drive-entity-${todo}`)).toBeVisible();
	await expect(page.getByTestId(`drive-expand-${todo}`)).toHaveCount(0);

	await deleteTodo(page.request, todo);
});

test("the attached file opens from the listing", async ({ owner, run }) => {
	const page = owner.page;
	const { todo, fileName } = await attachFile(
		page.request,
		`open-${run.run_id}-${Date.now()}`,
	);

	await page.goto(`/drive/attachments/ToDo/${todo}`);
	const file = page.getByText(fileName, { exact: true });
	await expect(file).toBeVisible();
	await file.click();
	await expect(page).toHaveURL(/\/drive\/f\//);

	await deleteTodo(page.request, todo);
});

test("another user's attachments stay out of the listing", async ({
	owner,
	collaborator,
	run,
}) => {
	const { todo, fileName } = await attachFile(
		owner.page.request,
		`private-${run.run_id}-${Date.now()}`,
	);

	const page = collaborator.page;
	await page.goto(`/drive/attachments/ToDo/${todo}`);
	await expect(page.getByText(fileName, { exact: true })).toHaveCount(0);

	await deleteTodo(owner.page.request, todo);
});
