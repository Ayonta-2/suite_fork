import { expect, test } from "../../fixtures/test";
import {
	createWriterDocument,
	openWriterDocument,
	uniqueWriterTitle,
} from "../../helpers/writer";

// Regression for the mobile tab bar (ToCMobile):
//   1. a tab added while the bar is already mounted must appear in it, and
//   2. tapping a tab on mobile must actually switch the visible panel.
test("mobile tab bar reflects added tabs and switches the active panel", async ({
	owner,
	run,
}) => {
	const { page } = owner;
	await page.setViewportSize({ width: 1440, height: 900 });
	const file = await createWriterDocument(
		page.request,
		uniqueWriterTitle(run.run_id, "tabs-mobile"),
	);
	// Open the Table of Contents expanded so its tab controls are reachable
	// (the collapsed toggle is an icon-only button with no accessible name).
	await page.addInitScript(() => window.localStorage.setItem("showToc", "true"));
	await openWriterDocument(page, file.name);

	// First tab wraps the doc; the bar (ToCMobile) mounts here (CSS-hidden on
	// desktop). Adding the second tab afterwards is the live-update case.
	await page.getByRole("button", { name: "Create tab" }).click();
	await page.getByRole("button", { name: "Add tab" }).click();

	// Switch to a phone viewport: the bar becomes visible. Only ToCMobile renders
	// frappe-ui TabButtons (data-slot="tab-button"), so these are its buttons.
	await page.setViewportSize({ width: 390, height: 844 });

	// Bug 1: the second tab (added after the bar mounted) shows up in the bar.
	const barButtons = page.locator('[data-slot="tab-button"]');
	await expect(barButtons).toHaveCount(2);

	// Exactly one tab panel is shown; the freshly-added (second) tab is active.
	const panels = page.locator("[data-tab-id]");
	await expect(panels).toHaveCount(2);
	const ids = await panels.evaluateAll((els) =>
		els.map((el) => el.getAttribute("data-tab-id")),
	);
	await expect(page.locator(`[data-tab-id="${ids[1]}"]`)).toBeVisible();
	await expect(page.locator(`[data-tab-id="${ids[0]}"]`)).toBeHidden();

	// Bug 2: tapping the first tab in the bar switches the visible panel.
	await barButtons.first().click();
	await expect(page.locator(`[data-tab-id="${ids[0]}"]`)).toBeVisible();
	await expect(page.locator(`[data-tab-id="${ids[1]}"]`)).toBeHidden();
});
