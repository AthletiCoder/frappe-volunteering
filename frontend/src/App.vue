<template>
	<div class="min-h-screen bg-bg pb-20 text-ink lg:pl-60 lg:pb-0">
		<PortalSidebar :items="sidebarItems" :full-name="fullName" :initials="initials" :role-label="roleLabel" :open="drawerOpen" @close="drawerOpen = false" />
		<header class="app-header sticky top-0 z-20 w-full border-b border-line">
			<div class="mx-auto flex h-16 max-w-[1480px] items-center gap-3 px-4 md:px-6 lg:px-8">
				<button type="button" class="btn-ghost lg:hidden" aria-label="Open menu" @click="drawerOpen = true"><Icon name="menu" /></button>
				<RouterLink to="/home" class="text-sm font-bold lg:hidden">Sevamrita</RouterLink>
				<button type="button" class="portal-search-trigger mx-auto hidden w-full max-w-md items-center gap-3 rounded-xl border border-line bg-bg px-3 py-2 text-sm text-muted hover:border-accent hover:text-ink sm:flex" @click="openSearch">
					<Icon name="search" size="sm" /><span class="flex-1 text-left">Search pages and actions</span><kbd class="rounded-md border border-line bg-surface px-1.5 py-0.5 text-[10px]">⌘ K</kbd>
				</button>
				<div class="ml-auto flex items-center gap-1 sm:ml-0">
					<button type="button" class="btn-ghost sm:hidden" aria-label="Search" @click="openSearch"><Icon name="search" /></button>
					<NotifyMenu />
					<a href="/desk" class="btn-ghost" title="Open Desk" aria-label="Open Desk"><Icon name="desk" /></a>
					<a href="/help" class="btn-ghost" aria-label="Help"><Icon name="help" /></a>
					<RouterLink to="/profile" class="portal-profile-trigger ml-1 hidden items-center gap-2 rounded-xl p-1.5 hover:bg-soft md:flex" aria-label="Account profile">
						<span class="flex h-8 w-8 items-center justify-center rounded-full bg-accent-soft text-xs font-bold text-accent">{{ initials }}</span>
						<span class="portal-profile-details hidden text-left xl:block"><span class="block text-xs font-semibold leading-tight">{{ fullName }}</span><span class="block text-[11px] text-muted">{{ roleLabel }}</span></span>
					</RouterLink>
				</div>
			</div>
		</header>
		<main class="mx-auto w-full max-w-[1480px] p-4 md:p-6 lg:p-8"><RouterView /></main>
		<div class="app-header fixed inset-x-0 bottom-0 z-20 w-full border-t border-line pb-[env(safe-area-inset-bottom)] lg:hidden">
			<div class="mx-auto flex max-w-lg items-center px-2">
				<AppNav layout="bottom" :items="mobileItems" aria-label="Mobile" />
				<button type="button" class="flex min-w-[3.5rem] flex-col items-center gap-1 rounded-xl px-2 py-2 text-[11px] text-muted" aria-label="More sections" @click="drawerOpen = true"><Icon name="menu" /><span>More</span></button>
			</div>
		</div>
		<div v-if="searchOpen" class="fixed inset-0 z-50 flex items-start justify-center bg-ink/40 px-4 pt-[10vh]" @click.self="searchOpen = false">
			<div class="w-full max-w-xl overflow-hidden rounded-2xl border border-line bg-surface shadow-lift" role="dialog" aria-modal="true" aria-label="Search pages and actions">
				<div class="flex items-center gap-3 border-b border-line px-4 py-3"><Icon name="search" class="text-muted" /><input ref="searchInput" v-model="searchQuery" type="search" class="min-w-0 flex-1 bg-transparent text-base text-ink outline-none" placeholder="Search your pages and actions" aria-label="Search your pages and actions" /><button type="button" class="text-xs text-muted" @click="searchOpen = false">Esc</button></div>
				<div class="max-h-[55vh] overflow-y-auto p-2">
					<a v-for="item in searchResults" :key="item.route" :href="item.route" class="flex items-center gap-3 rounded-xl px-3 py-2.5 hover:bg-accent-soft"><Icon :name="item.icon" size="sm" class="text-accent" /><span class="min-w-0"><span class="block text-sm font-medium">{{ item.label }}</span><span v-if="item.hint" class="block truncate text-xs text-muted">{{ item.hint }}</span></span></a>
					<p v-if="!searchResults.length" class="px-3 py-8 text-center text-sm text-muted">No matching pages or actions.</p>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { homePayload, loadHomePayload, startHomePoll, stopHomePoll } from "./lib/home";
import AppNav from "./components/AppNav.vue";
import Icon from "./components/Icon.vue";
import NotifyMenu from "./components/NotifyMenu.vue";
import PortalSidebar from "./components/PortalSidebar.vue";

const route = useRoute();
const drawerOpen = ref(false);
const searchOpen = ref(false);
const searchQuery = ref("");
const searchInput = ref(null);
const payload = computed(() => homePayload.value);
const actions = computed(() => payload.value?.actions || {});
const todoCount = computed(() => payload.value?.waiting_count ?? payload.value?.todo_count ?? 0);
const fullName = computed(() => payload.value?.full_name || "My account");
const initials = computed(() => fullName.value.split(/\s+/).slice(0, 2).map((part) => part[0] || "").join("").toUpperCase());
const roleLabel = computed(() => {
	if (actions.value.system_management?.length) return "System management";
	if (actions.value.hr_management?.length) return "HR management";
	if (actions.value.accounts?.some((row) => row.id === "chart_of_accounts")) return "Accounts manager";
	if (actions.value.accounts?.length) return "Accounts team";
	if (actions.value.projects?.some((row) => row.id === "review_project_proposals")) return "Projects manager";
	if (actions.value.team?.length) return "Team lead";
	return "Employee";
});

const sidebarItems = computed(() => {
	const nav = payload.value?.nav || {};
	const items = [{ to: "/home", label: "Home", icon: "home" }, { to: "/todos", label: "My Work", icon: "check", badge: todoCount.value }, { section: "Work" }];
	if (nav.projects) items.push({ to: "/projects", label: "Projects", icon: "folder" });
	if (payload.value?.flags?.show_time) items.push({ href: "/volunteering/home#time", label: "Time & leave", icon: "clock" });
	if (payload.value?.flags?.show_money) items.push({ to: "/expense-claims", label: "Expenses", icon: "receipt" });
	if (nav.advances) items.push({ to: "/advances", label: "Advances", icon: "wallet" });
	if (nav.team) items.push({ to: "/team", label: "My team", icon: "people" });
	if (nav.volunteering) items.push({ href: "/desk/volunteering", label: "Volunteering", icon: "people" });
	const management = [];
	if (actions.value.projects?.some((row) => row.id === "review_project_proposals")) management.push({ to: "/project-proposals/review", label: "Project reviews", icon: "clipboard-check" });
	if (actions.value.accounts?.length) management.push({ href: "/volunteering/home#accounts", label: "Accounts work", icon: "bank" });
	if (nav.budget_health) management.push({ to: "/budget-health", label: "Budgets", icon: "chart" });
	if (actions.value.hr_management?.length) management.push({ to: "/hr-management", label: "HR management", icon: "user-plus" });
	if (actions.value.system_management?.length) management.push({ to: "/system-management", label: "System management", icon: "user-shield" });
	if (management.length) items.push({ section: "Management" }, ...management);
	if (payload.value?.allowed) items.push({ section: "Organisation" }, { to: "/office-addresses", label: "Office addresses", icon: "map-pin" });
	return items;
});
const mobileItems = computed(() => {
	const items = [{ to: "/home", label: "Home", icon: "home" }, { to: "/todos", label: "My Work", icon: "check", badge: todoCount.value }];
	if (payload.value?.nav?.projects) items.push({ to: "/projects", label: "Projects", icon: "folder" });
	if (payload.value?.nav?.advances) items.push({ to: "/advances", label: "Advances", icon: "wallet" });
	return items;
});
const searchCatalog = computed(() => {
	const entries = sidebarItems.value.filter((item) => item.to || item.href).map((item) => ({ label: item.label, route: item.href || `/volunteering${item.to}`, icon: item.icon }));
	for (const group of Object.values(actions.value)) for (const action of group || []) {
		if (action.route) entries.push({ label: action.label, route: action.route, icon: "arrow-right", hint: action.hint });
		if (action.list_route) entries.push({ label: action.list_label, route: action.list_route, icon: "document-history" });
	}
	return [...new Map(entries.map((item) => [item.route, item])).values()];
});
const searchResults = computed(() => {
	const query = searchQuery.value.trim().toLowerCase();
	return searchCatalog.value.filter((item) => !query || `${item.label} ${item.hint || ""}`.toLowerCase().includes(query)).slice(0, 8);
});
async function openSearch() {
	searchQuery.value = "";
	searchOpen.value = true;
	await nextTick();
	searchInput.value?.focus();
}
function onKeydown(event) {
	if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); openSearch(); }
	else if (event.key === "Escape") { searchOpen.value = false; drawerOpen.value = false; }
}
watch(() => route.fullPath, () => { drawerOpen.value = false; searchOpen.value = false; });
onMounted(() => {
	if (!homePayload.value) loadHomePayload().catch(() => {});
	startHomePoll();
	window.addEventListener("keydown", onKeydown);
});
onUnmounted(() => { stopHomePoll(); window.removeEventListener("keydown", onKeydown); });
</script>
