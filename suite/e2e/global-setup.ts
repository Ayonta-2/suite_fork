import type { FullConfig } from "@playwright/test";

export default async function globalSetup(config: FullConfig): Promise<void> {
	const baseURL = config.projects[0]?.use.baseURL;
	if (typeof baseURL !== "string") throw new Error("Playwright baseURL is required");

	for (let attempt = 1; attempt <= 40; attempt++) {
		try {
			const response = await fetch(baseURL, { redirect: "manual" });
			if (response.status < 500) return;
		} catch {
			// Bench may still be starting.
		}
		await new Promise((resolve) => setTimeout(resolve, 1_000));
	}

	throw new Error(`Frappe did not become ready at ${baseURL}`);
}
