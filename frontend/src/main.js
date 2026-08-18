import "./index.css";
import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import { initTheme } from "./lib/theme";
import App from "./App.vue";
import Home from "./views/Home.vue";
import BudgetHealth from "./views/BudgetHealth.vue";
import Advances from "./views/Advances.vue";

initTheme();

const router = createRouter({
	history: createWebHistory("/volunteering"),
	routes: [
		{ path: "/", redirect: "/home" },
		{ path: "/home", component: Home, name: "Home" },
		{ path: "/todos", redirect: { path: "/home", hash: "#todos" } },
		{ path: "/budget-health", component: BudgetHealth, name: "BudgetHealth" },
		{ path: "/advances", component: Advances, name: "Advances" },
		{ path: "/advances/:name", component: Advances, name: "AdvanceDetail" },
	],
});

const app = createApp(App);
app.use(router);
app.mount("#app");
