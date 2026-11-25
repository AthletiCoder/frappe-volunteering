import { defineConfig } from "../frontend/node_modules/vite/dist/node/index.js";
import vue from "../frontend/node_modules/@vitejs/plugin-vue/dist/index.mjs";
import { fileURLToPath } from "node:url";
import { cpSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";

const output = fileURLToPath(new URL("../volunteering/public/sf_tasks", import.meta.url));
function precache() {
	return {
		name: "sf-tasks-offline-index",
		closeBundle() {
			const pdfjs = fileURLToPath(new URL("./node_modules/pdfjs-dist/", import.meta.url));
			for (const resource of ["LICENSE", "cmaps", "iccs", "standard_fonts", "wasm"]) {
				cpSync(path.join(pdfjs, resource), path.join(output, "pdfjs", resource), {
					recursive: true,
				});
			}
			const walk = (directory) =>
				readdirSync(directory, { withFileTypes: true }).flatMap((row) =>
					row.isDirectory()
						? walk(path.join(directory, row.name))
						: [path.join(directory, row.name)],
				);
			writeFileSync(
				path.join(output, "precache.json"),
				JSON.stringify(
					walk(output)
						.filter(
							(name) =>
								!name.endsWith("precache.json") && !name.endsWith("build.json"),
						)
						.map(
							(name) =>
								"/assets/volunteering/sf_tasks/" +
								path.relative(output, name).replaceAll("\\", "/"),
						),
				),
			);
		},
	};
}

export default defineConfig({
	root: fileURLToPath(new URL(".", import.meta.url)),
	base: "/assets/volunteering/sf_tasks/",
	plugins: [vue(), precache()],
	resolve: {
		alias: {
			vue: fileURLToPath(
				new URL(
					"../frontend/node_modules/vue/dist/vue.runtime.esm-bundler.js",
					import.meta.url,
				),
			),
		},
	},
	build: {
		outDir: output,
		emptyOutDir: true,
		target: "es2022",
		manifest: "build.json",
		rollupOptions: {
			input: {
				app: fileURLToPath(new URL("./index.html", import.meta.url)),
				worker: fileURLToPath(new URL("./src/worker.js", import.meta.url)),
			},
		},
	},
});
