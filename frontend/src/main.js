import "./index.css";
import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import BudgetHealth from "./views/BudgetHealth.vue";
import Advances from "./views/Advances.vue";

const router = createRouter({
	history: createWebHistory("/volunteering"),
	routes: [
		{ path: "/", redirect: "/budget-health" },
		{ path: "/budget-health", component: BudgetHealth, name: "BudgetHealth" },
		{ path: "/advances", component: Advances, name: "Advances" },
		{ path: "/advances/:name", component: Advances, name: "AdvanceDetail" },
	],
});

const app = createApp(App);
app.use(router);
app.mount("#app");
