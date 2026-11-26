<template>
	<div class="mx-auto max-w-6xl space-y-5">
		<PageHeader
			title="HR Management"
			subtitle="Create employee records and maintain employment and reporting details."
			eyebrow="People"
		>
			<template #actions>
				<button v-if="!editing" type="button" class="btn-primary" @click="beginNew">
					Add employee
				</button>
				<RouterLink to="/home" class="btn-back">Back to Home</RouterLink>
			</template>
		</PageHeader>

		<p v-if="loading" class="text-muted" role="status">Loading employees…</p>
		<p v-if="error" class="message-error" role="alert">{{ error }}</p>
		<p v-if="success" class="message-success" role="status">{{ success }}</p>

		<div v-if="!loading && editing" class="form-layout">
			<form class="kit-panel step-panel min-w-0" @submit.prevent="save">
				<fieldset class="form-step">
					<legend class="form-step__title"><span aria-hidden="true" class="step-num" :class="{ 'step-num--done': form.first_name && form.gender && form.date_of_birth }">1</span>Name and identity</legend>
					<div class="form-step__grid">
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
						<label class="field-label sm:col-span-2"
							>Last name<input
								v-model.trim="form.last_name"
								maxlength="140"
								class="field-input"
						/></label>
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
					</div>
				</fieldset>

				<fieldset class="form-step">
					<legend class="form-step__title"><span aria-hidden="true" class="step-num" :class="{ 'step-num--done': form.status && form.date_of_joining }">2</span>Employment</legend>
					<div class="form-step__grid">
						<label class="field-label"
							>Status *<select v-model="form.status" required class="field-input">
								<option v-for="status in workspace.options.statuses" :key="status">
									{{ status }}
								</option>
							</select></label
						>
						<label class="field-label"
							>Date of joining *<input
								v-model="form.date_of_joining"
								type="date"
								required
								class="field-input"
						/></label>
						<label v-if="form.status === 'Left'" class="field-label sm:col-span-2"
							>Relieving date *<input
								v-model="form.relieving_date"
								type="date"
								required
								class="field-input"
						/></label>
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
					</div>
				</fieldset>

				<fieldset class="form-step">
					<legend class="form-step__title"><span aria-hidden="true" class="step-num" :class="{ 'step-num--done': form.user_id }">3</span>Login and reporting</legend>
					<div class="form-step__grid">
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
					</div>
				</fieldset>

				<fieldset class="form-step">
					<legend class="form-step__title"><span aria-hidden="true" class="step-num" :class="{ 'step-num--done': form.cell_number || form.company_email || form.personal_email }">4</span>Contact</legend>
					<div class="form-step__grid">
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
					</div>
				</fieldset>

				<div class="form-step__foot">
					<button type="button" class="btn-secondary" @click="cancelEdit">
						Back to directory
					</button>
					<button type="submit" class="btn-primary" :disabled="saving">
						{{ saving ? "Saving…" : "Save employee" }}
					</button>
				</div>
			</form>

			<aside class="form-rail min-w-0 space-y-4" aria-label="Employee summary">
				<div class="kit-panel record-card">
					<div class="record-card__head">
						<Avatar :name="previewName || 'New employee'" size="lg" />
						<div class="min-w-0">
							<h2 class="truncate font-display text-base font-semibold text-ink">
								{{ form.name ? form.employee_name : "Add employee" }}
							</h2>
							<p class="truncate text-xs text-muted">
								{{ form.name || "The employee number will be assigned automatically." }}
							</p>
						</div>
					</div>
					<dl class="summary-list">
						<div><dt>Status</dt><dd><span :class="pillClass(employeeTone(form.status))">{{ form.status || "—" }}</span></dd></div>
						<div><dt>Role</dt><dd>{{ [form.designation, form.grade].filter(Boolean).join(" · ") || "Not assigned" }}</dd></div>
						<div><dt>Department</dt><dd>{{ form.department || "Not assigned" }}</dd></div>
						<div><dt>Reports to</dt><dd>{{ managerName || "No manager" }}</dd></div>
						<div><dt>Login</dt><dd>{{ form.user_id || "Not linked" }}</dd></div>
					</dl>
				</div>
				<p class="rounded-2xl bg-soft p-4 text-sm text-muted">
					Employee records are retained for audit history. To end access, mark the
					employee Left or Inactive and disable their User account separately.
				</p>
			</aside>
		</div>

		<div v-if="!loading && !editing" class="list-board">
			<aside class="min-w-0">
				<div class="filter-rail kit-panel" role="group" aria-label="Filter employees by status">
					<button
						v-for="option in statusOptions"
						:key="option"
						type="button"
						class="filter-btn"
						:class="{ 'filter-btn--active': statusFilter === option }"
						:aria-pressed="statusFilter === option"
						@click="statusFilter = option"
					>
						<span class="filter-btn__dot" :class="dotClass(option === 'All' ? 'info' : employeeTone(option))"></span>
						<span class="min-w-0 flex-1 truncate text-left">{{ option }}</span>
						<span class="filter-btn__count">{{ statusCounts[option] || 0 }}</span>
					</button>
				</div>
			</aside>
			<section class="min-w-0 space-y-3" aria-label="Employees">
				<label class="field-label relative block"
					><span class="sr-only">Find an employee</span
					><Icon name="search" size="sm" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" /><input
						v-model.trim="search"
						class="field-input !mt-0 pl-9"
						aria-label="Find an employee"
						placeholder="Name, employee ID, email or department"
				/></label>
				<p class="text-sm text-muted">{{ filteredEmployees.length }} employees</p>
				<div v-if="!filteredEmployees.length" class="kit-panel px-6 py-12 text-center text-muted">
					No matching employees.
				</div>
				<div v-else class="kit-panel overflow-hidden">
					<button
						v-for="employee in filteredEmployees"
						:key="employee.name"
						type="button"
						class="directory-card dir-row"
						@click="edit(employee.name)"
					>
						<Avatar :name="employee.employee_name" />
						<span class="min-w-0">
							<strong class="block truncate text-sm text-ink">{{ employee.employee_name }}</strong>
							<span class="block truncate text-xs text-muted"
								>{{ employee.name
								}}<template v-if="employee.user_id"> · {{ employee.user_id }}</template></span
							>
						</span>
						<span class="dir-row__meta truncate">{{
							[employee.designation, employee.grade, employee.department]
								.filter(Boolean)
								.join(" · ") || "Employment details not assigned"
						}}</span>
						<span :class="pillClass(employeeTone(employee.status))">{{ employee.status }}</span>
						<Icon name="arrow-right" size="sm" class="dir-row__arrow" />
					</button>
				</div>
			</section>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import Avatar from "../components/Avatar.vue";
import Icon from "../components/Icon.vue";
import { dotClass, pillClass } from "../lib/tones.js";
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
const statusOptions = computed(() => ["All", ...workspace.options.statuses]);
const statusCounts = computed(() => {
	const counts = { All: workspace.employees.length };
	for (const employee of workspace.employees)
		counts[employee.status] = (counts[employee.status] || 0) + 1;
	return counts;
});
const previewName = computed(
	() =>
		form.employee_name ||
		[form.first_name, form.middle_name, form.last_name].filter(Boolean).join(" "),
);
const managerName = computed(() => {
	if (!form.reports_to) return "";
	const manager = workspace.options.reporting_managers.find((row) => row.name === form.reports_to);
	return manager?.employee_name || form.reports_to;
});
function employeeTone(status) {
	if (status === "Active") return "ok";
	if (status === "Left") return "muted";
	if (status === "Inactive" || status === "Suspended") return "warn";
	return "info";
}
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
