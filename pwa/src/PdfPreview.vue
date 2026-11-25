<template>
	<section aria-label="PDF preview">
		<p v-if="error" class="muted" role="status">{{ error }}</p>
		<p v-else-if="!page" class="muted" role="status">Preparing PDF preview…</p>
		<div v-if="pages > 1 && !error" class="pdf-controls">
			<button
				type="button"
				class="secondary"
				:disabled="busy || page <= 1"
				@click="render(page - 1)"
			>
				Previous
			</button>
			<span aria-live="polite">Page {{ page || 1 }} of {{ pages }}</span>
			<button
				type="button"
				class="secondary"
				:disabled="busy || page >= pages"
				@click="render(page + 1)"
			>
				Next
			</button>
		</div>
		<canvas
			v-show="page && !error"
			ref="canvas"
			class="pdf-page"
			role="img"
			:aria-label="`PDF page ${page} of ${pages}`"
		></canvas>
	</section>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { getDocument, GlobalWorkerOptions } from "pdfjs-dist/legacy/build/pdf.min.mjs";
import workerUrl from "pdfjs-dist/legacy/build/pdf.worker.min.mjs?url";

const props = defineProps({ url: { type: String, required: true } });
const canvas = ref(null);
const busy = ref(true);
const page = ref(0);
const pages = ref(0);
const error = ref("");
const resources = import.meta.env.BASE_URL + "pdfjs/";
let loadingTask;
let document;
let renderTask;
let closed = false;

function previewFailed() {
	if (!closed)
		error.value = "This PDF could not be previewed. Download it to open it in a PDF reader.";
}

async function render(number) {
	busy.value = true;
	try {
		const pdfPage = await document.getPage(number);
		if (closed) return;
		const original = pdfPage.getViewport({ scale: 1 });
		const scale = Math.min(2, 1800 / Math.max(original.width, original.height));
		const viewport = pdfPage.getViewport({ scale });
		canvas.value.width = Math.max(1, Math.ceil(viewport.width));
		canvas.value.height = Math.max(1, Math.ceil(viewport.height));
		renderTask = pdfPage.render({ canvas: canvas.value, viewport });
		await renderTask.promise;
		if (!closed) page.value = number;
		pdfPage.cleanup();
	} catch {
		previewFailed();
	} finally {
		renderTask = undefined;
		busy.value = false;
	}
}

onMounted(async () => {
	try {
		GlobalWorkerOptions.workerSrc = workerUrl;
		loadingTask = getDocument({
			url: props.url,
			cMapUrl: resources + "cmaps/",
			standardFontDataUrl: resources + "standard_fonts/",
			wasmUrl: resources + "wasm/",
			iccUrl: resources + "iccs/",
			isEvalSupported: false,
			enableXfa: false,
			canvasMaxAreaInBytes: 32 * 1024 * 1024,
		});
		document = await loadingTask.promise;
		if (closed) return;
		pages.value = document.numPages;
		await render(1);
	} catch {
		previewFailed();
	}
});

onBeforeUnmount(() => {
	closed = true;
	renderTask?.cancel();
	void loadingTask?.destroy().catch(() => {});
});
</script>

<style scoped>
.pdf-controls {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.5rem;
	margin-bottom: 0.75rem;
	font-size: 0.875rem;
}
.pdf-page {
	display: block;
	width: 100%;
	height: auto;
	border: 1px solid var(--border);
	border-radius: 8px;
	background: white;
}
</style>
