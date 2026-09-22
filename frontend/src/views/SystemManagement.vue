<template>
	<div class="max-w-5xl mx-auto space-y-5">
		<PageHeader
			title="System Management"
			subtitle="Create login accounts and control system access through roles."
			eyebrow="Access"
		>
			<template #actions
				><button v-if="!editing" type="button" class="btn-primary" @click="beginNew">
					Add user</button
				><RouterLink to="/home" class="btn-secondary">Back to Home</RouterLink></template
			>
		</PageHeader>
		<p v-if="loading" class="text-muted" role="status">Loading users…</p>
		<p v-if="error" class="message-error" role="alert">{{ error }}</p>
		<p v-if="success" class="message-success" role="status">{{ success }}</p>

		<section v-if="!loading && editing" class="form-card">
			<div class="flex flex-wrap items-start justify-between gap-3 mb-5">
				<div>
					<h2 class="form-title mb-0">{{ form.name ? form.full_name : "Add user" }}</h2>
					<p class="form-hint mb-0">
						{{
							form.name ||
							"Create a login identity. HR links it to an Employee separately."
						}}
					</p>
				</div>
				<div class="flex flex-wrap gap-2">
					<button
						v-if="form.name"
						type="button"
						class="btn-secondary"
						:disabled="!form.enabled || resetting"
						@click="resetPassword"
					>
						{{ resetting ? "Sending…" : "Reset password" }}
					</button>
					<button type="button" class="btn-secondary" @click="cancelEdit">
						Back to users
					</button>
				</div>
			</div>
			<p v-if="form.name && !form.enabled" class="form-hint">
				Enable and save this account before sending a password reset link.
			</p>
			<form class="space-y-5" @submit.prevent="save">
				<div class="form-grid">
					<label v-if="!form.name" class="field-label sm:col-span-2"
						>Email / User ID *<input
							v-model.trim="form.email"
							type="email"
							required
							maxlength="140"
							autocomplete="email"
							class="field-input"
					/></label>
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
						>User type<select v-model="form.user_type" class="field-input">
							<option v-for="value in workspace.user_types" :key="value">
								{{ value }}
							</option></select
						><span class="field-help"
							>A role with Desk access makes the account a System User
							automatically.</span
						></label
					>
					<label class="flex items-start gap-2 text-sm"
						><input v-model="form.enabled" type="checkbox" class="mt-1" /><span
							><strong class="block">Enabled</strong
							><span class="text-muted">Allow this account to log in.</span></span
						></label
					>
					<label v-if="!form.name" class="flex items-start gap-2 text-sm"
						><input
							v-model="form.send_welcome_email"
							type="checkbox"
							class="mt-1"
						/><span
							><strong class="block">Send welcome email</strong
							><span class="text-muted"
								>Ask the user to set their password by email.</span
							></span
						></label
					>
				</div>
				<div class="rounded-2xl border border-line p-4">
					<h3 class="font-semibold text-ink">Access assignment</h3>
					<p class="text-sm text-muted mt-1">
						Use direct roles for individual access, or role profiles for a centrally
						maintained bundle.
					</p>
					<p class="text-sm text-muted mt-1">
						HR links an Employee record separately. Frappe assigns its Employee role
						after that link is made.
					</p>
					<div class="grid sm:grid-cols-2 gap-3 mt-4">
						<label
							:class="[
								'choice-card',
								form.role_mode === 'roles' && 'choice-card-active',
							]"
							><input v-model="form.role_mode" type="radio" value="roles" /><span
								><strong>Direct roles</strong
								><small>Choose exact roles for this user.</small></span
							></label
						>
						<label
							:class="[
								'choice-card',
								form.role_mode === 'profiles' && 'choice-card-active',
							]"
							><input v-model="form.role_mode" type="radio" value="profiles" /><span
								><strong>Role profiles</strong
								><small>Use one or more managed role bundles.</small></span
							></label
						>
					</div>
					<div v-if="form.role_mode === 'roles'" class="mt-4">
						<label class="field-label"
							>Find a role<input
								v-model.trim="roleSearch"
								class="field-input"
								placeholder="Search roles"
						/></label>
						<div class="option-grid mt-3">
							<label
								v-for="role in filteredRoles"
								:key="role.name"
								class="option-row"
								><input
									v-model="form.roles"
									type="checkbox"
									:value="role.name"
								/><span
									><strong>{{ role.name }}</strong
									><small>{{
										role.desk_access
											? "Desk access"
											: "Portal / background role"
									}}</small></span
								></label
							>
						</div>
					</div>
					<div v-else class="option-grid mt-4">
						<label
							v-for="profile in workspace.role_profiles"
							:key="profile.name"
							class="option-row"
							><input
								v-model="form.role_profiles"
								type="checkbox"
								:value="profile.name"
							/><span
								><strong>{{ profile.name }}</strong
								><small>{{
									profile.roles.join(", ") || "No roles configured"
								}}</small></span
							></label
						>
						<p v-if="!workspace.role_profiles.length" class="text-sm text-muted">
							No Role Profiles are configured.
						</p>
					</div>
				</div>
				<div class="rounded-xl bg-warn-soft p-3 text-sm text-ink">
					Role changes take effect immediately. Disable accounts instead of deleting them
					so historical approvals and transactions remain attributable.
				</div>
				<div class="flex justify-end">
					<button type="submit" class="btn-primary" :disabled="saving">
						{{ saving ? "Saving…" : "Save user and access" }}
					</button>
				</div>
			</form>
		</section>

		<template v-if="!loading && !editing">
			<section class="form-card">
				<div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem_12rem]">
					<label class="field-label"
						>Find a user<input
							v-model.trim="search"
							class="field-input"
							placeholder="Name, email or linked employee" /></label
					><label class="field-label"
						>Access<select v-model="enabledFilter" class="field-input">
							<option>All</option>
							<option>Enabled</option>
							<option>Disabled</option>
						</select></label
					><label class="field-label"
						>User type<select v-model="typeFilter" class="field-input">
							<option>All</option>
							<option v-for="value in workspace.user_types" :key="value">
								{{ value }}
							</option>
						</select></label
					>
				</div>
			</section>
			<p class="text-sm text-muted">{{ filteredUsers.length }} users</p>
			<div v-if="!filteredUsers.length" class="form-card text-center text-muted">
				No matching users.
			</div>
			<div class="grid gap-3 sm:grid-cols-2">
				<button
					v-for="user in filteredUsers"
					:key="user.name"
					type="button"
					class="directory-card text-left"
					@click="edit(user.name)"
				>
					<div class="flex items-start justify-between gap-3">
						<strong>{{ user.full_name || user.name }}</strong
						><span :class="['status-pill', !user.enabled && 'status-disabled']">{{
							user.enabled ? "Enabled" : "Disabled"
						}}</span>
					</div>
					<p class="text-xs text-muted mt-1 break-all">{{ user.name }}</p>
					<p class="text-sm mt-3">
						{{ user.user_type
						}}<template v-if="user.employee">
							· {{ user.employee.employee_name }} ({{
								user.employee.status
							}})</template
						>
					</p>
					<p class="text-sm text-accent font-medium mt-3">Manage user and roles →</p>
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
	resetting = ref(false),
	editing = ref(false);
const error = ref(""),
	success = ref(""),
	search = ref(""),
	roleSearch = ref("");
const enabledFilter = ref("All"),
	typeFilter = ref("All");
const workspace = reactive({ users: [], roles: [], role_profiles: [], user_types: [] });
const blank = () => ({
	name: "",
	modified: "",
	email: "",
	full_name: "",
	first_name: "",
	middle_name: "",
	last_name: "",
	enabled: true,
	user_type: "System User",
	send_welcome_email: true,
	role_mode: "roles",
	roles: [],
	role_profiles: [],
});
const form = reactive(blank());
const filteredRoles = computed(() => {
	const needle = roleSearch.value.toLowerCase();
	return workspace.roles.filter((role) => {
		if (!form.employee && ["Employee", "Employee Self Service"].includes(role.name))
			return false;
		return !needle || role.name.toLowerCase().includes(needle);
	});
});
const filteredUsers = computed(() => {
	const needle = search.value.toLowerCase();
	return workspace.users.filter((user) => {
		if (enabledFilter.value === "Enabled" && !user.enabled) return false;
		if (enabledFilter.value === "Disabled" && user.enabled) return false;
		if (typeFilter.value !== "All" && user.user_type !== typeFilter.value) return false;
		return (
			!needle ||
			[user.full_name, user.name, user.employee?.employee_name, user.employee?.name].some(
				(value) =>
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
	Object.assign(form, blank(), value, {
		enabled: value.enabled === undefined ? true : Boolean(value.enabled),
		roles: [...(value.roles || [])],
		role_profiles: [...(value.role_profiles || [])],
		role_mode: value.role_profiles?.length ? "profiles" : "roles",
	});
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
		applyWorkspace(await call(`${API}get_system_management_workspace`));
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
		resetForm(await call(`${API}get_managed_user`, { name }));
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
		const result = await call(`${API}save_managed_user`, {
			details: { ...form },
			name: form.name || null,
			expected_modified: form.modified || null,
		});
		applyWorkspace(result.workspace);
		resetForm(result.user);
		success.value = `${result.user.full_name || result.user.name} was saved.`;
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		saving.value = false;
	}
}
async function resetPassword() {
	if (!form.name || !form.enabled || resetting.value) return;
	if (!window.confirm(`Send a password reset link to ${form.name}?`)) return;
	resetting.value = true;
	error.value = "";
	success.value = "";
	try {
		await call(`${API}send_managed_user_password_reset`, { name: form.name });
		success.value = `A password reset link was sent to ${form.name}.`;
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		resetting.value = false;
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
	@apply rounded-full bg-ok-soft px-2.5 py-1 text-xs text-ok;
}
.status-disabled {
	@apply bg-soft text-muted;
}
.choice-card {
	@apply flex cursor-pointer items-start gap-3 rounded-xl border border-line bg-bg p-3;
}
.choice-card-active {
	@apply border-accent bg-accent-soft;
}
.choice-card span,
.option-row span {
	@apply min-w-0;
}
.choice-card strong,
.choice-card small,
.option-row strong,
.option-row small {
	@apply block;
}
.choice-card small,
.option-row small {
	@apply text-xs text-muted mt-0.5;
}
.option-grid {
	@apply grid max-h-80 gap-2 overflow-y-auto sm:grid-cols-2;
}
.option-row {
	@apply flex items-start gap-2 rounded-xl border border-line bg-bg p-3 text-sm;
}
</style>
