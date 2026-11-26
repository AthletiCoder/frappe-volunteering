import "./index.css";
import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import { initTheme } from "./lib/theme";
import App from "./App.vue";
import Home from "./views/Home.vue";
const Todos = () => import("./views/Todos.vue");
const Records = () => import("./views/Records.vue");
const BudgetHealth = () => import("./views/BudgetHealth.vue");
const Advances = () => import("./views/Advances.vue");
const AdvanceWorkflow = () => import("./views/AdvanceWorkflow.vue");
const InvoiceGenerator = () => import("./views/InvoiceGenerator.vue");
const ExpenseClaim = () => import("./views/ExpenseClaim.vue");
const MultiInvoiceExpenseClaim = () => import("./views/MultiInvoiceExpenseClaim.vue");
const ExpenseClaims = () => import("./views/ExpenseClaims.vue");
const ExpenseClaimWorkflow = () => import("./views/ExpenseClaimWorkflow.vue");
const Projects = () => import("./views/Projects.vue");
const ProjectProposalReviews = () => import("./views/ProjectProposalReviews.vue");
const BankAccounts = () => import("./views/BankAccounts.vue");
const OfficeAddresses = () => import("./views/OfficeAddresses.vue");
const Profile = () => import("./views/Profile.vue");
const ProjectAccountMapping = () => import("./views/ProjectAccountMapping.vue");
const Team = () => import("./views/Team.vue");
const HRManagement = () => import("./views/HRManagement.vue");
const SystemManagement = () => import("./views/SystemManagement.vue");
const ChartOfAccounts = () => import("./views/ChartOfAccounts.vue");
const ExpenseApprovalLimits = () => import("./views/ExpenseApprovalLimits.vue");
const Donations = () => import("./views/Donations.vue");
const OpeningBalances = () => import("./views/OpeningBalances.vue");
const FiscalYears = () => import("./views/FiscalYears.vue");
const WorkLogs = () => import("./views/WorkLogs.vue");
const TimeLeave = () => import("./views/TimeLeave.vue");
const VendorPurchases = () => import("./views/VendorPurchases.vue");
const Collaboration = () => import("./views/Collaboration.vue");

initTheme();

const router = createRouter({
	history: createWebHistory("/volunteering"),
	routes: [
		{ path: "/", redirect: "/home" },
		{ path: "/home", component: Home, name: "Home" },
		{ path: "/collaboration", component: Collaboration, name: "Collaboration" },
		{ path: "/vendor-purchases", component: VendorPurchases, name: "VendorPurchases", props: { workspaceView: "requests" }, beforeEnter: to => to.query.view === "payments" ? { path: "/purchase-accounts", query: to.query } : undefined },
		{ path: "/purchase-approvals", component: VendorPurchases, name: "PurchaseApprovals", props: { workspaceView: "approvals" } },
		{ path: "/purchase-accounts", component: VendorPurchases, name: "PurchaseAccounts", props: { workspaceView: "accounts" } },
		{ path: "/donations", component: Donations, name: "Donations" },
		{ path: "/opening-balances", component: OpeningBalances, name: "OpeningBalances" },
		{ path: "/fiscal-years", component: FiscalYears, name: "FiscalYears" },
		{ path: "/work-logs", component: WorkLogs, name: "WorkLogs" },
		{ path: "/time-leave", component: TimeLeave, name: "TimeLeave" },
		{ path: "/profile", component: Profile, name: "Profile" },
		{ path: "/todos", component: Todos, name: "Todos" },
		{ path: "/records", component: Records, name: "Records" },
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
		{
			path: "/expense-approval-limits",
			component: ExpenseApprovalLimits,
			name: "ExpenseApprovalLimits",
		},
		{ path: "/invoice-generator", component: InvoiceGenerator, name: "InvoiceGenerator" },
		{
			path: "/invoice-expense-claim",
			component: ExpenseClaim,
			name: "InvoiceExpenseClaim",
		},
		{ path: "/expense-claim", component: ExpenseClaim, name: "ExpenseClaim" },
		{ path: "/expense-claim/multiple", component: MultiInvoiceExpenseClaim, name: "MultiInvoiceExpenseClaim" },
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

const root = document.querySelector("#app");

// Stop the browser from stepping a focused number input during wheel scrolling.
root.addEventListener("wheel", (event) => {
	if (!event.ctrlKey && event.target instanceof HTMLInputElement
		&& event.target.type === "number" && event.target.matches(":focus")) {
		event.preventDefault();
	}
}, { capture: true, passive: false });

const app = createApp(App);
app.use(router);
app.mount(root);
