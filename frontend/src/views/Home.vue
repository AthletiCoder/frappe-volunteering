<template>
	<div>
		<div v-if="error" class="text-bad mb-4">{{ error }}</div>
		<div v-else-if="!payload" class="text-muted">Loading…</div>
		<div v-else-if="!payload.allowed" class="rounded-2xl border border-line bg-surface p-6 shadow-soft">
			<h1 class="text-2xl font-bold text-ink">Home is for staff</h1>
			<p class="text-sm text-muted mt-2">{{ payload.greeting }}</p>
		</div>
		<div v-else class="space-y-8">
			<PageHeader :title="`Hello ${firstName}`" :subtitle="payload.greeting" eyebrow="Home" />

			<TodoList
				title="Waiting on you"
				:items="waitingPreview"
				:total-count="waitingCount"
				:see-all-to="waitingCount > HOME_WAITING_CAP ? '/todos' : ''"
				:show-empty="true"
				empty-title="You’re clear"
				:empty-hint="clearHint"
			/>

			<ActionGrid v-if="showTime" title="Start · Time" icon="clock" :actions="payload.actions.time" />
			<ActionGrid
				v-if="showMoney"
				:title="moneyTitle"
				icon="wallet"
				:actions="payload.actions.money"
			/>

			<TodoList
				v-if="resumeItems.length"
				title="Resume"
				icon="clock"
				icon-class="text-muted"
				:items="resumePreview"
				:total-count="resumeItems.length"
				:see-all-to="resumeItems.length > HOME_RESUME_CAP ? '/todos?bucket=resume' : ''"
			/>

			<details v-if="hasMore" class="group rounded-2xl border border-line bg-surface shadow-soft">
				<summary
					class="cursor-pointer list-none px-4 py-3 text-sm font-semibold text-ink flex items-center justify-between"
				>
					More
					<span class="text-muted font-normal group-open:hidden">Programs, people, setup</span>
				</summary>
				<div class="px-4 pb-4 space-y-6 border-t border-line pt-4">
					<ProgramsStrip :programs="payload.programs" />
					<LinkStrip
						v-if="payload.people && payload.people.length"
						title="People"
						icon="people"
						:links="payload.people"
					/>
					<LinkStrip
						v-if="payload.admin && payload.admin.length"
						title="Setup"
						icon="desk"
						:links="payload.admin"
					/>
				</div>
			</details>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { homePayload, loadHomePayload } from "../lib/home";
import PageHeader from "../components/PageHeader.vue";
import TodoList from "../components/TodoList.vue";
import ActionGrid from "../components/ActionGrid.vue";
import ProgramsStrip from "../components/ProgramsStrip.vue";
import LinkStrip from "../components/LinkStrip.vue";

const HOME_WAITING_CAP = 3;
const HOME_RESUME_CAP = 2;

const error = ref("");
const payload = computed(() => homePayload.value);

const firstName = computed(() => {
	const name = payload.value?.full_name || "";
	return name.split(" ")[0] || "there";
});

const waitingItems = computed(() => payload.value?.waiting || payload.value?.todos || []);
const waitingCount = computed(() => payload.value?.waiting_count ?? waitingItems.value.length);
const waitingPreview = computed(() => waitingItems.value.slice(0, HOME_WAITING_CAP));

const resumeItems = computed(() => payload.value?.resume || []);
const resumePreview = computed(() => resumeItems.value.slice(0, HOME_RESUME_CAP));

const showTime = computed(() => payload.value?.flags?.show_time && payload.value?.actions?.time?.length);
const showMoney = computed(() => payload.value?.flags?.show_money && payload.value?.actions?.money?.length);
const moneyTitle = computed(() =>
	payload.value?.flags?.deemphasize_self_service ? "Start · Your spend" : "Start · Money"
);

const clearHint = computed(() =>
	showTime.value ? "Log today’s work when you’re ready." : "Nothing needs you right now."
);

const hasMore = computed(() => {
	const p = payload.value;
	if (!p) return false;
	return Boolean(
		p.programs || (p.people && p.people.length) || (p.admin && p.admin.length)
	);
});

onMounted(async () => {
	try {
		await loadHomePayload();
	} catch (e) {
		error.value = e.message || String(e);
	}
});
</script>
