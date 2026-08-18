<template>
	<div class="min-h-screen bg-bg text-ink pb-24 md:pb-8">
		<header class="app-header sticky top-0 left-0 right-0 z-20 w-full border-b border-line px-6 md:px-10 py-3 flex gap-6 items-center">
			<AppNav class="max-md:hidden md:flex" :items="navItems" aria-label="Sections" />
			<div class="md:hidden font-semibold tracking-tight">Sevamrita</div>
			<div class="ml-auto flex items-center gap-1">
				<button
					type="button"
					class="p-2 rounded-xl text-muted hover:text-ink"
					:title="dark ? 'Switch to light mode' : 'Switch to dark mode'"
					:aria-pressed="dark"
					aria-label="Toggle colour theme"
					@click="onThemeClick"
				>
					<Icon :name="dark ? 'sun' : 'moon'" />
				</button>
				<button
					type="button"
					class="p-2 rounded-xl text-muted hover:text-ink"
					:title="notifyTitle"
					@click="onNotifyClick"
				>
					<Icon name="bell" />
				</button>
				<a href="/help" class="p-2 rounded-xl text-muted hover:text-ink" aria-label="Help">
					<Icon name="help" />
				</a>
			</div>
		</header>
		<main class="max-w-5xl mx-auto p-4 md:p-6">
			<RouterView />
		</main>
		<div
			class="app-header md:hidden fixed bottom-0 inset-x-0 z-20 w-full border-t border-line px-6 pb-[env(safe-area-inset-bottom)]"
		>
			<AppNav layout="bottom" :items="navItems" aria-label="Mobile" />
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { RouterView } from "vue-router";
import { homePayload, loadHomePayload, startHomePoll, stopHomePoll } from "./lib/home";
import { notifyPermission, requestNotifyPermission } from "./lib/notify";
import { isDark, toggleTheme } from "./lib/theme";
import AppNav from "./components/AppNav.vue";
import Icon from "./components/Icon.vue";

const permission = ref(notifyPermission());
const dark = ref(false);

const nav = computed(() => ({
	advances: homePayload.value?.nav?.advances ?? true,
	budget_health: homePayload.value?.nav?.budget_health ?? false,
}));

const todoCount = computed(() => homePayload.value?.todo_count || 0);

const navItems = computed(() => {
	const items = [{ to: "/home", label: "Home", icon: "home", badge: todoCount.value }];
	if (nav.value.advances) {
		items.push({ to: "/advances", label: "Advances", icon: "wallet" });
	}
	if (nav.value.budget_health) {
		items.push({ to: "/budget-health", label: "Budgets", icon: "chart" });
	}
	return items;
});

const notifyTitle = computed(() => {
	if (permission.value === "granted") return "Notifications on";
	if (permission.value === "denied") return "Notifications blocked in the browser";
	return "Turn on notifications";
});

async function onNotifyClick() {
	permission.value = await requestNotifyPermission();
}

function onThemeClick() {
	dark.value = toggleTheme();
}

onMounted(() => {
	dark.value = isDark();
	if (!homePayload.value) {
		loadHomePayload().catch(() => {});
	}
	startHomePoll();
});

onUnmounted(stopHomePoll);
</script>
