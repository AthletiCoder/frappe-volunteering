<template>
	<div class="mx-auto max-w-5xl space-y-5">
		<PageHeader
			title="Fiscal years"
			eyebrow="System management"
			subtitle="Keep the accounting years Sevamrita still needs available for correctly dated entries."
		>
			<template #actions><RouterLink to="/home" class="btn-secondary">Back to Home</RouterLink></template>
		</PageHeader>

		<p v-if="error" class="message-error" role="alert">{{ error }}</p>
		<p v-if="message" class="message-success" role="status">{{ message }}</p>
		<p v-if="loading" class="text-muted" role="status">Loading fiscal years…</p>

		<template v-else-if="workspace">
			<section class="rounded-2xl border border-line bg-accent-soft p-5 text-sm leading-relaxed">
				<strong class="text-ink">More than one fiscal year can remain active.</strong>
				<p class="mt-1 text-muted">
					Adding or reactivating a year does not close another year, change the default, or override an accounting freeze.
					Post each entry using its correct accounting date.
				</p>
			</section>

			<section class="form-card">
				<div class="mb-5 flex flex-wrap items-start justify-between gap-3">
					<div>
						<h2 class="text-lg font-semibold text-ink">Sevamrita’s fiscal years</h2>
						<p class="mt-1 text-sm text-muted">April–March years available to Sevamrita Foundation.</p>
					</div>
					<span class="rounded-full bg-soft px-3 py-1 text-xs font-semibold text-ink">{{ activeCount }} active</span>
				</div>
				<p v-if="!workspace.years.length" class="rounded-xl bg-soft p-4 text-sm text-muted">No April–March fiscal years are configured yet.</p>
				<div v-else class="space-y-3">
					<article v-for="year in workspace.years" :key="year.name" class="year-row">
						<div class="min-w-0">
							<div class="flex flex-wrap items-center gap-2">
								<h3 class="font-semibold text-ink">FY {{ year.name }}</h3>
								<span :class="['status-pill', year.active ? 'status-active' : 'status-disabled']">{{ year.active ? 'Active' : 'Disabled' }}</span>
								<span v-if="year.current" class="text-xs font-medium text-accent">Current dates</span>
							</div>
							<p class="mt-1 text-sm text-muted">{{ dateLabel(year.start_date) }} – {{ dateLabel(year.end_date) }}</p>
							<p v-if="!year.active && !year.can_activate" class="mt-1 text-xs text-muted">This shared year affects other companies; review it in Desk before enabling it.</p>
						</div>
						<button v-if="!year.active && year.can_activate" type="button" class="btn-secondary shrink-0" :disabled="saving" @click="activate(year)">
							{{ saving ? 'Working…' : 'Reactivate' }}
						</button>
					</article>
				</div>
			</section>

			<section class="form-card">
				<h2 class="text-lg font-semibold text-ink">Add a missing year</h2>
				<p class="mt-1 text-sm text-muted">Enter the calendar year in which the fiscal year starts. The dates are set automatically for Sevamrita’s April–March cycle.</p>
				<form class="mt-5 space-y-5" @submit.prevent="createYear">
					<label class="field-label max-w-sm">Starting year *
						<input v-model.trim="startYear" type="number" min="2000" max="2098" step="1" required inputmode="numeric" placeholder="For example, 2025" class="field-input" />
					</label>
					<div v-if="preview" class="rounded-xl border border-line bg-soft p-4 text-sm">
						<strong class="text-ink">FY {{ preview.name }}</strong>
						<p class="mt-1 text-muted">{{ preview.start }} – {{ preview.end }} · Sevamrita Foundation · Active</p>
					</div>
					<div class="flex justify-end">
						<button type="submit" class="btn-primary" :disabled="saving || !preview || alreadyExists">
							{{ alreadyExists ? 'Year already exists' : saving ? 'Creating…' : 'Create fiscal year' }}
						</button>
					</div>
				</form>
			</section>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
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
.form-card { @apply rounded-2xl border border-line bg-surface p-4 shadow-soft sm:p-6; }
.year-row { @apply flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-bg p-4; }
.status-pill { @apply rounded-full px-2.5 py-1 text-xs font-semibold; }
.status-active { @apply bg-ok-soft text-ok; }
.status-disabled { @apply bg-soft text-muted; }
.field-label { @apply block text-sm font-medium text-ink; }
.field-input { @apply mt-1 w-full rounded-xl border border-line bg-surface px-3 py-2.5 text-ink; }
.message-error { @apply rounded-xl border border-bad bg-bad-soft p-4 text-sm text-bad; }
.message-success { @apply rounded-xl border border-ok bg-ok-soft p-4 text-sm text-ink; }
</style>
