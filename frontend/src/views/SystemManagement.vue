<template>
	<div class="mx-auto max-w-6xl space-y-5">
		<PageHeader
			title="System Management"
			subtitle="Create login accounts and control system access through roles."
			eyebrow="Access"
		>
			<template #actions>
				<RouterLink to="/fiscal-years" class="btn-secondary">Fiscal years</RouterLink>
				<button v-if="!editing" type="button" class="btn-primary" @click="beginNew">Add user</button>
				<RouterLink to="/home" class="btn-back">Back to Home</RouterLink>
			</template>
		</PageHeader>
		<p v-if="loading" class="text-muted" role="status">Loading users…</p>
		<p v-if="error" class="message-error" role="alert">{{ error }}</p>
		<p v-if="success" class="message-success" role="status">{{ success }}</p>

		<div v-if="!loading && editing" class="form-layout">
			<form class="kit-panel step-panel min-w-0" @submit.prevent="save">
				<fieldset class="form-step">
					<legend class="form-step__title"><span aria-hidden="true" class="step-num" :class="{ 'step-num--done': (form.name || form.email) && form.first_name }">1</span>Login identity</legend>
					<div class="form-step__grid">
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
					</div>
					<div class="mt-4 grid gap-3 sm:grid-cols-2">
						<label class="check-card"
							><input v-model="form.enabled" type="checkbox" /><span
								><strong>Enabled</strong
								><small>Allow this account to log in.</small></span
							></label
						>
						<label v-if="!form.name" class="check-card"
							><input v-model="form.send_welcome_email" type="checkbox" /><span
								><strong>Send welcome email</strong
								><small>Ask the user to set their password by email.</small></span
							></label
						>
					</div>
				</fieldset>

				<fieldset class="form-step">
					<legend class="form-step__title"><span aria-hidden="true" class="step-num" :class="{ 'step-num--done': accessCount }">2</span>Access assignment</legend>
					<p class="text-sm text-muted">
						Use direct roles for individual access, or role profiles for a centrally
						maintained bundle. HR links an Employee record separately. Frappe assigns its
						Employee role after that link is made.
					</p>
					<div class="mt-4 grid gap-3 sm:grid-cols-2">
						<label class="check-card"
							><input v-model="form.role_mode" type="radio" value="roles" /><span
								><strong>Direct roles</strong
								><small>Choose exact roles for this user.</small></span
							></label
						>
						<label class="check-card"
							><input v-model="form.role_mode" type="radio" value="profiles" /><span
								><strong>Role profiles</strong
								><small>Use one or more managed role bundles.</small></span
							></label
						>
					</div>
					<div v-if="form.role_mode === 'roles'" class="mt-4">
						<label class="field-label relative block"
							><span class="sr-only">Find a role</span
							><Icon name="search" size="sm" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" /><input
								v-model.trim="roleSearch"
								class="field-input !mt-0 pl-9"
								aria-label="Find a role"
								placeholder="Search roles"
						/></label>
						<div class="option-grid mt-3">
							<label
								v-for="role in filteredRoles"
								:key="role.name"
								class="check-card option-row"
								><input
									v-model="form.roles"
									type="checkbox"
									:value="role.name"
								/><span class="min-w-0"
									><strong class="truncate">{{ role.name }}</strong
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
							class="check-card option-row"
							><input
								v-model="form.role_profiles"
								type="checkbox"
								:value="profile.name"
							/><span class="min-w-0"
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
				</fieldset>

				<div class="form-step__foot">
					<button type="button" class="btn-secondary" @click="cancelEdit">
						Back to users
					</button>
					<button type="submit" class="btn-primary" :disabled="saving || resetting">
						{{ saving ? "Saving…" : "Save user and access" }}
					</button>
				</div>
			</form>

			<aside class="form-rail min-w-0 space-y-4" aria-label="User summary">
				<div class="kit-panel record-card">
					<div class="record-card__head">
						<Avatar :name="previewName || 'New user'" size="lg" />
						<div class="min-w-0 flex-1">
							<h2 class="break-words font-display text-base font-semibold text-ink">
								{{ form.name ? form.full_name : "Add user" }}
							</h2>
							<p class="break-all text-xs text-muted">
								{{
									form.name ||
									"Create a login identity. HR links it to an Employee separately."
								}}
							</p>
						</div>
					</div>
					<dl class="summary-list">
						<div><dt>Login</dt><dd><span :class="pillClass(form.enabled ? 'ok' : 'muted')">{{ form.enabled ? "Enabled" : "Disabled" }}</span></dd></div>
						<div><dt>User type</dt><dd>{{ form.user_type || "—" }}</dd></div>
						<div><dt>{{ form.role_mode === "profiles" ? "Role profiles" : "Direct roles" }}</dt><dd>{{ accessCount }}</dd></div>
					</dl>
					<ul v-if="selectedAccess.length" class="mt-3 flex flex-wrap gap-1.5" aria-label="Selected access">
						<li v-for="item in selectedAccess.slice(0, 12)" :key="item" class="pill pill--info">{{ item }}</li>
						<li v-if="selectedAccess.length > 12" class="pill pill--muted">+{{ selectedAccess.length - 12 }} more</li>
					</ul>
					<div v-if="form.name" class="mt-4 border-t border-line pt-4">
						<button
							type="button"
							class="btn-secondary w-full justify-center"
							:disabled="!form.enabled || resetting || saving"
							@click="resetPassword"
						>
							{{ resetting ? "Sending…" : "Reset password" }}
						</button>
						<p v-if="!form.enabled" class="form-hint mb-0 mt-2">
							Enable and save this account before sending a password reset link.
						</p>
					</div>
				</div>
				<p class="rounded-2xl bg-warn-soft p-4 text-sm text-ink">
					Role changes take effect immediately. Disable accounts instead of deleting them
					so historical approvals and transactions remain attributable.
				</p>
			</aside>
		</div>

		<div v-if="!loading && !editing" class="list-board">
			<aside class="min-w-0 space-y-4">
				<div class="filter-rail kit-panel" role="group" aria-label="Filter users by access">
					<button
						v-for="option in ['All', 'Enabled', 'Disabled']"
						:key="option"
						type="button"
						class="filter-btn"
						:class="{ 'filter-btn--active': enabledFilter === option }"
						:aria-pressed="enabledFilter === option"
						@click="enabledFilter = option"
					>
						<span class="filter-btn__dot" :class="dotClass(option === 'Enabled' ? 'ok' : option === 'Disabled' ? 'muted' : 'info')"></span>
						<span class="min-w-0 flex-1 truncate text-left">{{ option }}</span>
						<span class="filter-btn__count">{{ accessCounts[option] }}</span>
					</button>
				</div>
			</aside>
			<section class="min-w-0 space-y-3" aria-label="Users">
				<div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem]">
					<label class="field-label relative block"
						><span class="sr-only">Find a user</span
						><Icon name="search" size="sm" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" /><input
							v-model.trim="search"
							class="field-input !mt-0 pl-9"
							aria-label="Find a user"
							placeholder="Name, email or linked employee"
					/></label>
					<label class="field-label"
						><span class="sr-only">User type</span
						><select v-model="typeFilter" class="field-input !mt-0" aria-label="User type">
							<option value="All">All user types</option>
							<option v-for="value in workspace.user_types" :key="value" :value="value">
								{{ value }}
							</option>
						</select></label
					>
				</div>
				<p class="text-sm text-muted">{{ filteredUsers.length }} users</p>
				<div v-if="!filteredUsers.length" class="kit-panel px-6 py-12 text-center text-muted">
					No matching users.
				</div>
				<div v-else class="kit-panel overflow-hidden">
					<button
						v-for="user in filteredUsers"
						:key="user.name"
						type="button"
						class="directory-card dir-row"
						@click="edit(user.name)"
					>
						<Avatar :name="user.full_name || user.name" />
						<span class="min-w-0">
							<strong class="block truncate text-sm text-ink">{{ user.full_name || user.name }}</strong>
							<span class="block truncate text-xs text-muted">{{ user.name }}</span>
						</span>
						<span class="dir-row__meta truncate"
							>{{ user.user_type
							}}<template v-if="user.employee">
								· {{ user.employee.employee_name }} ({{
									user.employee.status
								}})</template
							></span
						>
						<span :class="pillClass(user.enabled ? 'ok' : 'muted')">{{
							user.enabled ? "Enabled" : "Disabled"
						}}</span>
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
const accessCounts = computed(() => {
	const enabled = workspace.users.filter((user) => user.enabled).length;
	return { All: workspace.users.length, Enabled: enabled, Disabled: workspace.users.length - enabled };
});
const previewName = computed(
	() =>
		[form.first_name, form.middle_name, form.last_name].filter(Boolean).join(" ") ||
		form.full_name ||
		form.email,
);
const selectedAccess = computed(() =>
	form.role_mode === "profiles" ? form.role_profiles : form.roles,
);
const accessCount = computed(() => selectedAccess.value.length);
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
	if (saving.value || resetting.value) return;
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
	if (!form.name || !form.enabled || resetting.value || saving.value) return;
	if (!window.confirm(`Send a password reset link to ${form.name}?`)) return;
	const name = form.name;
	const modified = form.modified;
	resetting.value = true;
	error.value = "";
	success.value = "";
	try {
		const result = await call(`${API}send_managed_user_password_reset`, {
			name,
			expected_modified: modified,
		});
		// Reset changes only the server-side password fields. Keep pending form
		// edits; never replace them or advance a different/reopened editor.
		if (form.name === name && form.modified === modified) {
			form.modified = result.modified;
			success.value = `A password reset link was sent to ${name}.`;
		}
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		resetting.value = false;
	}
}
onMounted(load);
</script>

<style scoped>
.option-grid {
	@apply grid max-h-80 gap-2 overflow-y-auto sm:grid-cols-2;
}
</style>
