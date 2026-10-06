<template>
	<aside class="portal-sidebar hidden lg:flex fixed inset-y-0 left-0 z-30 w-60 flex-col border-r border-line bg-surface">
		<RouterLink to="/home" class="flex items-center gap-3 border-b border-line px-5 py-4" aria-label="Sevamrita Home">
			<span class="flex h-9 w-9 items-center justify-center rounded-xl bg-accent text-on-accent font-bold">S</span>
			<span><span class="block text-sm font-bold leading-tight">Sevamrita</span><span class="block text-xs text-muted">Operations</span></span>
		</RouterLink>
		<div class="min-h-0 flex-1 overflow-y-auto px-3 py-3"><AppNav layout="sidebar" :items="items" aria-label="Sections" /></div>
		<RouterLink to="/profile" class="flex items-center gap-3 border-t border-line p-4 hover:bg-soft">
			<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-bold text-accent">{{ initials }}</span>
			<span class="min-w-0"><span class="block truncate text-sm font-semibold">{{ fullName }}</span><span class="block truncate text-xs text-muted">{{ roleLabel }}</span></span>
		</RouterLink>
	</aside>
	<div v-if="open" class="fixed inset-0 z-40 bg-ink/40 lg:hidden" @click="$emit('close')"></div>
	<aside v-if="open" class="fixed inset-y-0 left-0 z-50 flex w-[min(19rem,85vw)] flex-col bg-surface shadow-lift lg:hidden" aria-label="Mobile menu">
		<div class="flex items-center justify-between border-b border-line px-4 py-4">
			<span class="font-bold">Sevamrita Operations</span>
			<button type="button" class="btn-ghost" aria-label="Close menu" @click="$emit('close')"><Icon name="close" /></button>
		</div>
		<div class="min-h-0 flex-1 overflow-y-auto px-3 py-3"><AppNav layout="sidebar" :items="items" aria-label="Mobile sections" @navigate="$emit('close')" /></div>
		<RouterLink to="/profile" class="border-t border-line px-5 py-4 text-sm font-medium text-accent" @click="$emit('close')">{{ fullName }} · Profile</RouterLink>
	</aside>
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
});
defineEmits(["close"]);
</script>
