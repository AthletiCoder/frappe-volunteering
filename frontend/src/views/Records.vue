<template>
	<div class="mx-auto max-w-4xl space-y-5">
		<PageHeader title="Records" eyebrow="Everything you raised" subtitle="Every request you have made, in one place. Open a kind to see its history and status.">
			<template #actions>
				<RouterLink to="/home" class="btn-back">Back to Home</RouterLink>
			</template>
		</PageHeader>

		<p v-if="loading" class="text-muted" role="status">Loading your records…</p>
		<div v-else-if="!kinds.length" class="kit-panel flex flex-col items-center px-6 py-12 text-center">
			<span class="flex h-12 w-12 items-center justify-center rounded-2xl bg-navy-50 text-navy-900"><Icon name="document-history" /></span>
			<h2 class="mt-3 text-base font-semibold text-ink">No records yet</h2>
			<p class="mt-1 text-sm text-muted">Requests you raise will be listed here.</p>
		</div>
		<template v-else>
			<RouterLink v-if="waiting" to="/todos" class="kit-panel records-waiting group">
				<span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-marigold text-navy-900"><Icon name="check" size="sm" /></span>
				<span class="min-w-0 flex-1">
					<strong class="block text-sm text-ink">{{ waiting }} {{ waiting === 1 ? "request is" : "requests are" }} waiting on you</strong>
					<span class="block text-xs text-muted">Decisions other people need from you live in Waiting.</span>
				</span>
				<Icon name="arrow-right" size="sm" class="dir-row__arrow !block" />
			</RouterLink>
			<nav class="kit-panel overflow-hidden" aria-label="Record kinds">
				<a v-for="kind in kinds" :key="kind.id" :href="kind.href" class="dir-row group">
					<span class="flex h-10 w-10 items-center justify-center rounded-xl bg-navy-50 text-navy-900"><Icon :name="kind.icon" size="sm" /></span>
					<span class="min-w-0">
						<strong class="block truncate text-sm text-ink">{{ kind.label }}</strong>
						<span class="block truncate text-xs text-muted">{{ kind.hint }}</span>
					</span>
					<span class="dir-row__meta"></span>
					<span v-if="kind.open" class="pill pill--warn">{{ kind.open }} pending</span>
					<span v-else class="pill pill--muted">Up to date</span>
					<Icon name="arrow-right" size="sm" class="dir-row__arrow" />
				</a>
			</nav>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { RouterLink } from "vue-router";
import Icon from "../components/Icon.vue";
import PageHeader from "../components/PageHeader.vue";
import { homePayload, loadHomePayload } from "../lib/home";
import { buildRecordKinds } from "../lib/workspaceNavigation";

const loading = computed(() => !homePayload.value);
const kinds = computed(() => buildRecordKinds(homePayload.value));
const waiting = computed(() => Number(homePayload.value?.waiting_count || 0));
onMounted(() => {
	if (!homePayload.value) loadHomePayload().catch(() => {});
});
</script>

<style scoped>
.records-waiting { display: flex; align-items: center; gap: 0.875rem; padding: 1rem 1.25rem; background: var(--marigold-soft); border-color: color-mix(in srgb, var(--marigold) 45%, var(--line)); transition: box-shadow var(--dur) ease; }
.records-waiting:hover { box-shadow: var(--shadow-lift); }
.records-waiting:hover .dir-row__arrow { transform: translateX(2px); color: var(--navy-900); }
</style>
