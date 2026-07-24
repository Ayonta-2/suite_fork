import {
	expect,
	test as base,
	type Browser,
	type BrowserContext,
	type Page,
} from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { Credentials } from "../../shared/auth";

const statePath = resolve(__dirname, "../.state/run.json");
const authStatePaths = [
	resolve(__dirname, "../.state/owner.json"),
	resolve(__dirname, "../.state/collaborator.json"),
];

interface ProvisionedUser extends Credentials {
	user: string;
	drive_settings: string;
	personal_team: string;
}

interface ProvisionedRun {
	run_id: string;
	users: ProvisionedUser[];
}

interface AuthenticatedPage {
	context: BrowserContext;
	page: Page;
	user: ProvisionedUser;
}

interface Fixtures {
	owner: AuthenticatedPage;
	collaborator: AuthenticatedPage;
	guestPage: Page;
}

interface WorkerFixtures {
	run: ProvisionedRun;
}

async function authenticatedPage(
	browser: Browser,
	user: ProvisionedUser,
	storageState: string,
): Promise<AuthenticatedPage> {
	const context = await browser.newContext({ storageState });
	return { context, page: await context.newPage(), user };
}

export const test = base.extend<Fixtures, WorkerFixtures>({
	run: [
		async ({}, use) => {
			const run = JSON.parse(readFileSync(statePath, "utf8")) as ProvisionedRun;
			await use(run);
		},
		{ scope: "worker" },
	],
	owner: async ({ browser, run }, use) => {
		const authenticated = await authenticatedPage(
			browser,
			run.users[0],
			authStatePaths[0],
		);
		await use(authenticated);
		await authenticated.context.close();
	},
	collaborator: async ({ browser, run }, use) => {
		const authenticated = await authenticatedPage(
			browser,
			run.users[1],
			authStatePaths[1],
		);
		await use(authenticated);
		await authenticated.context.close();
	},
	guestPage: async ({ browser }, use) => {
		const context = await browser.newContext();
		const page = await context.newPage();
		await use(page);
		await context.close();
	},
});

export { expect };
