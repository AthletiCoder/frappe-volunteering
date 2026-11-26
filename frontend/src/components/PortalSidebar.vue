<template>
	<aside class="portal-sidebar fixed inset-y-0 left-0 z-30 hidden w-[17rem] flex-col border-r border-line bg-surface lg:flex">
		<RouterLink to="/home" class="flex h-16 shrink-0 items-center px-5" aria-label="Sevamrita Home">
			<img :src="'/assets/volunteering/brand/logo-horizontal.png'" alt="" class="h-9 w-auto" width="155" height="36" />
		</RouterLink>
		<div v-if="canCreate" class="px-3 pb-2">
			<button type="button" class="sidebar-new group" @click="$emit('new')">
				<Icon name="plus" size="sm" /><span class="flex-1 text-left">New</span><span class="sidebar-new__kbd" aria-hidden="true">N</span>
			</button>
		</div>
		<div class="sidebar-scroll min-h-0 flex-1 overflow-y-auto px-3 pb-4 pt-1"><AppNav layout="sidebar" :items="items" aria-label="Sections" /></div>
		<div class="border-t border-line p-3">
			<RouterLink to="/profile" class="flex items-center gap-3 rounded-xl p-2 transition-colors duration-150 hover:bg-soft">
				<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-navy-900 text-xs font-semibold tracking-wide text-white">{{ initials }}</span>
				<span class="min-w-0"><span class="block truncate text-sm font-semibold text-ink">{{ fullName }}</span><span class="block truncate text-xs text-muted">{{ roleLabel }}</span></span>
			</RouterLink>
		</div>
	</aside>
	<template v-if="open">
		<div class="app-scrim anim-fade fixed inset-0 z-40 lg:hidden" @click="$emit('close')"></div>
		<aside class="anim-drawer fixed inset-y-0 left-0 z-50 flex w-[min(20rem,86vw)] flex-col bg-surface shadow-pop lg:hidden" aria-label="Mobile menu">
			<div class="flex h-16 shrink-0 items-center justify-between border-b border-line pl-5 pr-3">
				<img :src="'/assets/volunteering/brand/logo-horizontal.png'" alt="Sevamrita Foundation" class="h-8 w-auto" width="138" height="32" />
				<button type="button" class="btn-ghost" aria-label="Close menu" @click="$emit('close')"><Icon name="close" /></button>
			</div>
			<div class="min-h-0 flex-1 overflow-y-auto px-3 py-3"><AppNav layout="sidebar" :items="items" aria-label="Mobile sections" @navigate="$emit('close')" /></div>
			<div class="flex items-center gap-2 border-t border-line p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
				<RouterLink to="/profile" class="flex min-w-0 flex-1 items-center gap-3 rounded-xl p-2 hover:bg-soft" @click="$emit('close')">
					<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-navy-900 text-xs font-semibold text-white">{{ initials }}</span>
					<span class="min-w-0"><span class="block truncate text-sm font-semibold text-ink">{{ fullName }}</span><span class="block truncate text-xs text-muted">{{ roleLabel }}</span></span>
				</RouterLink>
				<button type="button" class="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-line px-3 py-2 text-[13px] font-medium text-ink hover:bg-soft disabled:opacity-60" :disabled="loggingOut" @click="$emit('logout')"><Icon name="logout" size="sm" />{{ loggingOut ? "Logging out…" : "Logout" }}</button>
			</div>
		</aside>
	</template>
</template>

<script setup>
import { RouterLink } from "vue-router";
import AppNav from "./AppNav.vue";
import Icon from "./Icon.vue";

defineProps({
	items: { type: Array, default: () => [] },
	fullName: { type: String, default: "My account" },
	initials: { type: String, default: "" },
	roleLabel: { type: String, default: "Employee" },
	open: { type: Boolean, default: false },
	loggingOut: { type: Boolean, default: false },
	canCreate: { type: Boolean, default: false },
});
defineEmits(["close", "logout", "new"]);
</script>

<style scoped>
.sidebar-new {
	display: flex;
	width: 100%;
	align-items: center;
	gap: 0.625rem;
	border-radius: 12px;
	background: var(--navy-900);
	padding: 0.625rem 0.875rem;
	font-size: 0.875rem;
	font-weight: 600;
	color: #fff;
	box-shadow: 0 8px 18px -10px rgb(5 34 77 / 0.6);
	transition: background-color var(--dur-fast) ease, transform var(--dur) var(--ease-out);
}
.sidebar-new:hover { background: var(--navy-800); }
.sidebar-new:active { transform: scale(0.98); }
.sidebar-new:focus-visible { outline: 2px solid var(--navy-900); outline-offset: 2px; }
.sidebar-new__kbd { border-radius: 6px; border: 1px solid rgb(255 255 255 / 0.25); padding: 0 0.375rem; font-family: inherit; font-size: 0.6875rem; color: rgb(255 255 255 / 0.75); }
</style>
