<template>
	<div class="mx-auto max-w-6xl space-y-5">
		<PageHeader
			title="Fiscal years"
			eyebrow="System management"
			subtitle="Keep the accounting years Sevamrita still needs available for correctly dated entries."
		>
			<template #actions><RouterLink to="/home" class="btn-back">Back to Home</RouterLink></template>
		</PageHeader>

		<p v-if="error" class="message-error" role="alert">{{ error }}</p>
		<p v-if="message" class="message-success" role="status">{{ message }}</p>
		<p v-if="loading" class="text-muted" role="status">Loading fiscal years…</p>

		<div v-else-if="workspace" class="form-layout">
			<section class="kit-panel min-w-0 overflow-hidden" aria-labelledby="fy-list-title">
				<header class="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
					<div>
						<h2 id="fy-list-title" class="font-display text-base font-semibold text-ink">Sevamrita’s fiscal years</h2>
						<p class="mt-0.5 text-sm text-muted">April–March years available to Sevamrita Foundation.</p>
					</div>
					<span class="pill pill--info">{{ activeCount }} active</span>
				</header>
				<p v-if="!workspace.years.length" class="m-5 rounded-xl bg-soft p-4 text-sm text-muted">No April–March fiscal years are configured yet.</p>
				<div v-else>
					<article v-for="year in workspace.years" :key="year.name" class="year-row" :class="{ 'year-row--current': year.current }">
						<span class="year-tile" :class="{ 'year-tile--off': !year.active }" aria-hidden="true">
							<span class="text-[10px] font-semibold uppercase tracking-wider opacity-70">FY</span>
							<span class="font-display text-sm font-semibold">{{ shortName(year.name) }}</span>
						</span>
						<div class="min-w-0 flex-1">
							<div class="flex flex-wrap items-center gap-2">
								<h3 class="font-semibold text-ink">FY {{ year.name }}</h3>
								<span :class="pillClass(year.active ? 'ok' : 'muted')">{{ year.active ? 'Active' : 'Disabled' }}</span>
								<span v-if="year.current" class="pill pill--info">Current dates</span>
							</div>
							<p class="mt-1 text-sm text-muted">{{ dateLabel(year.start_date) }} – {{ dateLabel(year.end_date) }}</p>
							<div v-if="year.current" class="mt-2 max-w-xs">
								<div class="h-1.5 overflow-hidden rounded-full bg-soft" role="img" :aria-label="`${elapsed(year)}% of this year has passed`">
									<div class="h-full rounded-full bg-accent" :style="{ width: `${elapsed(year)}%` }"></div>
								</div>
								<p class="mt-1 text-xs text-muted">{{ elapsed(year) }}% of the year has passed</p>
							</div>
							<p v-if="!year.active && !year.can_activate" class="mt-1 text-xs text-muted">This shared year affects other companies; review it in Desk before enabling it.</p>
						</div>
						<button v-if="!year.active && year.can_activate" type="button" class="btn-secondary shrink-0" :disabled="saving" @click="activate(year)">
							{{ saving ? 'Working…' : 'Reactivate' }}
						</button>
					</article>
				</div>
			</section>

			<aside class="form-rail min-w-0 space-y-4">
				<section class="kit-panel p-5" aria-labelledby="fy-add-title">
					<h2 id="fy-add-title" class="step-title mb-1"><span class="step-num"><Icon name="calendar-check" size="sm" /></span>Add a missing year</h2>
					<p class="text-sm text-muted">Enter the calendar year in which the fiscal year starts. The dates are set automatically for Sevamrita’s April–March cycle.</p>
					<form class="mt-4 space-y-4" @submit.prevent="createYear">
						<label class="field-label">Starting year *
							<input v-model.trim="startYear" type="number" min="2000" max="2098" step="1" required inputmode="numeric" placeholder="For example, 2025" class="field-input" />
						</label>
						<div v-if="preview" class="rounded-xl border border-line bg-soft p-4 text-sm">
							<strong class="text-ink">FY {{ preview.name }}</strong>
							<p class="mt-1 text-muted">{{ preview.start }} – {{ preview.end }} · Sevamrita Foundation · Active</p>
						</div>
						<button type="submit" class="btn-primary w-full justify-center" :disabled="saving || !preview || alreadyExists">
							{{ alreadyExists ? 'Year already exists' : saving ? 'Creating…' : 'Create fiscal year' }}
						</button>
					</form>
				</section>
				<section class="rounded-2xl bg-accent-soft p-4 text-sm leading-relaxed">
					<strong class="text-ink">More than one fiscal year can remain active.</strong>
					<p class="mt-1 text-muted">
						Adding or reactivating a year does not close another year, change the default, or override an accounting freeze.
						Post each entry using its correct accounting date.
					</p>
				</section>
			</aside>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import Icon from "../components/Icon.vue";
import { pillClass } from "../lib/tones.js";
import { call } from "../lib/frappe";

const API = "volunteering.volunteering.fiscal_year_portal.";
const loading = ref(true);
const saving = ref(false);
const workspace = ref(null);
const startYear = ref("");
const error = ref("");
const message = ref("");
const activeCount = computed(() => workspace.value?.years.filter((year) => year.active).length || 0);
const preview = computed(() => {
	const raw = String(startYear.value || "");
	if (!/^20\d{2}$/.test(raw) || Number(raw) > 2098) return null;
	const next = Number(raw) + 1;
	return { name: `${raw}-${next}`, start: `1 Apr ${raw}`, end: `31 Mar ${next}` };
});
const alreadyExists = computed(() => Boolean(preview.value && workspace.value?.years.some((year) => year.name === preview.value.name)));

function dateLabel(value) {
	if (!value) return "";
	const [year, month, day] = String(value).slice(0, 10).split("-");
	return `${day}/${month}/${year}`;
}

function shortName(name) {
	const [start, end] = String(name || "").split("-");
	return end ? `${start.slice(-2)}–${end.slice(-2)}` : name;
}
function elapsed(year) {
	const start = new Date(year.start_date).getTime();
	const end = new Date(year.end_date).getTime();
	if (!start || !end || end <= start) return 0;
	return Math.round(Math.min(1, Math.max(0, (Date.now() - start) / (end - start))) * 100);
}

async function load() {
	loading.value = true;
	error.value = "";
	try {
		workspace.value = await call(`${API}get_fiscal_year_workspace`);
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
	}
}

async function createYear() {
	if (!preview.value || alreadyExists.value || saving.value) return;
	if (!window.confirm(`Create FY ${preview.value.name} for Sevamrita Foundation?`)) return;
	saving.value = true;
	error.value = "";
	message.value = "";
	try {
		const name = preview.value.name;
		workspace.value = await call(`${API}create_fiscal_year`, { start_year: startYear.value });
		startYear.value = "";
		message.value = `FY ${name} is active for Sevamrita Foundation.`;
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		saving.value = false;
	}
}

async function activate(year) {
	if (saving.value || !year.can_activate) return;
	if (!window.confirm(`Reactivate FY ${year.name} for Sevamrita Foundation?`)) return;
	saving.value = true;
	error.value = "";
	message.value = "";
	try {
		workspace.value = await call(`${API}activate_fiscal_year`, { name: year.name });
		message.value = `FY ${year.name} is active again.`;
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		saving.value = false;
	}
}

onMounted(load);
</script>

<style scoped>
.year-row { display: flex; flex-wrap: wrap; align-items: center; gap: 0.875rem; padding: 1rem 1.25rem; }
.year-row + .year-row { border-top: 1px solid var(--line); }
.year-row--current { background: color-mix(in srgb, var(--navy-50) 55%, transparent); }
.year-tile { display: flex; width: 3.25rem; height: 3.25rem; flex-shrink: 0; flex-direction: column; align-items: center; justify-content: center; border-radius: 14px; background: var(--navy-900); color: #fff; line-height: 1.1; }
.year-tile--off { background: var(--soft); color: var(--muted); }
</style>
