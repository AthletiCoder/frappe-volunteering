<template>
	<div class="relative" data-notify-menu>
		<button
			type="button"
			class="btn-ghost"
			:title="title"
			:aria-expanded="open"
			aria-haspopup="true"
			aria-label="Notifications"
			@click.stop="toggle"
		>
			<Icon name="bell" />
		</button>
		<div
			v-if="open"
			class="absolute right-0 mt-2 w-72 rounded-2xl border border-line bg-surface shadow-lift p-3 z-30"
			role="dialog"
			aria-label="Notification settings"
			@click.stop
		>
			<p class="text-sm font-semibold text-ink mb-2">Notifications</p>
			<p class="text-xs text-muted mb-3">{{ browserHint }}</p>

			<button
				v-if="permission === 'default'"
				type="button"
				class="btn-secondary text-sm w-full mb-3"
				@click="enableBrowser"
			>
				Allow browser alerts
			</button>

			<label
				v-if="orgEnabled"
				class="flex items-start gap-2.5 text-sm text-ink cursor-pointer select-none"
			>
				<input
					type="checkbox"
					class="mt-0.5 h-4 w-4 shrink-0"
					:checked="workLogOptIn"
					:disabled="saving"
					@change="onOptInChange"
				/>
				<span class="min-w-0 flex-1">
					<span class="font-medium">Morning work log reminder</span>
					<span class="block text-xs text-muted mt-0.5">
						Email if yesterday’s hours are missing (around {{ reminderHour }}:00). Off when
						you’ve already logged, or on leave/holiday.
					</span>
				</span>
			</label>
			<p v-else class="text-xs text-muted">
				Morning work log emails are turned off for the organisation.
			</p>

			<p v-if="error" class="text-xs text-bad mt-2">{{ error }}</p>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import Icon from "./Icon.vue";
import {
	loadNotificationPreferences,
	notifyPermission,
	requestNotifyPermission,
	setWorkLogReminderOptIn,
} from "../lib/notify";

const open = ref(false);
const permission = ref(notifyPermission());
const workLogOptIn = ref(true);
const orgEnabled = ref(true);
const reminderHour = ref(9);
const saving = ref(false);
const error = ref("");

const title = computed(() => {
	if (permission.value === "denied") return "Browser notifications blocked";
	return "Notification settings";
});

const browserHint = computed(() => {
	if (permission.value === "granted") return "Browser alerts are on while Home is open.";
	if (permission.value === "denied") {
		return "Browser blocked alerts — you can still use email reminders.";
	}
	if (permission.value === "insecure") {
		return "Browser alerts need HTTPS (or localhost). On http://sevamrita.local use email reminders below.";
	}
	if (permission.value === "unsupported") return "This browser does not support alerts.";
	return "Optional: allow alerts for new actions while you are on Home.";
});

async function refreshPrefs() {
	try {
		const prefs = await loadNotificationPreferences();
		workLogOptIn.value = !!prefs.work_log_reminder_opt_in;
		orgEnabled.value = !!prefs.org_enabled;
		reminderHour.value = prefs.reminder_hour ?? 9;
		error.value = "";
	} catch (e) {
		error.value = e.message || String(e);
	}
}

async function toggle() {
	open.value = !open.value;
	if (open.value) {
		permission.value = notifyPermission();
		await refreshPrefs();
	}
}

async function enableBrowser() {
	permission.value = await requestNotifyPermission();
}

async function onOptInChange(event) {
	const next = !!event.target.checked;
	saving.value = true;
	error.value = "";
	try {
		const prefs = await setWorkLogReminderOptIn(next);
		workLogOptIn.value = !!prefs.work_log_reminder_opt_in;
	} catch (e) {
		error.value = e.message || String(e);
		event.target.checked = workLogOptIn.value;
	} finally {
		saving.value = false;
	}
}

function onWindowClick(event) {
	if (!open.value) return;
	const el = event.target;
	if (el instanceof Element && el.closest("[data-notify-menu]")) return;
	open.value = false;
}

onMounted(() => {
	window.addEventListener("click", onWindowClick);
});

onUnmounted(() => {
	window.removeEventListener("click", onWindowClick);
});
</script>
