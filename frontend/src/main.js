import "./index.css";
import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import { initTheme } from "./lib/theme";
import App from "./App.vue";
import Home from "./views/Home.vue";
import Todos from "./views/Todos.vue";
import BudgetHealth from "./views/BudgetHealth.vue";
import Advances from "./views/Advances.vue";
import InvoiceGenerator from "./views/InvoiceGenerator.vue";
import ExpenseClaim from "./views/ExpenseClaim.vue";
import Projects from "./views/Projects.vue";
import BankAccounts from "./views/BankAccounts.vue";
import OfficeAddresses from "./views/OfficeAddresses.vue";

initTheme();

const router = createRouter({
	history: createWebHistory("/volunteering"),
	routes: [
		{ path: "/", redirect: "/home" },
		{ path: "/home", component: Home, name: "Home" },
		{ path: "/todos", component: Todos, name: "Todos" },
		{ path: "/budget-health", component: BudgetHealth, name: "BudgetHealth" },
		{ path: "/advances", component: Advances, name: "Advances" },
		{ path: "/advances/:name", component: Advances, name: "AdvanceDetail" },
		{ path: "/invoice-generator", component: InvoiceGenerator, name: "InvoiceGenerator" },
		{ path: "/expense-claim", component: ExpenseClaim, name: "ExpenseClaim" },
		{ path: "/bank-account", component: BankAccounts, name: "BankAccounts" },
		{ path: "/office-addresses", component: OfficeAddresses, name: "OfficeAddresses" },
		{ path: "/projects", component: Projects, name: "Projects" },
	],
});

const app = createApp(App);
app.use(router);
app.mount("#app");
