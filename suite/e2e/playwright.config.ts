import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.BASE_URL ?? "http://suite.localhost:8000";
const isCI = !!process.env.CI;

export default defineConfig({
	testDir: "./specs",
	fullyParallel: true,
	forbidOnly: isCI,
	retries: isCI ? 2 : 0,
	workers: 2,
	timeout: isCI ? 90_000 : 60_000,
	expect: { timeout: 10_000 },
	reporter: isCI
		? [
				["list"],
				["github"],
				["html", { open: "never" }],
				["junit", { outputFile: "results.xml" }],
			]
		: [["list"], ["html", { open: "never" }]],
	use: {
		baseURL,
		trace: "on-first-retry",
		video: "on-first-retry",
		screenshot: "only-on-failure",
		viewport: { width: 1440, height: 900 },
		actionTimeout: 15_000,
		navigationTimeout: 30_000,
	},
	projects: [
		{
			name: "chromium",
			use: { ...devices["Desktop Chrome"], channel: "chrome" },
		},
	],
	globalSetup: "./global-setup.ts",
	globalTeardown: "./global-teardown.ts",
});
