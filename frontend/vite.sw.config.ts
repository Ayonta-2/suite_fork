import fs from "node:fs";
import path from "node:path";
import { defineConfig } from "vite";

import { slidesBuildId } from "./slidesBuildId";

const swOutput = path.resolve(__dirname, "../suite/www/service-worker.js");

// frappe renders files under www/ through Jinja before serving them, so a Jinja
// delimiter in the bundle would either be stripped or blow up the request.
const guardServedOutput = () => ({
	name: "slides-sw-output-guard",
	closeBundle() {
		const code = fs.readFileSync(swOutput, "utf-8");
		const forbidden = ["{{", "{%", "{#", "process.env"];
		const found = forbidden.filter((token) => code.includes(token));
		if (found.length) {
			throw new Error(`service-worker.js must not contain ${found.join(", ")}`);
		}
	},
});

export default defineConfig({
	root: __dirname,
	// suite/www holds hand-written templates: never clear it, never copy public/ into it
	publicDir: false,
	define: {
		"process.env.NODE_ENV": '"production"',
		__SLIDES_BUILD__: JSON.stringify(slidesBuildId()),
	},
	plugins: [guardServedOutput()],
	build: {
		outDir: "../suite/www",
		emptyOutDir: false,
		minify: false,
		sourcemap: false,
		target: "es2020",
		lib: {
			entry: path.resolve(__dirname, "src/apps/slides/service-worker.js"),
			formats: ["iife"],
			name: "slidesServiceWorker",
			fileName: () => "service-worker.js",
		},
	},
});
