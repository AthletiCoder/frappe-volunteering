<template>
	<section v-if="items.length">
		<div class="flex items-center justify-between mb-3">
			<h2 class="text-sm font-semibold text-ink flex items-center gap-2">
				<Icon name="check" size="sm" class="text-todo" />
				{{ title }}
				<span
					class="min-w-[1.25rem] h-5 px-1.5 rounded-full bg-todo-soft text-todo text-xs font-bold inline-flex items-center justify-center"
					>{{ items.length }}</span
				>
			</h2>
			<RouterLink v-if="seeAllTo" :to="seeAllTo" class="text-sm text-accent hover:underline">See all</RouterLink>
		</div>
		<ul class="rounded-2xl border border-line bg-surface shadow-soft divide-y divide-line overflow-hidden">
			<li v-for="item in items" :key="item.id">
				<a
					:href="item.route"
					class="flex items-start gap-3 px-4 py-3.5 hover:bg-accent-soft transition-colors duration-150 active:scale-[0.99]"
				>
					<span
						:class="
							cn(
								'mt-0.5 w-9 h-9 rounded-xl flex items-center justify-center shrink-0',
								item.bucket === 'pay'
									? 'bg-warn-soft text-warn'
									: item.bucket === 'yours'
										? 'bg-soft text-muted'
										: 'bg-todo-soft text-todo'
							)
						"
					>
						<Icon :name="item.bucket === 'pay' ? 'wallet' : item.bucket === 'yours' ? 'clock' : 'check'" />
					</span>
					<div class="min-w-0 flex-1">
						<div class="text-[11px] font-semibold uppercase tracking-wide text-muted">{{ item.kind }}</div>
						<div class="font-medium text-ink truncate">{{ item.title }}</div>
						<div class="text-sm text-muted truncate">{{ item.subtitle }}</div>
					</div>
					<span class="text-sm font-medium text-accent shrink-0 mt-3">Open</span>
				</a>
			</li>
		</ul>
	</section>
	<section v-else-if="showEmpty" class="rounded-2xl border border-dashed border-line bg-surface p-6 text-center">
		<Icon name="spark" class="mx-auto text-ok mb-2" size="lg" />
		<h2 class="text-sm font-semibold text-ink">{{ title }}</h2>
		<p class="text-sm text-muted mt-1">Nothing waiting. You’re clear.</p>
	</section>
</template>

<script setup>
import { RouterLink } from "vue-router";
import Icon from "./Icon.vue";
import { cn } from "../lib/cn";

defineProps({
	title: { type: String, default: "To-do" },
	items: { type: Array, default: () => [] },
	seeAllTo: { type: String, default: "" },
	showEmpty: { type: Boolean, default: false },
});
</script>
