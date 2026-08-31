<template>
	<div>
		<div v-if="error" class="text-bad mb-4">{{ error }}</div>
		<div v-else-if="!payload" class="text-muted">Loading…</div>
		<div v-else-if="!payload.allowed" class="rounded-2xl border border-line bg-surface p-6 shadow-soft">
			<h1 class="text-2xl font-bold text-ink">Waiting is for staff</h1>
			<p class="text-sm text-muted mt-2">{{ payload.greeting }}</p>
		</div>
		<div v-else>
			<PageHeader
				eyebrow="Home"
				title="Waiting"
				subtitle="Everything that needs a decision or follow-up — same actions as Home, full list."
			>
				<template #actions>
					<RouterLink to="/home" class="btn-secondary text-sm">Back to Home</RouterLink>
				</template>
			</PageHeader>

			<div class="flex flex-wrap gap-2 mb-5">
				<button
					v-for="chip in chips"
					:key="chip.id"
					type="button"
					:class="
						cn(
							'px-3 py-1.5 rounded-full text-sm font-medium border transition-colors',
							filter === chip.id
								? 'bg-accent text-on-accent border-accent'
								: 'bg-surface text-muted border-line hover:text-ink'
						)
					"
					@click="filter = chip.id"
				>
					{{ chip.label }}
					<span class="tabular-nums ml-1 opacity-80">{{ chip.count }}</span>
				</button>
			</div>

			<TodoList
				:title="listTitle"
				:items="pageItems"
				:total-count="filtered.length"
				:show-empty="true"
				empty-hint="Nothing in this filter."
			/>

			<div v-if="pageCount > 1" class="flex items-center justify-between mt-4 text-sm">
				<button
					type="button"
					class="btn-secondary text-sm"
					:disabled="page <= 1"
					@click="page = Math.max(1, page - 1)"
				>
					Previous
				</button>
				<span class="text-muted">Page {{ page }} of {{ pageCount }}</span>
				<button
					type="button"
					class="btn-secondary text-sm"
					:disabled="page >= pageCount"
					@click="page = Math.min(pageCount, page + 1)"
				>
					Next
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { homePayload, loadHomePayload } from "../lib/home";
import { cn } from "../lib/cn";
import PageHeader from "../components/PageHeader.vue";
import TodoList from "../components/TodoList.vue";

const PAGE_SIZE = 20;

const route = useRoute();
const error = ref("");
const payload = computed(() => homePayload.value);
const filter = ref("all");
const page = ref(1);

const waiting = computed(() => payload.value?.waiting || payload.value?.todos || []);
const resume = computed(() => payload.value?.resume || []);

const allItems = computed(() => {
	if (filter.value === "resume") return resume.value;
	if (filter.value === "review") return waiting.value.filter((row) => row.bucket === "review");
	if (filter.value === "pay") return waiting.value.filter((row) => row.bucket === "pay");
	return [...waiting.value, ...resume.value];
});

const filtered = computed(() => allItems.value);

const pageCount = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)));
const pageItems = computed(() => {
	const start = (page.value - 1) * PAGE_SIZE;
	return filtered.value.slice(start, start + PAGE_SIZE);
});

const chips = computed(() => [
	{ id: "all", label: "All", count: waiting.value.length + resume.value.length },
	{
		id: "review",
		label: "Decide",
		count: waiting.value.filter((row) => row.bucket === "review").length,
	},
	{ id: "pay", label: "Pay", count: waiting.value.filter((row) => row.bucket === "pay").length },
	{ id: "resume", label: "Drafts", count: resume.value.length },
]);

const listTitle = computed(() => {
	const map = { all: "All", review: "Decide", pay: "Pay", resume: "Drafts" };
	return map[filter.value] || "Waiting";
});

watch(filter, () => {
	page.value = 1;
});

onMounted(async () => {
	const bucket = route.query.bucket;
	if (typeof bucket === "string" && ["review", "pay", "resume", "all"].includes(bucket)) {
		filter.value = bucket;
	}
	try {
		await loadHomePayload({ notify: false });
	} catch (e) {
		error.value = e.message || String(e);
	}
});
</script>
