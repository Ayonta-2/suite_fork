import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { request, type APIRequestContext, type FullConfig } from "@playwright/test";
import { loginViaApi, type Credentials } from "../shared/auth";
import { frappeData } from "../shared/frappe";

const statePath = resolve(__dirname, ".state/run.json");
const ownerStatePath = resolve(__dirname, ".state/owner.json");
const collaboratorStatePath = resolve(__dirname, ".state/collaborator.json");
const admin: Credentials = {
	email: process.env.E2E_ADMIN_EMAIL ?? "Administrator",
	password: process.env.E2E_ADMIN_PASSWORD ?? "admin",
};

async function cleanupPreviousRun(api: APIRequestContext): Promise<void> {
	try {
		const { run_id } = JSON.parse(readFileSync(statePath, "utf8")) as {
			run_id: string;
		};
		await api.post("/api/method/suite.drive.e2e_api.cleanup_users", {
			form: { run_id },
		});
	} catch {
		// No interrupted run to clean up.
	}
}

export default async function globalSetup(config: FullConfig): Promise<void> {
	const baseURL = config.projects[0]?.use.baseURL;
	if (typeof baseURL !== "string") throw new Error("Playwright baseURL is required");

	let ready = false;
	for (let attempt = 1; attempt <= 40; attempt++) {
		try {
			const response = await fetch(baseURL, { redirect: "manual" });
			if (response.status < 500) {
				ready = true;
				break;
			}
		} catch {
			// Bench may still be starting.
		}
		await new Promise((resolve) => setTimeout(resolve, 1_000));
	}
	if (!ready) throw new Error(`Frappe did not become ready at ${baseURL}`);

	const api = await request.newContext({ baseURL });
	await loginViaApi(api, admin);
	await cleanupPreviousRun(api);
	const runId = `${Date.now().toString(36)}-${process.pid}`;
	const response = await api.post(
		"/api/method/suite.drive.e2e_api.provision_users",
		{
			form: {
				run_id: runId,
				password: process.env.E2E_USER_PASSWORD ?? "DriveWriterE2E!2026",
			},
		},
	);
	const run = await frappeData<{
		users: Credentials[];
	}>(response);
	mkdirSync(dirname(statePath), { recursive: true });
	writeFileSync(statePath, JSON.stringify(run));
	for (const [user, path] of [
		[run.users[0], ownerStatePath],
		[run.users[1], collaboratorStatePath],
	] as const) {
		const userApi = await request.newContext({ baseURL });
		await loginViaApi(userApi, user);
		await userApi.storageState({ path });
		await userApi.dispose();
	}
	await api.dispose();
}
