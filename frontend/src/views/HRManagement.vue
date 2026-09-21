<template>
	<div class="max-w-5xl mx-auto space-y-5">
		<PageHeader
			title="HR Management"
			subtitle="Create employee records and maintain employment and reporting details."
			eyebrow="People"
		>
			<template #actions>
				<button v-if="!editing" type="button" class="btn-primary" @click="beginNew">
					Add employee
				</button>
				<RouterLink to="/home" class="btn-secondary">Back to Home</RouterLink>
			</template>
		</PageHeader>

		<p v-if="loading" class="text-muted" role="status">Loading employees…</p>
		<p v-if="error" class="message-error" role="alert">{{ error }}</p>
		<p v-if="success" class="message-success" role="status">{{ success }}</p>

		<section v-if="!loading && editing" class="form-card">
			<div class="flex flex-wrap items-start justify-between gap-3 mb-5">
				<div>
					<h2 class="form-title mb-0">
						{{ form.name ? form.employee_name : "Add employee" }}
					</h2>
					<p class="form-hint mb-0">
						{{ form.name || "The employee number will be assigned automatically." }}
					</p>
				</div>
				<button type="button" class="btn-secondary" @click="cancelEdit">
					Back to directory
				</button>
			</div>

			<form class="form-grid" @submit.prevent="save">
				<label class="field-label"
					>First name *<input
						v-model.trim="form.first_name"
						required
						maxlength="140"
						class="field-input"
				/></label>
				<label class="field-label"
					>Middle name<input
						v-model.trim="form.middle_name"
						maxlength="140"
						class="field-input"
				/></label>
				<label class="field-label"
					>Last name<input
						v-model.trim="form.last_name"
						maxlength="140"
						class="field-input"
				/></label>
				<label class="field-label"
					>Status *<select v-model="form.status" required class="field-input">
						<option v-for="status in workspace.options.statuses" :key="status">
							{{ status }}
						</option>
					</select></label
				>

				<label class="field-label"
					>Gender *<select v-model="form.gender" required class="field-input">
						<option value="">Select gender</option>
						<option v-for="gender in workspace.options.genders" :key="gender">
							{{ gender }}
						</option>
					</select></label
				>
				<label class="field-label"
					>Date of birth *<input
						v-model="form.date_of_birth"
						type="date"
						required
						class="field-input"
				/></label>
				<label class="field-label"
					>Date of joining *<input
						v-model="form.date_of_joining"
						type="date"
						required
						class="field-input"
				/></label>
				<label v-if="form.status === 'Left'" class="field-label"
					>Relieving date *<input
						v-model="form.relieving_date"
						type="date"
						required
						class="field-input"
				/></label>

				<label class="field-label sm:col-span-2"
					>Linked User account<select v-model="form.user_id" class="field-input">
						<option value="">No login account linked</option>
						<option
							v-for="user in workspace.options.users"
							:key="user.name"
							:value="user.name"
							:disabled="user.linked && user.name !== form.user_id"
						>
							{{ user.full_name || user.name }} · {{ user.name
							}}{{
								user.linked && user.name !== form.user_id
									? " · already linked"
									: ""
							}}
						</option></select
					><span class="field-help"
						>System Management creates login accounts. HR links an existing account
						here.</span
					></label
				>

				<label class="field-label"
					>Department<select v-model="form.department" class="field-input">
						<option value="">Not assigned</option>
						<option v-for="value in workspace.options.departments" :key="value">
							{{ value }}
						</option>
					</select></label
				>
				<label class="field-label"
					>Designation<select v-model="form.designation" class="field-input">
						<option value="">Not assigned</option>
						<option v-for="value in workspace.options.designations" :key="value">
							{{ value }}
						</option>
					</select></label
				>
				<label v-if="workspace.options.grades.length" class="field-label"
					>Grade<select v-model="form.grade" class="field-input">
						<option value="">Not assigned</option>
						<option v-for="value in workspace.options.grades" :key="value">
							{{ value }}
						</option></select
					><span class="field-help"
						>Grade controls financial approval authority.</span
					></label
				>
				<label class="field-label"
					>Employment type<select v-model="form.employment_type" class="field-input">
						<option value="">Not assigned</option>
						<option v-for="value in workspace.options.employment_types" :key="value">
							{{ value }}
						</option>
					</select></label
				>
				<label class="field-label sm:col-span-2"
					>Reports to<select v-model="form.reports_to" class="field-input">
						<option value="">No reporting manager</option>
						<option
							v-for="employee in reportingManagers"
							:key="employee.name"
							:value="employee.name"
						>
							{{ employee.employee_name }} · {{ employee.name }}
						</option>
					</select></label
				>

				<label class="field-label"
					>Mobile<input
						v-model.trim="form.cell_number"
						type="tel"
						maxlength="40"
						class="field-input"
				/></label>
				<label class="field-label"
					>Company email<input
						v-model.trim="form.company_email"
						type="email"
						maxlength="140"
						class="field-input"
				/></label>
				<label class="field-label sm:col-span-2"
					>Personal email<input
						v-model.trim="form.personal_email"
						type="email"
						maxlength="140"
						class="field-input"
				/></label>

				<div class="sm:col-span-2 rounded-xl bg-soft p-3 text-sm text-muted">
					Employee records are retained for audit history. To end access, mark the
					employee Left or Inactive and disable their User account separately.
				</div>
				<div class="sm:col-span-2 flex justify-end">
					<button type="submit" class="btn-primary" :disabled="saving">
						{{ saving ? "Saving…" : "Save employee" }}
					</button>
				</div>
			</form>
		</section>

		<template v-if="!loading && !editing">
			<section class="form-card">
				<div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_14rem]">
					<label class="field-label"
						>Find an employee<input
							v-model.trim="search"
							class="field-input"
							placeholder="Name, employee ID, email or department"
					/></label>
					<label class="field-label"
						>Status<select v-model="statusFilter" class="field-input">
							<option>All</option>
							<option v-for="status in workspace.options.statuses" :key="status">
								{{ status }}
							</option>
						</select></label
					>
				</div>
			</section>
			<p class="text-sm text-muted">{{ filteredEmployees.length }} employees</p>
			<div v-if="!filteredEmployees.length" class="form-card text-center text-muted">
				No matching employees.
			</div>
			<div class="grid gap-3 sm:grid-cols-2">
				<button
					v-for="employee in filteredEmployees"
					:key="employee.name"
					type="button"
					class="directory-card text-left"
					@click="edit(employee.name)"
				>
					<div class="flex items-start justify-between gap-3">
						<strong>{{ employee.employee_name }}</strong
						><span class="status-pill">{{ employee.status }}</span>
					</div>
					<p class="text-xs text-muted mt-1">
						{{ employee.name
						}}<template v-if="employee.user_id"> · {{ employee.user_id }}</template>
					</p>
					<p class="text-sm mt-3">
						{{
							[employee.designation, employee.grade, employee.department]
								.filter(Boolean)
								.join(" · ") || "Employment details not assigned"
						}}
					</p>
					<p class="text-sm text-accent font-medium mt-3">Open employee →</p>
				</button>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { call } from "../lib/frappe";

const API = "volunteering.volunteering.people_management.";
const loading = ref(true),
	saving = ref(false),
	editing = ref(false);
const error = ref(""),
	success = ref(""),
	search = ref(""),
	statusFilter = ref("All");
const workspace = reactive({
	employees: [],
	options: {
		statuses: [],
		genders: [],
		departments: [],
		designations: [],
		grades: [],
		employment_types: [],
		reporting_managers: [],
		users: [],
	},
});
const blank = () => ({
	name: "",
	modified: "",
	employee_name: "",
	first_name: "",
	middle_name: "",
	last_name: "",
	status: "Active",
	gender: "",
	date_of_birth: "",
	date_of_joining: "",
	relieving_date: "",
	user_id: "",
	department: "",
	designation: "",
	grade: "",
	employment_type: "",
	reports_to: "",
	cell_number: "",
	company_email: "",
	personal_email: "",
});
const form = reactive(blank());
const reportingManagers = computed(() =>
	workspace.options.reporting_managers.filter(
		(employee) => employee.status === "Active" && employee.name !== form.name,
	),
);
const filteredEmployees = computed(() => {
	const needle = search.value.toLowerCase();
	return workspace.employees.filter((employee) => {
		if (statusFilter.value !== "All" && employee.status !== statusFilter.value) return false;
		return (
			!needle ||
			[
				employee.employee_name,
				employee.name,
				employee.user_id,
				employee.department,
				employee.designation,
				employee.grade,
			].some((value) =>
				String(value || "")
					.toLowerCase()
					.includes(needle),
			)
		);
	});
});
function applyWorkspace(value) {
	Object.assign(workspace, value || {});
}
function resetForm(value = {}) {
	Object.assign(form, blank(), value);
}
function beginNew() {
	resetForm();
	editing.value = true;
	error.value = "";
	success.value = "";
}
function cancelEdit() {
	editing.value = false;
	resetForm();
	error.value = "";
}
async function load() {
	loading.value = true;
	error.value = "";
	try {
		applyWorkspace(await call(`${API}get_hr_management_workspace`));
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
	}
}
async function edit(name) {
	error.value = "";
	success.value = "";
	try {
		resetForm(await call(`${API}get_managed_employee`, { name }));
		editing.value = true;
		window.scrollTo({ top: 0, behavior: "smooth" });
	} catch (e) {
		error.value = e.message || String(e);
	}
}
async function save() {
	saving.value = true;
	error.value = "";
	success.value = "";
	try {
		const result = await call(`${API}save_managed_employee`, {
			details: { ...form },
			name: form.name || null,
			expected_modified: form.modified || null,
		});
		applyWorkspace(result.workspace);
		resetForm(result.employee);
		success.value = `${result.employee.employee_name} was saved.`;
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		saving.value = false;
	}
}
onMounted(load);
</script>

<style scoped>
.form-card {
	@apply rounded-2xl border border-line bg-surface p-4 sm:p-5 shadow-soft;
}
.form-title {
	@apply text-lg font-semibold text-ink mb-3;
}
.form-hint {
	@apply text-sm text-muted mb-4;
}
.form-grid {
	@apply grid sm:grid-cols-2 gap-3;
}
.field-label {
	@apply text-sm font-medium text-ink;
}
.field-input {
	@apply mt-1 w-full rounded-xl border border-line bg-bg px-3 py-2 text-ink;
}
.field-help {
	@apply block text-xs text-muted mt-1;
}
.directory-card {
	@apply rounded-2xl border border-line bg-surface p-4 shadow-soft hover:shadow-lift transition-all;
}
.message-error {
	@apply rounded-xl border border-bad bg-bad-soft p-3 text-sm text-bad;
}
.message-success {
	@apply rounded-xl border border-ok bg-ok-soft p-3 text-sm text-ink;
}
.status-pill {
	@apply rounded-full bg-soft px-2.5 py-1 text-xs text-muted;
}
</style>
