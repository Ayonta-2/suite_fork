import {
	expect,
	test as base,
	type Browser,
	type BrowserContext,
	type Page,
	request as playwrightRequest,
} from "@playwright/test";
import { loginViaApi, type Credentials } from "../helpers/auth";
import { frappeData } from "../helpers/frappe";

const baseURL = process.env.BASE_URL ?? "http://suite.localhost:8000";
const admin: Credentials = {
	email: process.env.E2E_ADMIN_EMAIL ?? "Administrator",
	password: process.env.E2E_ADMIN_PASSWORD ?? "admin",
};
const testPassword = process.env.E2E_USER_PASSWORD ?? "DriveWriterE2E!2026";

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

function runId(): string {
	const configured = process.env.E2E_RUN_ID;
	if (configured) return configured.toLowerCase();
	return `${Date.now().toString(36)}-${process.pid}`;
}

async function authenticatedPage(
	browser: Browser,
	user: ProvisionedUser,
): Promise<AuthenticatedPage> {
	const context = await browser.newContext();
	await loginViaApi(context.request, user);
	return { context, page: await context.newPage(), user };
}

export const test = base.extend<Fixtures, WorkerFixtures>({
	run: [
		async ({}, use) => {
			const api = await playwrightRequest.newContext({ baseURL });
			await loginViaApi(api, admin);
			const id = runId();
			const response = await api.post(
				"/api/method/suite.drive.e2e_api.provision_users",
				{ form: { run_id: id, password: testPassword } },
			);
			const run = await frappeData<ProvisionedRun>(response);
			try {
				await use(run);
			} finally {
				const cleanup = await api.post(
					"/api/method/suite.drive.e2e_api.cleanup_users",
					{ form: { run_id: id } },
				);
				if (!cleanup.ok()) {
					console.warn(`E2E cleanup failed: ${await cleanup.text()}`);
				}
				await api.dispose();
			}
		},
		{ scope: "worker" },
	],
	owner: async ({ browser, run }, use) => {
		const authenticated = await authenticatedPage(browser, run.users[0]);
		await use(authenticated);
		await authenticated.context.close();
	},
	collaborator: async ({ browser, run }, use) => {
		const authenticated = await authenticatedPage(browser, run.users[1]);
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
export type { AuthenticatedPage, ProvisionedRun, ProvisionedUser };
