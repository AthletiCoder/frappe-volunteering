<template>
	<div class="max-w-5xl mx-auto space-y-5">
		<PageHeader
			title="Project account mapping"
			eyebrow="Accounts"
			subtitle="Map approved employee-facing labels to ledger accounts. Labels, allocations and project details cannot be changed here."
		>
			<template #actions
				><RouterLink to="/home" class="btn-secondary">Back to Home</RouterLink></template
			>
		</PageHeader>
		<div
			v-if="error"
			role="alert"
			class="rounded-xl border border-bad bg-bad-soft p-4 text-sm text-bad"
		>
			{{ error }}
		</div>
		<div v-if="message" role="status" class="rounded-xl bg-ok-soft p-4 text-sm">
			{{ message }}
		</div>
		<div v-if="loading" class="text-muted">Loading approved projects…</div>
		<template v-else-if="authorized">
			<section class="form-card">
				<h2 class="form-title">Approved projects</h2>
				<p class="form-hint">
					New claims become available once every active label has an account. Only
					Accounts Managers can save mappings.
				</p>
				<div v-if="!projects.length" class="text-muted text-sm">
					No manager-approved projects are available.
				</div>
				<div class="space-y-2">
					<button
						v-for="project in projects"
						:key="project.name"
						type="button"
						@click="open(project.name)"
						class="w-full rounded-xl border border-line p-3 text-left flex flex-wrap justify-between gap-2"
						:disabled="saving"
					>
						<span class="font-semibold text-sm"
							>{{ project.project_name }}
							<span class="text-muted font-normal">· {{ project.name }}</span></span
						>
						<span class="text-xs text-muted">{{
							project.closed
								? "Closed"
								: project.ready
									? "Mapped"
									: "Awaiting account mapping"
						}}</span>
					</button>
				</div>
			</section>
			<form v-if="selected" class="form-card" @submit.prevent="save">
				<h2 class="form-title">{{ selected.project_name }}</h2>
				<p class="form-hint">
					The same ledger account may serve several labels; each label keeps its own
					claim budget. A mapping is locked once its label is used in a claim.
				</p>
				<div v-if="selected.closed" class="text-muted text-sm mb-4">
					This project is closed; its mappings cannot be changed.
				</div>
				<div class="space-y-4">
					<section
						v-for="row in selected.rows"
						:key="row.budget_key"
						class="rounded-xl border border-line bg-bg p-4"
					>
						<div class="flex flex-wrap justify-between gap-2 mb-3">
							<h3 class="font-semibold">{{ row.employee_label }}</h3>
							<span class="text-sm text-muted"
								>Approved allocation: {{ currency(row.approved_amount)
								}}{{ row.is_active ? "" : " · Disabled for new claims" }}</span
							>
						</div>
						<SearchSelect
							v-model="row.expense_account"
							:label="`Ledger account for ${row.employee_label}`"
							:required="Boolean(row.is_active)"
							:disabled="row.locked || selected.closed || saving"
							:options="accountOptions(row)"
						/>
						<p v-if="row.locked" class="field-help mt-2">
							Used in an existing claim. Propose a new label if a different account
							is needed for future bills.
						</p>
					</section>
				</div>
				<button
					v-if="!selected.closed"
					class="btn-primary mt-5"
					type="submit"
					:disabled="saving || !selected.rows.length"
				>
					{{ saving ? "Saving…" : "Save account mappings" }}
				</button>
			</form>
		</template>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import SearchSelect from "../components/SearchSelect.vue";
import { call } from "../lib/frappe";

const service = "volunteering.volunteering.project_account_mapping.";
const route = useRoute();
const projects = ref([]),
	selected = ref(null),
	accounts = ref([]);
const loading = ref(true),
	saving = ref(false),
	authorized = ref(false),
	error = ref(""),
	message = ref("");
const currency = (amount) =>
	new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(amount || 0);

function accountOptions(row) {
	const options = accounts.value.map((account) => ({
		value: account.name,
		label: account.account_name,
		description: account.name,
	}));
	if (row.expense_account && !options.some((option) => option.value === row.expense_account))
		options.push({ value: row.expense_account, label: row.expense_account });
	return options;
}
async function open(project) {
	error.value = "";
	message.value = "";
	try {
		const result = await call(service + "get_mapping_workspace", { project });
		selected.value = result.project;
		accounts.value = result.accounts;
	} catch (err) {
		selected.value = null;
		error.value = err.message || "Unable to load account mappings.";
	}
}
async function save() {
	saving.value = true;
	error.value = "";
	message.value = "";
	try {
		selected.value = await call(service + "save_account_mapping", {
			project: selected.value.name,
			modified: selected.value.modified,
			mappings: selected.value.rows.map((row) => ({
				budget_key: row.budget_key,
				expense_account: row.expense_account,
			})),
		});
		projects.value = (await call(service + "get_mapping_workspace")).projects;
		message.value =
			"Account mappings saved. Employees can now select the active expense labels.";
	} catch (err) {
		error.value = err.message || "Unable to save account mappings.";
	} finally {
		saving.value = false;
	}
}
onMounted(async () => {
	try {
		projects.value = (await call(service + "get_mapping_workspace")).projects;
		authorized.value = true;
		if (route.query.project) await open(route.query.project);
	} catch (err) {
		error.value = err.message || "Only Accounts Managers can access this page.";
	} finally {
		loading.value = false;
	}
});
</script>
