<template>
	<div class="min-h-screen bg-bg text-ink pb-24 md:pb-8">
	<header class="app-header sticky top-0 left-0 right-0 z-20 w-full border-b border-line">
			<div class="max-w-5xl mx-auto px-4 md:px-6 py-3 flex items-center w-full gap-3">
				<AppNav class="max-md:hidden md:flex shrink-0" :items="navItems" aria-label="Sections" />
				<div class="md:hidden font-semibold tracking-tight">Sevamrita</div>
				<div class="ml-auto flex items-center gap-0.5 shrink-0">
					<button
						type="button"
						class="btn-ghost"
						:title="dark ? 'Switch to light mode' : 'Switch to dark mode'"
						:aria-pressed="dark"
						aria-label="Toggle colour theme"
						@click="onThemeClick"
					>
						<Icon :name="dark ? 'sun' : 'moon'" />
					</button>
					<NotifyMenu />
					<a href="/desk" class="btn-ghost" title="Open Desk" aria-label="Open Desk">
						<Icon name="desk" />
					</a>
					<a href="/help" class="btn-ghost" aria-label="Help">
						<Icon name="help" />
					</a>
				</div>
			</div>
		</header>
		<main class="max-w-5xl mx-auto p-4 md:p-6">
			<RouterView />
		</main>
		<div
			class="app-header md:hidden fixed bottom-0 inset-x-0 z-20 w-full border-t border-line pb-[env(safe-area-inset-bottom)]"
		>
			<div class="max-w-5xl mx-auto px-4">
				<AppNav layout="bottom" :items="navItems" aria-label="Mobile" />
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { RouterView } from "vue-router";
import { homePayload, loadHomePayload, startHomePoll, stopHomePoll } from "./lib/home";
import { isDark, toggleTheme } from "./lib/theme";
import AppNav from "./components/AppNav.vue";
import Icon from "./components/Icon.vue";
import NotifyMenu from "./components/NotifyMenu.vue";

const dark = ref(false);

const nav = computed(() => ({
	advances: homePayload.value?.nav?.advances ?? true,
	budget_health: homePayload.value?.nav?.budget_health ?? false,
}));

const todoCount = computed(
	() => homePayload.value?.waiting_count ?? homePayload.value?.todo_count ?? 0
);

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
