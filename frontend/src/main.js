import "./index.css";
import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import { initTheme } from "./lib/theme";
import App from "./App.vue";
import Home from "./views/Home.vue";
import Todos from "./views/Todos.vue";
import BudgetHealth from "./views/BudgetHealth.vue";
import Advances from "./views/Advances.vue";
import AdvanceWorkflow from "./views/AdvanceWorkflow.vue";
import InvoiceGenerator from "./views/InvoiceGenerator.vue";
import ExpenseClaim from "./views/ExpenseClaim.vue";
import ExpenseClaims from "./views/ExpenseClaims.vue";
import ExpenseClaimWorkflow from "./views/ExpenseClaimWorkflow.vue";
import Projects from "./views/Projects.vue";
import ProjectProposalReviews from "./views/ProjectProposalReviews.vue";
import BankAccounts from "./views/BankAccounts.vue";
import OfficeAddresses from "./views/OfficeAddresses.vue";
import Profile from "./views/Profile.vue";
import ProjectAccountMapping from "./views/ProjectAccountMapping.vue";
import Team from "./views/Team.vue";
import HRManagement from "./views/HRManagement.vue";
import SystemManagement from "./views/SystemManagement.vue";
import ChartOfAccounts from "./views/ChartOfAccounts.vue";

initTheme();

const router = createRouter({
	history: createWebHistory("/volunteering"),
	routes: [
		{ path: "/", redirect: "/home" },
		{ path: "/home", component: Home, name: "Home" },
		{ path: "/profile", component: Profile, name: "Profile" },
		{ path: "/todos", component: Todos, name: "Todos" },
		{ path: "/budget-health", component: BudgetHealth, name: "BudgetHealth" },
		{ path: "/advances", component: Advances, name: "Advances" },
		{ path: "/advances/:name", component: Advances, name: "AdvanceDetail" },
		{ path: "/advance-workflow", component: AdvanceWorkflow, name: "AdvanceWorkflow" },
		{ path: "/team", component: Team, name: "Team" },
		{ path: "/hr-management", component: HRManagement, name: "HRManagement" },
		{
			path: "/system-management",
			component: SystemManagement,
			name: "SystemManagement",
		},
		{
			path: "/chart-of-accounts",
			component: ChartOfAccounts,
			name: "ChartOfAccounts",
		},
		{ path: "/invoice-generator", component: InvoiceGenerator, name: "InvoiceGenerator" },
		{ path: "/expense-claim", component: ExpenseClaim, name: "ExpenseClaim" },
		{ path: "/expense-claims", component: ExpenseClaims, name: "ExpenseClaims" },
		{
			path: "/expense-claim-workflow",
			component: ExpenseClaimWorkflow,
			name: "ExpenseClaimWorkflow",
		},
		{ path: "/bank-account", component: BankAccounts, name: "BankAccounts" },
		{ path: "/office-addresses", component: OfficeAddresses, name: "OfficeAddresses" },
		{ path: "/projects", component: Projects, name: "Projects" },
		{
			path: "/project-proposals/review",
			component: ProjectProposalReviews,
			name: "ProjectProposalReviews",
		},
		{
			path: "/project-account-mapping",
			component: ProjectAccountMapping,
			name: "ProjectAccountMapping",
		},
	],
});

const app = createApp(App);
app.use(router);
app.mount("#app");
