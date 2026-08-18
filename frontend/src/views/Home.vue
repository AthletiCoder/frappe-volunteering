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

			<div id="todos">
				<TodoList :items="payload.todos || []" :show-empty="true" />
			</div>

			<ActionGrid v-if="showTime" title="Time" icon="clock" :actions="payload.actions.time" />
			<ActionGrid v-if="showMoney" :title="moneyTitle" icon="wallet" :actions="payload.actions.money" />

			<ProgramsStrip :programs="payload.programs" />
			<LinkStrip v-if="payload.people && payload.people.length" title="People" icon="people" :links="payload.people" />
			<LinkStrip v-if="payload.admin && payload.admin.length" title="Setup" icon="desk" :links="payload.admin" />
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

const error = ref("");
const payload = computed(() => homePayload.value);

const firstName = computed(() => {
	const name = payload.value?.full_name || "";
	return name.split(" ")[0] || "there";
});

const showTime = computed(() => payload.value?.flags?.show_time && payload.value?.actions?.time?.length);
const showMoney = computed(() => payload.value?.flags?.show_money && payload.value?.actions?.money?.length);
const moneyTitle = computed(() =>
	payload.value?.flags?.deemphasize_self_service ? "Your spend" : "Money"
);

onMounted(async () => {
	try {
		await loadHomePayload();
	} catch (e) {
		error.value = e.message || String(e);
	}
});
</script>
