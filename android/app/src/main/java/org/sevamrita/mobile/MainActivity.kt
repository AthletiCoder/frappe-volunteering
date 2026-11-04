package org.sevamrita.mobile

import android.os.Bundle
import android.os.Build
import android.Manifest
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.platform.LocalContext
import org.sevamrita.mobile.reminders.WorkReminders
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.imePadding
import androidx.compose.material3.AlertDialog
import org.sevamrita.mobile.ui.ChatView
import org.sevamrita.mobile.ui.TrackerFilter
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Assignment
import androidx.compose.material.icons.automirrored.filled.ReceiptLong
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Checklist
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Timeline
import androidx.compose.material.icons.filled.Wallet
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import org.json.JSONObject
import org.sevamrita.mobile.data.Server
import org.sevamrita.mobile.data.DemoLogins
import org.sevamrita.mobile.data.display
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import org.sevamrita.mobile.ui.AdvanceRequestScreen
import org.sevamrita.mobile.ui.ExpenseRequestScreen
import org.sevamrita.mobile.ui.AdvanceQueueScreen
import org.sevamrita.mobile.ui.AdvanceReviewScreen
import org.sevamrita.mobile.ui.ClaimQueueScreen
import org.sevamrita.mobile.ui.ClaimReviewScreen
import org.sevamrita.mobile.ui.ReceiptScreen
import org.sevamrita.mobile.ui.ProposalsScreen
import org.sevamrita.mobile.ui.ProposalScreen
import org.sevamrita.mobile.ui.ProposalFormScreen
import org.sevamrita.mobile.ui.Page
import org.sevamrita.mobile.ui.PortalState
import org.sevamrita.mobile.ui.PortalViewModel
import org.sevamrita.mobile.ui.ChartScreen
import org.sevamrita.mobile.ui.LedgerScreen
import org.sevamrita.mobile.ui.AccountFormScreen
import org.sevamrita.mobile.ui.BankAccountScreen
import org.sevamrita.mobile.ui.OfficeAddressesScreen
import org.sevamrita.mobile.ui.OfficeAddressFormScreen
import org.sevamrita.mobile.ui.TeamScreen
import org.sevamrita.mobile.ui.OpeningBalancesScreen
import org.sevamrita.mobile.ui.ProjectMappingScreen
import org.sevamrita.mobile.ui.ProjectMappingDetailScreen
import org.sevamrita.mobile.ui.ClaimLimitsScreen
import org.sevamrita.mobile.ui.FiscalYearsScreen
import org.sevamrita.mobile.ui.DonationScreen
import org.sevamrita.mobile.ui.HRManagementScreen
import org.sevamrita.mobile.ui.ManagedEmployeeFormScreen
import org.sevamrita.mobile.ui.SystemManagementScreen
import org.sevamrita.mobile.ui.ManagedUserFormScreen
import org.sevamrita.mobile.ui.InvoiceScreen
import org.sevamrita.mobile.ui.InvoiceResultScreen
import org.sevamrita.mobile.ui.MultiClaimScreen
import org.sevamrita.mobile.ui.MultiResultScreen
import org.sevamrita.mobile.ui.BudgetHealthScreen
import org.sevamrita.mobile.ui.CombinedClaimScreen
import org.sevamrita.mobile.ui.CorrectClaimScreen
import org.sevamrita.mobile.ui.CollaborationScreen

private val green = Color(0xFF08745E)
private val ink = Color(0xFF1D3035)
private val muted = Color(0xFF637378)
private val canvas = Color(0xFFF5F7F4)
private val pale = Color(0xFFE5F3ED)

private data class WorkLink(val item: String, val room: String, val kind: String)

class MainActivity : ComponentActivity() {
    private var pendingWork by mutableStateOf<WorkLink?>(null)
    private fun readWorkLink(intent: Intent?) {
        val item = intent?.getStringExtra("work_item").orEmpty()
        val room = intent?.getStringExtra("work_room").orEmpty()
        val kind = intent?.getStringExtra("work_kind").orEmpty()
        if (item.isNotBlank() && room.isNotBlank() && kind in listOf("Task", "Tracker")) pendingWork = WorkLink(item, room, kind)
        intent?.removeExtra("work_item")
    }
    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); setIntent(intent); readWorkLink(intent) }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        readWorkLink(intent)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.light(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.light(android.graphics.Color.WHITE, android.graphics.Color.WHITE)
        )
        setContent {
            MaterialTheme(colorScheme = lightColorScheme(
                primary = green, onPrimary = Color.White, background = canvas,
                onBackground = ink, surface = Color.White, onSurface = ink,
                secondaryContainer = pale, onSecondaryContainer = ink
            )) {
                val model: PortalViewModel = viewModel()
                PortalApp(model, onExit = { finish() }, workLink = pendingWork, onWorkLinkHandled = { pendingWork = null })
            }
        }
    }
}

@Composable
private fun PortalApp(model: PortalViewModel, onExit: () -> Unit, workLink: WorkLink?, onWorkLinkHandled: () -> Unit) {
    val state = model.state.value
    val context = LocalContext.current
    var reminderSettings by remember { mutableStateOf(false) }
    val notificationPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        WorkReminders.reschedule(context); WorkReminders.requestSync(context)
    }
    LaunchedEffect(state.signedIn, state.user) {
        if (state.signedIn && Build.VERSION.SDK_INT >= 33 && !WorkReminders.notificationsAllowed(context)) {
            val prefs = context.getSharedPreferences("reminder_permission", android.content.Context.MODE_PRIVATE)
            if (!prefs.getBoolean("asked", false)) { prefs.edit().putBoolean("asked", true).apply(); notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS) }
        }
    }
    LaunchedEffect(state.signedIn, workLink) {
        if (state.signedIn && workLink != null) {
            if (workLink.kind == "Tracker") model.openTracker(workLink.room, workLink.item) else model.openTask(workLink.room, workLink.item)
            onWorkLinkHandled()
        }
    }
    var confirmExit by remember { mutableStateOf(false) }
    if (state.booting) {
        Box(Modifier.fillMaxSize().background(canvas).safeDrawingPadding(), contentAlignment = Alignment.Center) {
            Text(BuildConfig.APP_NAME, color = green, fontWeight = FontWeight.Bold, fontSize = 30.sp)
        }
        return
    }
    if (!state.signedIn) { LoginScreen(state, model); return }
    BackHandler { if (!model.backInChat()) confirmExit = true }
    val screenStates = rememberSaveableStateHolder()
    val route = state.chatNavigation.current
    val depth = state.chatNavigation.history.size
    var previousRoute by remember { mutableStateOf(route) }
    var previousDepth by remember { mutableStateOf(depth) }
    val motion = remember(route) { Animatable(if (route == previousRoute) 1f else 0f) }
    val direction = remember(route) { if (depth < previousDepth) -1 else 1 }
    val layoutDirection = LocalLayoutDirection.current
    LaunchedEffect(route) {
        previousRoute = route
        previousDepth = depth
        motion.animateTo(1f, tween(durationMillis = 170, easing = FastOutSlowInEasing))
    }
    val roomChat = state.page != Page.RECEIPT && route.view == ChatView.CHAT
    var menuExpanded by remember { mutableStateOf(false) }
    val canGoBack = state.page == Page.RECEIPT || state.chatNavigation.canGoBack
    val title = if (state.page == Page.RECEIPT) state.receiptName else when (route.view) {
        ChatView.CONVERSATIONS -> "Chats"
        ChatView.MY_TASKS -> "My tasks"
        ChatView.TASKS -> "Tasks"
        ChatView.TRACKERS -> "Trackers"
        ChatView.MY_TRACKERS -> "My trackers"
        ChatView.TRACKER -> "Tracker"
        ChatView.TASK -> "Task"
        ChatView.CHAT -> state.chatRoom.optJSONObject("space")?.text("title").orEmpty().ifBlank { "Chat" }
    }
    Scaffold(
        containerColor = canvas,
        contentWindowInsets = WindowInsets.safeDrawing,
        topBar = {
            Column(Modifier.fillMaxWidth().background(Color.White).windowInsetsPadding(
                WindowInsets.safeDrawing.only(WindowInsetsSides.Top + WindowInsetsSides.Horizontal))) {
                if (!roomChat) Row(Modifier.fillMaxWidth().heightIn(min = 64.dp).padding(horizontal = 12.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    if (canGoBack) IconButton(onClick = { model.backInChat() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                    Column(Modifier.weight(1f)) {
                        Text(if (route.view == ChatView.CONVERSATIONS && state.page != Page.RECEIPT) BuildConfig.APP_NAME else title,
                            color = if (route.view == ChatView.CONVERSATIONS) green else ink,
                            fontWeight = FontWeight.Bold, fontSize = 25.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                    val trackerList = route.view in listOf(ChatView.TRACKERS, ChatView.MY_TRACKERS)
                    if (state.page != Page.RECEIPT && trackerList) TrackerFilter(state.trackerFilter, model::setTrackerFilter)
                    if (state.page != Page.RECEIPT && !trackerList && route.view != ChatView.MY_TASKS) IconButton(onClick = model::showPersonalTasks) {
                        Icon(Icons.Default.Checklist, "My tasks", tint = green)
                    }
                    if (state.page != Page.RECEIPT && !trackerList && route.view != ChatView.MY_TRACKERS) IconButton(onClick = model::showPersonalTrackers) {
                        Icon(Icons.Default.Timeline, "My trackers", tint = green)
                    }
                    Box {
                        IconButton(onClick = { menuExpanded = true }) { Icon(Icons.Default.MoreVert, "More options", tint = muted) }
                        DropdownMenu(expanded = menuExpanded, onDismissRequest = { menuExpanded = false }) {
                            DropdownMenuItem(text = { Text("Chats") }, onClick = { menuExpanded = false; model.showChatConversations() })
                            DropdownMenuItem(text = { Text("My tasks") }, onClick = { menuExpanded = false; model.showPersonalTasks() })
                            DropdownMenuItem(text = { Text("My trackers") }, onClick = { menuExpanded = false; model.showPersonalTrackers() })
                            DropdownMenuItem(text = { Text("Reminders") }, onClick = { menuExpanded = false; reminderSettings = true })
                            DropdownMenuItem(text = { Text("Refresh") }, onClick = { menuExpanded = false; model.refreshChat() })
                            DropdownMenuItem(text = { Text("Switch user") }, onClick = { menuExpanded = false; model.logout() }, enabled = !state.busy)
                        }
                    }
                }
            }
        }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).imePadding()) {
            if (state.error.isNotBlank()) MessageBar(state.error, isError = true, onDismiss = model::dismissMessage)
            if (state.notice.isNotBlank()) MessageBar(state.notice, isError = false, onDismiss = model::dismissMessage)
            if (state.page == Page.RECEIPT) ReceiptScreen(state) else Box(Modifier.weight(1f).fillMaxWidth().clipToBounds()) {
                Box(Modifier.fillMaxSize().graphicsLayer {
                    val remaining = 1f - motion.value
                    val side = if (layoutDirection == LayoutDirection.Ltr) direction else -direction
                    translationX = 16.dp.toPx() * side * remaining
                    alpha = 1f - 0.17f * remaining
                }) {
                    screenStates.SaveableStateProvider("${state.user}:${route.view}:${route.room}:${route.item}") {
                        CollaborationScreen(state, model)
                    }
                }
            }
        }
    }
    if (reminderSettings) AlertDialog(onDismissRequest = { reminderSettings = false },
        title = { Text("Work reminders") },
        text = { Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Reminders use the portal's time zone. Date-only tasks and trackers remind at 09:00.")
            Text(if (WorkReminders.notificationsAllowed(context)) "Notifications are enabled." else "Notifications are currently blocked.")
            if (!WorkReminders.notificationsAllowed(context)) TextButton(onClick = {
                if (Build.VERSION.SDK_INT >= 33) notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                context.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName))
            }) { Text("Enable notifications") }
            Text(if (WorkReminders.precise(context)) "Precise timing is enabled." else "Allow precise timing for reminders at the chosen time. Otherwise Android may delay them.")
            if (Build.VERSION.SDK_INT >= 31 && !WorkReminders.precise(context)) TextButton(onClick = {
                context.startActivity(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM, Uri.parse("package:${context.packageName}")))
            }) { Text("Enable precise timing") }
        } }, confirmButton = { TextButton(onClick = { reminderSettings = false; WorkReminders.reschedule(context); WorkReminders.requestSync(context) }) { Text("Done") } })
    if (confirmExit) AlertDialog(
        onDismissRequest = { confirmExit = false },
        title = { Text("Exit ${BuildConfig.APP_NAME}?") },
        text = { Text("You are on the first screen. Your session will remain signed in.") },
        confirmButton = { TextButton(onClick = { confirmExit = false; onExit() }) { Text("Exit") } },
        dismissButton = { TextButton(onClick = { confirmExit = false }) { Text("Stay") } }
    )
}

private fun pageTitle(state: PortalState) = when (state.page) {
    Page.HOME -> "Home"; Page.WORK -> "My work"; Page.PROJECTS -> "Projects"
    Page.COLLABORATION -> "Chat & workspaces"
    Page.PROJECT -> state.detailId; Page.ADVANCES -> "Advances"; Page.ADVANCE -> state.detailId
    Page.PROPOSALS -> "Project proposals"; Page.PROPOSAL -> state.detailId; Page.PROPOSAL_FORM -> "Project proposal"
    Page.NEW_ADVANCE -> "Request an advance"; Page.CLAIMS -> "Expense claims"; Page.CLAIM -> state.detailId
    Page.NEW_CLAIM -> "Submit an expense"; Page.PROFILE -> "My profile"; Page.UNAVAILABLE -> state.unavailableLabel
    Page.ADVANCE_QUEUE -> "Advance approvals"; Page.ADVANCE_REVIEW -> state.detailId
    Page.CLAIM_QUEUE -> "Expense review"; Page.CLAIM_REVIEW -> state.detailId
    Page.RECEIPT -> state.receiptName
    Page.CHART -> "Chart of Accounts"; Page.LEDGER -> "Account ledger"; Page.ACCOUNT_FORM -> "Account details"
    Page.BANK_ACCOUNT -> "Bank account"; Page.OFFICE_ADDRESSES -> "Office addresses"
    Page.OFFICE_ADDRESS_FORM -> "Office address"; Page.TEAM -> "My team"
    Page.OPENING_BALANCES -> "Opening balances"
    Page.PROJECT_MAPPING -> "Project account mapping"; Page.PROJECT_MAPPING_DETAIL -> "Project account mapping"
    Page.CLAIM_LIMITS -> "Expense approval limits"; Page.FISCAL_YEARS -> "Fiscal Years"
    Page.DONATIONS -> "Donations"
    Page.HR_MANAGEMENT -> "Employees"; Page.EMPLOYEE_FORM -> "Employee"
    Page.SYSTEM_MANAGEMENT -> "Users"; Page.USER_FORM -> "User"
    Page.INVOICE -> "Prepare an invoice"; Page.INVOICE_RESULT -> "Generated invoice"
    Page.MULTI_CLAIM -> "Multiple invoices"; Page.MULTI_RESULT -> "Invoices submitted"
    Page.COMBINED_START -> "Invoice and expense"; Page.COMBINED_INVOICE -> "Sign invoice"
    Page.CORRECT_CLAIM -> "Correct claim"
    Page.BUDGET_HEALTH -> "Budget health"
}
private fun parentOf(page: Page) = when (page) {
    Page.PROJECT -> Page.PROJECTS; Page.ADVANCE, Page.NEW_ADVANCE -> Page.ADVANCES
    Page.PROPOSAL, Page.PROPOSAL_FORM -> Page.PROPOSALS
    Page.CLAIM, Page.NEW_CLAIM -> Page.CLAIMS
    Page.LEDGER, Page.ACCOUNT_FORM -> Page.CHART
    Page.OFFICE_ADDRESS_FORM -> Page.OFFICE_ADDRESSES
    Page.PROJECT_MAPPING_DETAIL -> Page.PROJECT_MAPPING
    Page.EMPLOYEE_FORM -> Page.HR_MANAGEMENT; Page.USER_FORM -> Page.SYSTEM_MANAGEMENT
    Page.INVOICE_RESULT -> Page.INVOICE
    Page.MULTI_CLAIM, Page.MULTI_RESULT -> Page.CLAIMS
    Page.COMBINED_START -> Page.CLAIMS; Page.COMBINED_INVOICE -> Page.COMBINED_START
    Page.CORRECT_CLAIM -> Page.CLAIM
    else -> Page.HOME
}

@Composable
private fun LoginScreen(state: PortalState, model: PortalViewModel) {
    var username by androidx.compose.runtime.saveable.rememberSaveable { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }
    var expanded by remember { mutableStateOf(false) }
    val demoAccounts = DemoLogins.accounts(state.server)
    var demoEmail by remember { mutableStateOf(demoAccounts.firstOrNull()?.email.orEmpty()) }
    var demoExpanded by remember { mutableStateOf(false) }
    var manualLogin by remember { mutableStateOf(false) }
    var localAddress by remember(state.localAddress) { mutableStateOf(state.localAddress) }
    LazyColumn(
        Modifier.fillMaxSize().background(canvas).safeDrawingPadding().imePadding(), contentPadding = PaddingValues(24.dp),
        verticalArrangement = Arrangement.Center
    ) {
        item {
            Surface(color = green, shape = RoundedCornerShape(18.dp), modifier = Modifier.size(58.dp)) {
                Box(contentAlignment = Alignment.Center) { Text("S", fontSize = 30.sp, color = Color.White, fontWeight = FontWeight.Bold) }
            }
            Spacer(Modifier.height(22.dp))
            Text(BuildConfig.APP_NAME, fontSize = 34.sp, fontWeight = FontWeight.Bold, color = ink)
            Text("Conversations and tasks for your team.", color = muted, fontSize = 16.sp)
            Spacer(Modifier.height(30.dp))
            SectionCard {
                Text("Sign in", fontWeight = FontWeight.SemiBold, fontSize = 21.sp)
                Spacer(Modifier.height(16.dp))
                if (Server.available().size > 1) Box {
                    OutlinedButton(onClick = { expanded = true }, modifier = Modifier.fillMaxWidth()) { Text("Server: ${state.server.label}") }
                    DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                        Server.available().forEach { server ->
                            DropdownMenuItem(text = { Text(server.label) }, onClick = { expanded = false; model.selectServer(server) })
                        }
                    }
                }
                if (BuildConfig.LOCAL_PORTAL_ONLY) {
                    Text("Local testing only", color = green, fontWeight = FontWeight.SemiBold)
                    Text("Connect this phone and your laptop to the same Wi-Fi.", color = muted, fontSize = 13.sp)
                    Spacer(Modifier.height(10.dp))
                }
                if (state.server == Server.LOCAL) {
                    OutlinedTextField(
                        localAddress, { localAddress = it },
                        label = { Text("Laptop Wi-Fi IP address") },
                        supportingText = { Text("Port 8001 · use 10.0.2.2 only in the Android emulator") },
                        singleLine = true, modifier = Modifier.fillMaxWidth()
                    )
                }
                if (demoAccounts.isNotEmpty() && !manualLogin) {
                    Text("Choose a demo user", fontWeight = FontWeight.Medium)
                    Box {
                        OutlinedButton(onClick = { demoExpanded = true }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) {
                            Text("${demoAccounts.firstOrNull { it.email == demoEmail }?.label ?: "Select a user"} ▾")
                        }
                        DropdownMenu(expanded = demoExpanded, onDismissRequest = { demoExpanded = false }) {
                            demoAccounts.forEach { account -> DropdownMenuItem(
                                text = { Column { Text(account.label); Text(account.email, fontSize = 12.sp, color = muted) } },
                                onClick = { demoEmail = account.email; demoExpanded = false; model.dismissMessage() }
                            ) }
                        }
                    }
                    Text("No password entry needed for these local demo accounts.", color = muted, fontSize = 13.sp)
                    Button(onClick = { model.loginDemo(demoEmail, localAddress) }, enabled = !state.busy && demoAccounts.any { it.email == demoEmail }, modifier = Modifier.fillMaxWidth()) {
                        Text(if (state.busy) "Signing in…" else "Sign in")
                    }
                    TextButton(onClick = { manualLogin = true; model.dismissMessage() }, enabled = !state.busy) { Text("Sign in with another account") }
                } else {
                    OutlinedTextField(username, { username = it }, label = { Text("ERP email address") }, singleLine = true,
                        keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.Email),
                        modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(password, { password = it }, label = { Text("Password") }, singleLine = true,
                        visualTransformation = if (passwordVisible) androidx.compose.ui.text.input.VisualTransformation.None else PasswordVisualTransformation(),
                        trailingIcon = { TextButton(onClick = { passwordVisible = !passwordVisible }) { Text(if (passwordVisible) "Hide" else "Show") } },
                        keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.Password),
                        modifier = Modifier.fillMaxWidth())
                    Spacer(Modifier.height(10.dp))
                    Button(onClick = { model.login(username, password, if (state.server == Server.LOCAL) localAddress else null) }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) {
                        Text(if (state.busy) "Signing in…" else "Sign in")
                    }
                    TextButton(onClick = { model.requestPasswordReset(username, localAddress) }, enabled = !state.busy) { Text("Forgot password?") }
                    if (demoAccounts.isNotEmpty()) TextButton(onClick = { manualLogin = false; password = ""; model.dismissMessage() }, enabled = !state.busy) { Text("Back to demo users") }
                }
            }
            if (state.error.isNotBlank()) {
                Spacer(Modifier.height(12.dp))
                Text(state.error, color = MaterialTheme.colorScheme.error)
            }
            if (state.notice.isNotBlank()) {
                Spacer(Modifier.height(12.dp))
                Text(state.notice, color = green)
            }
            Spacer(Modifier.height(16.dp))
            Text("Use your Sevamrita ERP account. App chat access must be enabled for your user.", color = muted, fontSize = 13.sp)
        }
    }
}

@Composable
private fun HomeScreen(state: PortalState, model: PortalViewModel) {
    val home = state.home
    val projects = home.items("member_projects")
    val actions = home.optJSONObject("actions") ?: JSONObject()
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        if (projects.isNotEmpty()) {
            item { Heading("Your active projects", "Choose the project before starting work") }
            items(projects) { project ->
                SectionCard {
                    Text(project.display("project_name"), fontWeight = FontWeight.Bold, fontSize = 19.sp)
                    Text(project.display("name"), color = muted, fontSize = 12.sp)
                    if (project.text("purpose").isNotBlank()) Text(project.text("purpose"), color = muted)
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        SmallAction("Expense", Modifier.weight(1f), enabled = project.optBoolean("can_submit_expense")) { model.open(Page.NEW_CLAIM, project.text("name")) }
                        SmallAction("Advance", Modifier.weight(1f)) { model.open(Page.NEW_ADVANCE, project.text("name")) }
                    }
                    OutlinedButton(onClick = { model.open(Page.INVOICE) }, modifier = Modifier.fillMaxWidth()) { Text("Prepare an invoice") }
                    TextButton(onClick = { model.open(Page.PROJECT, project.text("name")) }) { Text("View project →") }
                }
            }
        } else item {
            Heading("Welcome, ${home.display("full_name", "there")}", "Your Sevamrita workspace")
        }
        if (home.items("waiting").isNotEmpty()) {
            item { Heading("Waiting on you") }
            items(home.items("waiting").take(5)) { row -> ActionRow(row.display("title"), row.text("subtitle")) {
                model.openAction(row.display("title"), row.text("route"))
            } }
        }
        if (home.items("resume").isNotEmpty()) {
            item { Heading("Pick up where you left off") }
            items(home.items("resume").take(4)) { row -> ActionRow(row.display("title"), row.text("subtitle")) {
                model.openAction(row.display("title"), row.text("route"))
            } }
        }
        item { Heading("Explore", "Only the actions available to your account are shown") }
        val sections = listOf("collaboration" to "Collaboration", "projects" to "Projects", "money" to "Money", "accounts" to "Accounts", "team" to "Team", "time" to "Time & leave", "hr_management" to "HR", "system_management" to "System", "organisation" to "Organisation")
        sections.forEach { (key, label) ->
            val rows = actions.items(key).filterNot { it.text("route").startsWith("/desk/") }
            if (rows.isNotEmpty()) {
                item { Text(label.uppercase(), color = green, fontWeight = FontWeight.Bold, fontSize = 12.sp, letterSpacing = 1.sp) }
                items(rows) { row -> ActionRow(row.display("label"), row.text("hint")) { model.openAction(row.display("label"), row.text("route")) } }
            }
        }
        item { Spacer(Modifier.height(8.dp)) }
    }
}

@Composable
private fun WorkScreen(state: PortalState, model: PortalViewModel) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Heading("Your work", "Approvals, follow-ups and drafts") }
        item { Text("WAITING ON YOU", color = green, fontSize = 12.sp, fontWeight = FontWeight.Bold) }
        if (state.home.items("waiting").isEmpty()) item { EmptyState("Nothing waiting right now") }
        items(state.home.items("waiting")) { row -> ActionRow(row.display("title"), row.text("subtitle")) { model.openAction(row.display("title"), row.text("route")) } }
        item { Text("YOUR DRAFTS", color = green, fontSize = 12.sp, fontWeight = FontWeight.Bold) }
        if (state.home.items("resume").isEmpty()) item { EmptyState("No drafts to resume") }
        items(state.home.items("resume")) { row -> ActionRow(row.display("title"), row.text("subtitle")) { model.openAction(row.display("title"), row.text("route")) } }
    }
}

@Composable
private fun ProjectsScreen(state: PortalState, model: PortalViewModel) {
    val projects = state.data.items("projects")
    val capabilities = state.data.optJSONObject("capabilities") ?: JSONObject()
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Heading("Approved projects", "Projects you are permitted to view") }
        if (capabilities.optBoolean("can_create")) item {
            Button(onClick = { model.open(Page.PROPOSAL_FORM) }, modifier = Modifier.fillMaxWidth()) { Text("Propose a project") }
        }
        if (capabilities.optBoolean("can_create")) item {
            OutlinedButton(onClick = { model.openProposals("mine") }, modifier = Modifier.fillMaxWidth()) { Text("Your proposals and change requests") }
        }
        if (capabilities.optBoolean("can_manage")) item {
            OutlinedButton(onClick = { model.openProposals("review") }, modifier = Modifier.fillMaxWidth()) { Text("Review pending proposals") }
        }
        if (projects.isEmpty() && !state.busy) item { EmptyState("No approved projects available") }
        items(projects) { project -> ActionRow(project.display("project_name"), "${project.display("name")} · ${project.display("operational_status")}") {
            model.open(Page.PROJECT, project.text("name"))
        } }
    }
}

@Composable
private fun ProjectScreen(state: PortalState, model: PortalViewModel) {
    val project = state.data
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(project.display("project_name", state.detailId), project.display("name")) }
        item { SectionCard {
            LabelValue("Status", project.display("operational_status"))
            LabelValue("Purpose", project.display("project_purpose"))
            if (project.text("project_type").isNotBlank()) LabelValue("Type", project.text("project_type"))
            if (project.text("project_owner").isNotBlank()) LabelValue("Owner", project.text("project_owner"))
            if (project.text("expected_start_date").isNotBlank()) LabelValue("Starts", project.text("expected_start_date"))
            if (project.text("expected_end_date").isNotBlank()) LabelValue("Ends", project.text("expected_end_date"))
        } }
        if (project.items("members").isNotEmpty()) item { SectionCard {
            Text("Project members", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            project.items("members").forEach { Text(it.display("full_name", it.display("user")), color = muted) }
        } }
        project.optJSONObject("financial_status")?.let { finance -> item { SectionCard {
            Text("Financial status", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            listOf("approved_budget" to "Approved budget", "pending_commitments" to "Pending commitments", "approved_expenditure" to "Approved expenditure", "available_after_commitments" to "Available after commitments").forEach { (key, label) ->
                if (finance.has(key)) LabelValue(label, money(finance.optDouble(key)))
            }
        } } }
        if (project.items("permitted_accounts").isNotEmpty()) item { SectionCard {
            Text("Expense break-up", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            project.items("permitted_accounts").forEach { Text(it.display("employee_label"), color = ink) }
        } }
        if (project.items("attachments").isNotEmpty()) item { SectionCard {
            Text("Supporting records", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            project.items("attachments").forEach { file ->
                Text("${file.display("file_name")} · ${file.display("project_visibility", "Basic")} access")
                val path = file.text("file_url")
                if (listOf(".pdf", ".png", ".jpg", ".jpeg").any { path.endsWith(it, true) })
                    TextButton(onClick = { model.openReceipt(path, Page.PROJECT) }) { Text("Open private file") }
            }
        } }
        val currentUser = project.optJSONObject("capabilities")?.text("current_user").orEmpty()
        val isMember = (project.optJSONArray("participants") ?: org.json.JSONArray()).let { people ->
            (0 until people.length()).any { people.optString(it) == currentUser }
        }
        if (isMember && project.text("operational_status") == "Active") {
            item { Button(onClick = { model.open(Page.NEW_CLAIM, state.detailId) }, modifier = Modifier.fillMaxWidth()) { Text("Submit an expense") } }
            item { OutlinedButton(onClick = { model.open(Page.NEW_ADVANCE, state.detailId) }, modifier = Modifier.fillMaxWidth()) { Text("Request an advance") } }
        }
        if (project.optJSONObject("capabilities")?.optBoolean("can_propose_changes") == true) item {
            OutlinedButton(onClick = model::openChangeRequest, modifier = Modifier.fillMaxWidth()) { Text("Propose changes to this project") }
        }
    }
}

@Composable
private fun AdvancesScreen(state: PortalState, model: PortalViewModel) {
    val advances = state.data.items("advances")
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Heading("Your advances", "Requests, approvals and settlement") }
        item { Button(onClick = { model.open(Page.NEW_ADVANCE) }, modifier = Modifier.fillMaxWidth()) { Icon(Icons.Default.Add, null); Text(" New request") } }
        if (advances.isEmpty() && !state.busy) item { EmptyState("No advance requests yet") }
        items(advances) { row -> ActionRow(row.display("purpose", row.display("name")), "${money(row.optDouble("advance_amount"))} · ${row.display("workflow_state", row.display("status"))}") {
            model.open(Page.ADVANCE, row.text("name"))
        } }
    }
}

@Composable
private fun AdvanceScreen(state: PortalState) {
    val advance = state.data
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(advance.display("purpose", state.detailId), state.detailId) }
        item { SectionCard {
            LabelValue("Status", advance.display("workflow_state", advance.display("status")))
            LabelValue("Requested", money(advance.optDouble("advance_amount")))
            LabelValue("Paid", money(advance.optDouble("paid_amount")))
            LabelValue("Still to settle", money(advance.optDouble("residual")))
            LabelValue("Project", advance.display("intended_project"))
            LabelValue("Needed by", advance.display("required_by_date"))
            LabelValue("Expected settlement", advance.display("expected_settlement_date"))
            if (advance.text("advance_additional_note").isNotBlank()) LabelValue("Note", advance.text("advance_additional_note"))
        } }
    }
}

@Composable
private fun ClaimsScreen(state: PortalState, model: PortalViewModel) {
    val claims = state.data.items("claims")
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Heading("Your expense claims", "Review progress and payment status") }
        item { Button(onClick = { model.open(Page.NEW_CLAIM) }, modifier = Modifier.fillMaxWidth()) { Icon(Icons.Default.Add, null); Text(" New claim") } }
        item { OutlinedButton(onClick = { model.open(Page.MULTI_CLAIM) }, modifier = Modifier.fillMaxWidth()) { Text("Submit multiple invoices") } }
        item { OutlinedButton(onClick = { model.open(Page.COMBINED_START) }, modifier = Modifier.fillMaxWidth()) { Text("Prepare invoice and submit expense") } }
        if (claims.isEmpty() && !state.busy) item { EmptyState("No expense claims yet") }
        items(claims) { row -> ActionRow(row.display("name"), "${row.display("project_name")} · ${money(row.optDouble("claimed_amount"))} · ${row.display("stage")}") {
            model.open(Page.CLAIM, row.text("name"))
        } }
    }
}

@Composable
private fun ClaimScreen(state: PortalState, model: PortalViewModel) {
    val claim = state.data
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(state.detailId, claim.display("project_name")) }
        item { SectionCard {
            LabelValue("Stage", claim.display("stage"))
            LabelValue("Claimed", money(claim.optDouble("claimed_amount")))
            LabelValue("Sanctioned", money(claim.optDouble("sanctioned_amount")))
            LabelValue("Reimbursed", money(claim.optDouble("reimbursed_amount")))
            LabelValue("Payment", claim.display("payment_status"))
            LabelValue("Receipt review", claim.display("receipt_review_status"))
            if (claim.text("pending_with").isNotBlank()) LabelValue("Pending with", claim.text("pending_with"))
            if (claim.text("receipt_review_notes").isNotBlank()) LabelValue("Review notes", claim.text("receipt_review_notes"))
        } }
        if (claim.optBoolean("can_correct")) item {
            Button(onClick = model::startCorrection, modifier = Modifier.fillMaxWidth()) { Text("Correct and resubmit this claim") }
        }
        item { Heading("Expense items") }
        items(claim.items("expenses")) { row -> SectionCard {
            Text(row.display("description"), fontWeight = FontWeight.SemiBold)
            LabelValue("Amount", money(row.optDouble("amount")))
            LabelValue("Invoice date", row.display("expense_date"))
            LabelValue("Category", row.display("category"))
            LabelValue("Supplier", row.display("supplier_name"))
            LabelValue("Receipt", if (row.text("receipt_attachment").isBlank()) "Not attached" else "Attached privately")
            if (row.text("receipt_attachment").isNotBlank()) TextButton(onClick = { model.openReceipt(row.text("receipt_attachment"), Page.CLAIM) }) { Text("Open private receipt") }
        } }
        if (claim.items("timeline").isNotEmpty()) {
            item { Heading("History") }
            items(claim.items("timeline")) { row -> SectionCard {
                Text(row.display("label"), fontWeight = FontWeight.SemiBold)
                Text(row.display("when"), color = muted, fontSize = 13.sp)
                if (row.text("detail").isNotBlank()) Text(row.text("detail"), color = muted)
            } }
        }
    }
}

@Composable
private fun ProfileScreen(state: PortalState, model: PortalViewModel) {
    val account = state.data.optJSONObject("account") ?: JSONObject()
    val employee = state.data.optJSONObject("employee") ?: JSONObject()
    val bank = state.form.optJSONObject("approved")
    val pending = state.form.optJSONObject("pending")
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(account.display("full_name", "My profile"), account.display("email")) }
        item { SectionCard {
            Text("Employee", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            LabelValue("Employee ID", employee.display("name"))
            LabelValue("Role", employee.display("designation"))
            LabelValue("Grade", employee.display("grade"))
            LabelValue("Reports to", employee.display("reporting_manager_name"))
            LabelValue("Work email", employee.display("company_email"))
        } }
        item { SectionCard {
            Text("Reimbursement bank account", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            if (bank == null) Text("No approved account on file", color = muted)
            else {
                LabelValue("Bank", bank.display("bank_name"))
                LabelValue("Account", bank.display("account_number_masked"))
                LabelValue("IFSC", bank.display("ifsc"))
                LabelValue("Holder", bank.display("account_holder_name"))
            }
            if (pending != null) Text("A bank-account request is awaiting review.", color = green)
        } }
        item { OutlinedButton(onClick = model::logout, modifier = Modifier.fillMaxWidth()) { Text("Log out") } }
        item { Text("Connected to ${state.server.label}. This app does not include Desk access.", color = muted, fontSize = 12.sp) }
    }
}

@Composable
private fun UnavailableScreen(state: PortalState) {
    Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
        SectionCard {
            Text("${state.unavailableLabel} isn't in the Android app yet", fontWeight = FontWeight.Bold, fontSize = 20.sp)
            Spacer(Modifier.height(8.dp))
            Text("This action is available on the Home portal, but it needs a dedicated native screen. The app will never open Desk or a web page for it.", color = muted)
        }
    }
}

@Composable
internal fun SectionCard(color: Color = Color.White, content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = color), shape = RoundedCornerShape(20.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp), content = content)
    }
}

@Composable
internal fun Heading(title: String, subtitle: String = "") {
    Column {
        Text(title, fontWeight = FontWeight.Bold, fontSize = 23.sp, color = ink)
        if (subtitle.isNotBlank()) Text(subtitle, color = muted, fontSize = 14.sp)
    }
}

@Composable
internal fun LabelValue(label: String, value: String) {
    Column {
        Text(label, color = muted, fontSize = 12.sp)
        Text(value, color = ink, fontSize = 15.sp)
    }
}

@Composable
internal fun ActionRow(title: String, subtitle: String, onClick: () -> Unit) {
    Card(onClick = onClick, colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(17.dp), modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                if (subtitle.isNotBlank()) Text(subtitle, color = muted, fontSize = 13.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
            }
            Icon(Icons.Default.ChevronRight, null, tint = green)
        }
    }
}

@Composable
private fun SmallAction(label: String, modifier: Modifier, enabled: Boolean = true, onClick: () -> Unit) {
    OutlinedButton(onClick = onClick, enabled = enabled, modifier = modifier, contentPadding = PaddingValues(horizontal = 7.dp)) { Text(label, fontSize = 12.sp, maxLines = 1) }
}

@Composable
private fun EmptyState(text: String) { SectionCard { Text(text, color = muted) } }

@Composable
private fun MessageBar(text: String, isError: Boolean, onDismiss: () -> Unit) {
    Surface(color = if (isError) Color(0xFFFFE6E3) else pale, modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(text, modifier = Modifier.weight(1f), color = if (isError) Color(0xFF9B2D25) else ink, fontSize = 13.sp)
            TextButton(onClick = onDismiss) { Text("Dismiss") }
        }
    }
}

internal fun money(amount: Double): String = "₹" + "%,.2f".format(java.util.Locale.US, amount)
