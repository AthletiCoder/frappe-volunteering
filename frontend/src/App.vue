<template>
	<div class="min-h-screen bg-bg text-ink lg:pl-[17rem] lg:pb-0" :class="route.path === '/work-logs' ? 'pb-0' : 'pb-24'">
		<PortalSidebar :items="sidebarItems" :full-name="fullName" :initials="initials" :role-label="roleLabel" :open="drawerOpen" :logging-out="loggingOut" @close="drawerOpen = false" @logout="logout" />
		<header class="app-header sticky top-0 z-20 w-full border-b border-line/80">
			<div class="mx-auto flex h-16 max-w-[1440px] items-center gap-2 px-3 sm:gap-3 sm:px-5 lg:px-8">
				<button type="button" class="btn-ghost -ml-1 lg:hidden" aria-label="Open menu" @click="drawerOpen = true"><Icon name="menu" /></button>
				<RouterLink to="/home" class="portal-mobile-brand flex items-center gap-2 rounded-lg" aria-label="Sevamrita">
					<img :src="'/assets/volunteering/brand/lotus-mark.png'" alt="" class="h-7 w-auto" width="33" height="28" />
					<span class="font-display text-[15px] font-semibold tracking-[0.06em] text-navy-900">SEVAMRITA</span>
				</RouterLink>
				<button type="button" class="portal-search-trigger group hidden w-full max-w-md items-center gap-3 rounded-xl border border-line bg-surface/70 px-3.5 py-2 text-sm text-muted shadow-soft transition-colors duration-150 hover:border-navy-200 hover:bg-surface hover:text-ink sm:ml-auto lg:ml-0" @click="openSearch">
					<Icon name="search" size="sm" /><span class="flex-1 text-left">Search pages and actions</span><kbd class="rounded-md border border-line bg-soft px-1.5 py-0.5 font-sans text-[11px] text-muted">⌘ K</kbd>
				</button>
				<div class="ml-auto flex items-center gap-0.5 sm:gap-1">
					<button type="button" class="btn-ghost sm:hidden" aria-label="Search" @click="openSearch"><Icon name="search" /></button>
					<NotifyMenu />
					<a href="/help" class="btn-ghost" aria-label="Help"><Icon name="help" /></a>
					<span class="mx-2 hidden h-6 w-px bg-line md:block" aria-hidden="true"></span>
					<RouterLink to="/profile" class="portal-profile-trigger hidden items-center gap-2.5 rounded-xl py-1 pl-1 pr-2 transition-colors duration-150 hover:bg-soft">
						<span class="flex h-8 w-8 items-center justify-center rounded-full bg-navy-900 text-[11px] font-semibold tracking-wide text-white">{{ initials }}</span>
						<span class="portal-profile-details hidden text-left"><span class="block text-[13px] font-semibold leading-tight text-ink">{{ fullName }}</span><span class="block text-xs leading-tight text-muted">{{ roleLabel }}</span></span>
					</RouterLink>
					<button type="button" class="portal-header-logout hidden items-center gap-1.5 rounded-xl px-2.5 py-2 text-[13px] font-medium text-muted transition-colors duration-150 hover:bg-soft hover:text-ink disabled:opacity-60" :disabled="loggingOut" @click="logout"><Icon name="logout" size="sm" />{{ loggingOut ? "Logging out…" : "Logout" }}</button>
				</div>
			</div>
		</header>
		<main class="mx-auto w-full max-w-[1440px] px-4 pb-6 pt-5 sm:px-5 md:pt-7 lg:px-8 lg:pb-10">
			<p v-if="logoutError" class="message-error mb-4" role="alert">{{ logoutError }}</p>
			<div ref="pageEl" class="page-enter"><RouterView /></div>
		</main>
		<div v-if="route.path !== '/work-logs'" class="app-header fixed inset-x-0 bottom-0 z-20 w-full border-t border-line pb-[env(safe-area-inset-bottom)] lg:hidden">
			<div class="mx-auto flex max-w-lg items-stretch px-1.5 pt-1">
				<AppNav class="min-w-0 flex-1" layout="bottom" :items="mobileItems" aria-label="Mobile" />
				<button type="button" class="flex w-[4.25rem] shrink-0 flex-col items-center gap-0.5 rounded-xl px-1 pb-1.5 pt-1 text-[11px] font-medium text-muted transition-colors hover:text-ink" aria-label="More sections" @click="drawerOpen = true"><span class="flex h-8 w-10 items-center justify-center rounded-full"><Icon name="menu" /></span><span>More</span></button>
			</div>
		</div>
		<div v-if="searchOpen" class="app-scrim anim-fade fixed inset-0 z-50 flex items-start justify-center px-4 pt-[12vh]" @click.self="searchOpen = false">
			<div class="anim-dialog w-full max-w-xl overflow-hidden rounded-2xl border border-line bg-surface shadow-pop" role="dialog" aria-modal="true" aria-label="Search pages and actions">
				<div class="flex items-center gap-3 border-b border-line px-4 py-3.5"><Icon name="search" class="text-muted" /><input ref="searchInput" v-model="searchQuery" type="search" class="search-input min-w-0 flex-1 border-0 bg-transparent p-0 text-base text-ink shadow-none outline-none" placeholder="Search your pages and actions" aria-label="Search your pages and actions" @keydown.down.prevent="moveActive(1)" @keydown.up.prevent="moveActive(-1)" @keydown.enter="openActive" /><button type="button" class="rounded-md border border-line px-1.5 py-0.5 text-[11px] text-muted hover:text-ink" @click="searchOpen = false">Esc</button></div>
				<div class="max-h-[55vh] overflow-y-auto p-2">
					<p v-if="searchResults.length" class="eyebrow px-3 pb-1 pt-2">{{ searchQuery.trim() ? "Matches" : "Jump to" }}</p>
					<a v-for="(item, index) in searchResults" :key="item.route" :href="item.route" class="flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors duration-100" :class="index === activeIndex ? 'bg-navy-50' : 'hover:bg-soft'" @mouseenter="activeIndex = index"><span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-soft text-navy-900"><Icon :name="item.icon" size="sm" /></span><span class="min-w-0"><span class="block text-sm font-medium text-ink">{{ item.label }}</span><span v-if="item.hint" class="block truncate text-xs text-muted">{{ item.hint }}</span></span></a>
					<p v-if="!searchResults.length" class="px-3 py-10 text-center text-sm text-muted">No matching pages or actions.</p>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { homePayload, loadHomePayload, startHomePoll, stopHomePoll } from "./lib/home";
import { buildSidebarItems } from "./lib/workspaceNavigation";
import { call } from "./lib/frappe";
import AppNav from "./components/AppNav.vue";
import Icon from "./components/Icon.vue";
import NotifyMenu from "./components/NotifyMenu.vue";
import PortalSidebar from "./components/PortalSidebar.vue";

const route = useRoute();
const drawerOpen = ref(false);
const searchOpen = ref(false);
const searchQuery = ref("");
const searchInput = ref(null);
const activeIndex = ref(0);
const pageEl = ref(null);
const loggingOut = ref(false);
const logoutError = ref("");
const payload = computed(() => homePayload.value);
const actions = computed(() => payload.value?.actions || {});
const todoCount = computed(() => payload.value?.waiting_count ?? payload.value?.todo_count ?? 0);
const fullName = computed(() => payload.value?.full_name || "My account");
const initials = computed(() => fullName.value.split(/\s+/).slice(0, 2).map((part) => part[0] || "").join("").toUpperCase());
const roleLabel = computed(() => {
	if (actions.value.system_management?.length) return "System management";
	if (actions.value.hr_management?.length) return "HR management";
	if (actions.value.accounts?.some((row) => row.id === "expense_approval_limits")) return "Accounts manager";
	if (actions.value.accounts?.length) return "Accounts team";
	if (actions.value.projects?.some((row) => row.id === "review_project_proposals")) return "Projects manager";
	if (actions.value.team?.length) return "Team lead";
	return "Employee";
});
const sidebarItems = computed(() => buildSidebarItems(payload.value));
const mobileItems = computed(() => {
	const items = [{ to: "/home", label: "Home", icon: "home" }, { to: "/todos", label: "My Work", icon: "check", badge: todoCount.value }];
	if (payload.value?.nav?.projects) items.push({ to: "/projects", label: "Projects", icon: "folder" });
	if (payload.value?.nav?.advances) items.push({ to: "/advances", label: "Advances", icon: "wallet" });
	return items;
});
const searchCatalog = computed(() => {
	const entries = sidebarItems.value.flatMap((item) => item.children || (item.to || item.href ? [item] : []))
		.map((item) => ({ label: item.label, route: item.href || `/volunteering${item.to}`, icon: item.icon || "document-history" }));
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
watch(searchQuery, () => { activeIndex.value = 0; });
function moveActive(step) {
	const count = searchResults.value.length;
	if (count) activeIndex.value = (activeIndex.value + step + count) % count;
}
function openActive() {
	const item = searchResults.value[activeIndex.value];
	if (item) window.location.assign(item.route);
}
async function openSearch() {
	searchQuery.value = "";
	activeIndex.value = 0;
	searchOpen.value = true;
	await nextTick();
	searchInput.value?.focus();
}
async function logout() {
	if (loggingOut.value) return;
	loggingOut.value = true;
	logoutError.value = "";
	try {
		await call("logout");
		stopHomePoll();
		homePayload.value = null;
		window.location.replace("/login?redirect-to=%2Fvolunteering%2Fhome");
	} catch (err) {
		logoutError.value = err.message || "Unable to log out. Please try again.";
		loggingOut.value = false;
	}
}
function onKeydown(event) {
	if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); openSearch(); }
	else if (event.key === "Escape") { searchOpen.value = false; drawerOpen.value = false; }
}
// Replay a short entrance on each page change without remounting the view,
// so views that share a component across routes keep their state.
watch(() => route.path, () => {
	const el = pageEl.value;
	if (!el) return;
	el.classList.remove("page-enter");
	void el.offsetWidth;
	el.classList.add("page-enter");
});
watch(() => route.fullPath, () => { drawerOpen.value = false; searchOpen.value = false; });
onMounted(() => {
	if (!homePayload.value) loadHomePayload().catch(() => {});
	startHomePoll();
	window.addEventListener("keydown", onKeydown);
});
onUnmounted(() => { stopHomePoll(); window.removeEventListener("keydown", onKeydown); });
</script>

<style scoped>
.search-input:focus,
.search-input:hover {
	box-shadow: none;
	border: 0;
}
</style>
