<template>
	<div class="max-w-5xl mx-auto space-y-5">
		<PageHeader
			title="Project account mapping"
			eyebrow="Accounts"
			subtitle="Suggest one or more ledger accounts for each approved expense break-up. Final classification still happens on each claim."
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
			<section v-if="!selected" class="form-card">
				<h2 class="form-title">Approved projects</h2>
				<p class="form-hint">
					Suggestions are optional and do not block claims. They help Accounts classify
					each approved claim quickly before it is posted.
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
						:disabled="saving || Boolean(openingProject)"
						:data-project-name="project.name"
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
									: "No account suggestions yet"
						}}</span>
					</button>
				</div>
			</section>
			<form
				v-if="selected"
				ref="mappingForm"
				class="form-card"
				tabindex="-1"
				@submit.prevent="save"
			>
				<div class="flex flex-wrap items-start justify-between gap-3 mb-3">
					<div>
						<h2 class="form-title mb-0">{{ selected.project_name }}</h2>
						<p class="text-sm text-muted">{{ selected.name }}</p>
					</div>
					<button type="button" class="btn-secondary" @click="closeProject">
						Choose another project
					</button>
				</div>
				<p class="form-hint">
					A label may suggest several ledger accounts, and the same account may serve
					several labels. These suggestions can be changed later without rewriting old claims.
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
						<div class="space-y-3">
							<div
								v-for="(account, index) in row.expense_accounts"
								:key="`${row.budget_key}-${index}`"
								class="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"
							>
								<SearchSelect
									v-model="row.expense_accounts[index]"
									:label="`Suggested account ${index + 1}`"
									:disabled="selected.closed || saving"
									:options="accountOptions(row, index)"
								/>
								<button
									type="button"
									class="btn-secondary text-bad"
									:disabled="selected.closed || saving"
									@click="removeAccount(row, index)"
								>
									Remove
								</button>
							</div>
							<button
								v-if="!selected.closed"
								type="button"
								class="btn-secondary"
								:disabled="saving"
								@click="addAccount(row)"
							>
								+ Suggest an account
							</button>
							<p v-if="!row.expense_accounts.length" class="field-help">
								No suggestion. Employees may still claim against this label; Accounts will
								choose the ledger before posting.
							</p>
						</div>
					</section>
				</div>
				<button
					v-if="!selected.closed"
					class="btn-primary mt-5"
					type="submit"
					:disabled="saving || !selected.rows.length"
				>
					{{ saving ? "Saving…" : "Save account suggestions" }}
				</button>
			</form>
		</template>
	</div>
</template>

<script setup>
import { nextTick, onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import SearchSelect from "../components/SearchSelect.vue";
import { call } from "../lib/frappe";

const service = "volunteering.volunteering.project_account_mapping.";
const route = useRoute();
const router = useRouter();
const projects = ref([]),
	selected = ref(null),
	accounts = ref([]);
const loading = ref(true),
	saving = ref(false),
	openingProject = ref(""),
	authorized = ref(false),
	error = ref(""),
	message = ref("");
const mappingForm = ref(null);
const currency = (amount) =>
	new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(amount || 0);

function accountOptions(row, currentIndex) {
	const options = accounts.value.map((account) => ({
		value: account.name,
		label: account.account_name,
		description: account.name,
	}));
	const current = row.expense_accounts[currentIndex];
	return options.filter(
		(option) => option.value === current || !row.expense_accounts.includes(option.value),
	);
}
function addAccount(row) {
	row.expense_accounts.push("");
}
function removeAccount(row, index) {
	row.expense_accounts.splice(index, 1);
}
async function open(project) {
	error.value = "";
	message.value = "";
	openingProject.value = project;
	try {
		const result = await call(service + "get_mapping_workspace", { project });
		selected.value = result.project;
		accounts.value = result.accounts;
		await router.replace({ query: { ...route.query, project } });
		await nextTick();
		mappingForm.value?.scrollIntoView({ behavior: "smooth", block: "start" });
		mappingForm.value?.focus({ preventScroll: true });
	} catch (err) {
		selected.value = null;
		error.value = err.message || "Unable to load account mappings.";
	} finally {
		openingProject.value = "";
	}
}
async function closeProject() {
	selected.value = null;
	accounts.value = [];
	error.value = "";
	message.value = "";
	const query = { ...route.query };
	delete query.project;
	await router.replace({ query });
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
				expense_accounts: row.expense_accounts.filter(Boolean),
			})),
		});
		projects.value = (await call(service + "get_mapping_workspace")).projects;
		message.value =
			"Account suggestions saved. Claims remain available even when a label has no suggestion.";
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
