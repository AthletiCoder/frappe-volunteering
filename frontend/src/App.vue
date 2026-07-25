<template>
	<div class="min-h-screen">
		<header class="border-b bg-white px-4 py-3 flex gap-4 items-center">
			<a href="/app" class="text-sm text-gray-500 hover:text-gray-800">← Desk</a>
			<nav class="flex gap-3 text-sm font-medium">
				<RouterLink
					to="/budget-health"
					class="px-3 py-1 rounded-full"
					active-class="bg-green-100 text-green-800"
					>Budget Health</RouterLink
				>
				<RouterLink
					to="/advances"
					class="px-3 py-1 rounded-full"
					active-class="bg-blue-100 text-blue-800"
					>Advances</RouterLink
				>
			</nav>
		</header>
		<main class="max-w-6xl mx-auto p-4 md:p-6">
			<RouterView />
		</main>
	</div>
</template>

<script setup>
import { RouterLink, RouterView } from "vue-router";
</script>
