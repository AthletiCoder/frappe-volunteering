import { expect, test, type Page } from '@playwright/test';
import { loginViaAPI } from '../../helpers/auth';
import { portalCall, requireLocalRegression } from '../../helpers/portal-regression';
import { PERSONAS } from '../../helpers/personas';

const API = 'volunteering.volunteering.collaboration.';
const password = 'DemoChat!2026';
const users = { owner: 'demo.chat.ravi@sevamrita.local', member: 'demo.chat.arjun@sevamrita.local', viewer: 'demo.chat.dev@sevamrita.local' };
async function signIn(page: Page, person: keyof typeof users = 'owner', route = '/volunteering/collaboration') {
    // Stop the previous account's page requests before replacing its session cookies.
    await page.goto('about:blank');
    await page.context().clearCookies();
    await loginViaAPI(page.request, users[person], password);
    await page.goto(route);
    await expect(page.getByRole('heading', { name: 'Chat & workspaces', exact: true })).toBeVisible();
    await expect(page.getByRole('status', { name: 'Loading your conversations…' })).toHaveCount(0);
    await expect(page.locator('.space-link').first()).toBeVisible();
}
async function newRoom(page: Page, members = false) {
    const title = `QA kitchen ${Date.now()}`;
    await page.getByRole('button', { name: '+ New conversation', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'New conversation', exact: true });
    await dialog.getByLabel('Name', { exact: true }).fill(title);
    if (members) for (const user of [users.member, users.viewer]) {
        await dialog.getByLabel('Add person', { exact: true }).selectOption(user);
        await dialog.getByRole('button', { name: 'Add member', exact: true }).click();
    }
    if (members) await dialog.getByLabel('Access for Dev Patil').selectOption('Viewer');
    const saved = page.waitForResponse(r => r.url().endsWith(API + 'save_space'));
    await dialog.getByRole('button', { name: 'Save conversation', exact: true }).click();
    const response = await saved;
    expect(response.status(), await response.text()).toBe(200);
    const name = (await response.json()).message.name;
    await expect(page.locator('.room-header h2')).toHaveText(title);
    return { name, title };
}
async function createItem(page: Page, type: string, title: string) {
    await page.getByRole('button', { name: '+ Create', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Create work item', exact: true });
    await dialog.getByLabel('Type', { exact: true }).selectOption(type);
    await dialog.getByLabel('Title', { exact: true }).fill(title);
    return dialog;
}
async function saveItem(page: Page) {
    const saved = page.waitForResponse(r => r.url().endsWith(API + 'save_item'));
    await page.getByRole('button', { name: 'Save work item', exact: true }).click();
    const response = await saved;
    expect(response.status(), await response.text()).toBe(200);
    await expect(page.getByRole('dialog')).toHaveCount(0);
    return (await response.json()).message;
}
test.beforeEach(({ baseURL }) => requireLocalRegression(baseURL));

test.beforeAll(async ({ request, baseURL }) => {
    if (new URL(baseURL!).port !== '8002') throw new Error('Use playwright.collaboration.config.ts and the isolated regression site, not the review database.');
    await loginViaAPI(request, users.owner, password);
    const session = await request.get('/api/method/volunteering.volunteering.mobile_session.get_mobile_session');
    const csrf = (await session.json()).message.csrf_token;
    const response = await request.post('/api/method/' + API + 'get_collaboration_home', {headers: {'X-Frappe-CSRF-Token': csrf}});
    expect(response.ok()).toBeTruthy();
    expect((await response.json()).message.isolated_test_site, 'Refuse to create test chats in the user review database').toBe(true);
});

test('Chat-only Website User opens Home and the native session bootstrap without Desk', async ({ page }) => {
    await loginViaAPI(page.request, users.owner, password);
    await page.goto('/volunteering/home');
    const home = await portalCall(page, 'volunteering.volunteering.home_service.get_home_payload');
    expect(home.flags.show_chat).toBeTruthy();
    const group = page.getByRole('navigation', { name: 'Sections', exact: true }).locator('details').filter({ has: page.locator('summary').filter({ hasText: 'Collaboration' }) });
    await group.locator('summary').click();
    await expect(group.getByRole('link', { name: 'Chat & workspaces', exact: true })).toBeVisible();
    const session = await page.request.get('/api/method/volunteering.volunteering.mobile_session.get_mobile_session');
    expect(session.status()).toBe(200);
    expect((await session.json()).message.user).toBe(users.owner);
    await group.getByRole('link', { name: 'Chat & workspaces', exact: true }).click();
    await expect(page.locator('.collab-heading h1')).toHaveText('Chat & workspaces');
});

test('An employee without Chat access cannot open the page or use its endpoints', async ({ page }) => {
    await loginViaAPI(page.request, PERSONAS.employee.email, PERSONAS.employee.password);
    await page.goto('/volunteering/home');
    const home = await portalCall(page, 'volunteering.volunteering.home_service.get_home_payload');
    expect(home.flags.show_chat).toBeFalsy();
    expect(home.actions.collaboration || []).toHaveLength(0);
    const denied = await page.request.post(`/api/method/${API}get_collaboration_home`, { headers: { 'X-Frappe-CSRF-Token': await page.evaluate(() => (window as any).csrf_token) } });
    expect(denied.status()).toBe(403);
    const response = await page.goto('/volunteering/collaboration');
    expect(response?.status()).toBe(403);
});

for (const [kind, webAllowed, appAllowed] of [['web', true, false], ['app', false, true], ['both', true, true]] as const) {
    test(`Independent ${kind} chat role controls web Home and native API`, async ({ page }) => {
        await loginViaAPI(page.request, `demo.interface.${kind}@sevamrita.local`, password);
        await page.goto('/volunteering/home');
        const home = await portalCall(page, 'volunteering.volunteering.home_service.get_home_payload');
        expect(home.flags.show_chat).toBe(webAllowed);
        expect((home.actions.collaboration || []).length > 0).toBe(webAllowed);
        const nav = page.getByRole('navigation', { name: 'Sections', exact: true });
        if (webAllowed) await expect(nav.getByText('Collaboration', { exact: true })).toBeVisible();
        else {
            await expect(nav.getByText('Collaboration', { exact: true })).toHaveCount(0);
            await expect(nav.getByRole('link', { name: 'Profile', exact: true })).toBeVisible();
            expect(home.waiting.every((row: any) => !row.route.startsWith('/volunteering/collaboration'))).toBeTruthy();
        }
        const csrf = await page.evaluate(() => (window as any).csrf_token);
        const headers = { 'X-Frappe-CSRF-Token': csrf, 'X-Sevamrita-Client': 'app' };
        const native = await page.request.post('/api/method/volunteering.volunteering.collaboration_mobile.get_collaboration_home', { headers });
        expect(native.status()).toBe(appAllowed ? 200 : 403);
        const web = await page.request.post('/api/method/' + API + 'get_collaboration_home', { headers });
        expect(web.status()).toBe(webAllowed ? 200 : 403);
        const direct = await page.goto('/volunteering/collaboration');
        expect(direct?.status()).toBe(webAllowed ? 200 : 403);
    });
}

test('Create workspace and membership; send a message with a private attachment and reply', async ({ page }) => {
    await signIn(page);
    const room = await newRoom(page, true);
    await page.getByLabel('Message', { exact: true }).fill('The utensils delivery is confirmed.');
    await page.locator('.attachment-picker input').setInputFiles({ name: 'delivery.txt', mimeType: 'text/plain', buffer: Buffer.from('Delivery note: 200 spoons') });
    const saved = page.waitForResponse(r => r.url().endsWith(API + 'send_message'));
    await page.getByRole('button', { name: 'Send message', exact: true }).click();
    expect((await saved).status()).toBe(200);
    const entry = page.locator('.message').filter({ has: page.locator('.message-text').filter({ hasText: 'The utensils delivery is confirmed.' }) });
    await expect(entry.getByRole('link', { name: /delivery.*\.txt/ })).toBeVisible();
    const fileUrl = await entry.getByRole('link', { name: /delivery.*\.txt/ }).getAttribute('href');
    expect(fileUrl).toMatch(/^\/private\/files\//);
    expect((await page.request.get(fileUrl!)).status()).toBe(200);
    await entry.locator('summary').click();
    await entry.getByRole('button', { name: 'Reply', exact: true }).click();
    await page.getByLabel('Message', { exact: true }).fill('Thank you. Please upload the confirmation.');
    await page.getByRole('button', { name: 'Send message', exact: true }).click();
    await expect(page.locator('.reply-label')).toContainText('Linked');
    await signIn(page, 'viewer', `/volunteering/collaboration?space=${room.name}`);
    await expect(page.locator('.read-only')).toContainText('viewing access');
    await expect(page.getByRole('button', { name: 'Send message', exact: true })).toHaveCount(0);
    expect((await page.request.get(fileUrl!)).status()).toBe(200);
});

test('Opening the web conversation updates message info for the native sender', async ({ page, browser }) => {
    await signIn(page);
    const room = await newRoom(page, true);
    const native = 'volunteering.volunteering.collaboration_mobile.';
    const entry = await portalCall(page, native + 'post_entry', {
        space: room.name, body: 'Receipt check from SF Tasks', request_key: `receipt-${Date.now()}`
    });
    const recipientPage = await browser.newPage({ baseURL: new URL(page.url()).origin });
    try {
        await recipientPage.bringToFront();
        const seen = recipientPage.waitForResponse(response => response.url().endsWith(API + 'mark_seen') &&
            response.request().postDataJSON().entry === entry.name);
        await signIn(recipientPage, 'member', `/volunteering/collaboration?space=${room.name}`);
        await expect(recipientPage.locator('.message-text')).toContainText('Receipt check from SF Tasks');
        expect((await seen).ok()).toBeTruthy();
    } finally {
        await recipientPage.close();
    }
    const info = await portalCall(page, native + 'get_message_info', { name: entry.name });
    expect(info.recipients).toEqual(expect.arrayContaining([
        expect.objectContaining({ user: users.member, status: 3 }),
        expect.objectContaining({ user: users.viewer, status: 1 }),
    ]));
});

test('Task from a message keeps its link, dates, recurrence and completion history', async ({ page }) => {
    await signIn(page); await newRoom(page);
    await page.getByLabel('Message', { exact: true }).fill('Confirm kitchen supplies');
    await page.getByRole('button', { name: 'Send message', exact: true }).click();
    const entry = page.locator('.message').filter({ hasText: 'Confirm kitchen supplies' });
    await entry.locator('summary').click();
    await entry.getByRole('button', { name: 'Create task', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Create work item' });
    await dialog.getByLabel('From date').fill('2026-11-02');
    await dialog.getByLabel('Until date').fill('2026-11-04');
    await dialog.getByLabel('Repeat', { exact: true }).selectOption('Weekly');
    const item = await saveItem(page);
    expect(item.source_entry).toBeTruthy();
    await page.getByRole('button', { name: /^Tasks/ }).click();
    const card = page.locator('.work-body .item-card').filter({ hasText: 'Confirm kitchen supplies' });
    await card.getByRole('button', { name: 'Complete', exact: true }).click();
    await expect(page.locator('.work-body .item-card')).toHaveCount(2);
    await expect(page.locator('.work-body .item-card').filter({ hasText: 'Completed' })).toHaveCount(1);
    await page.locator('.work-body .item-card').filter({ hasText: 'Completed' }).getByRole('button', { name: 'History', exact: true }).click();
    await expect(page.getByRole('dialog', { name: 'Activity history' })).toContainText('complete');
});

test('Shared list supports nested entries and another member updating it', async ({ page }) => {
    await signIn(page); const room = await newRoom(page, true);
    const dialog = await createItem(page, 'List', 'Kitchen supplies');
    await dialog.getByRole('button', { name: '+ Add list entry', exact: true }).click();
    await dialog.getByLabel('List entry 1', { exact: true }).fill('Utensils');
    await dialog.getByRole('button', { name: '+ Add list entry', exact: true }).click();
    await dialog.getByLabel('List entry 2', { exact: true }).fill('Spoons');
    await dialog.getByLabel('Parent of list entry 2').selectOption({ label: 'Utensils' });
    await saveItem(page);
    await signIn(page, 'member', `/volunteering/collaboration?space=${room.name}`);
    await page.getByRole('button', { name: /^Lists/ }).click();
    await page.locator('.work-body .item-card').getByRole('button', { name: 'Edit', exact: true }).click();
    await page.getByLabel('Complete list entry 2').check();
    await saveItem(page);
    await expect(page.locator('.work-body .checklist-preview')).toContainText('☑ Spoons');
});

test('Task snooze uses a date picker and preserves its action window', async ({ page }) => {
    await signIn(page); await newRoom(page);
    const dialog = await createItem(page, 'Task', 'Confirm the delivery route');
    const today = new Date();
    const day = (offset: number) => { const d = new Date(today); d.setDate(d.getDate() + offset); return d.toLocaleDateString('en-CA'); };
    await dialog.getByLabel('From date').fill(day(0));
    await dialog.getByLabel('Until date').fill(day(3));
    await saveItem(page);
    await page.getByRole('button', { name: /^Tasks/ }).click();
    await page.locator('.work-body .item-card').getByRole('button', { name: 'Snooze / wake', exact: true }).click();
    const schedule = page.getByRole('dialog', { name: 'Snooze task', exact: true });
    await schedule.getByLabel('Snooze until', { exact: true }).fill(day(1));
    await schedule.getByRole('button', { name: 'Save schedule', exact: true }).click();
    await expect(page.locator('.work-body .item-meta')).toContainText(`Snoozed until ${day(1)}`);
});

test('Weighted stages, dated progress snapshots and history work through the UI', async ({ page }) => {
    await signIn(page); await newRoom(page);
    const dialog = await createItem(page, 'Tracker', 'Meal service preparation');
    await dialog.getByLabel('Tracking scale').selectOption('Stages');
    for (const [index, label, position] of [[1, 'Plan agreed', '20'], [2, 'Meals served', '100']] as const) {
        await dialog.getByRole('button', { name: '+ Add stage', exact: true }).click();
        await dialog.getByLabel(`Stage ${index} label`).fill(label);
        await dialog.getByLabel(`Stage ${index} percent`).fill(position);
    }
    await dialog.getByLabel('Next action', { exact: true }).fill('Confirm the menu');
    await saveItem(page);
    await page.getByRole('button', { name: /^Progress/ }).click();
    await page.locator('.work-body .item-card').getByRole('button', { name: 'Update progress', exact: true }).click();
    const progress = page.getByRole('dialog', { name: 'Record progress', exact: true });
    await progress.getByRole('button', { name: /Plan agreed/ }).click();
    await progress.getByLabel('Progress note', { exact: true }).fill('The menu and timings are agreed.');
    await progress.getByRole('button', { name: 'Post progress update', exact: true }).click();
    await expect(page.locator('.work-body .tracker-value')).toHaveText('Plan agreed');
    await page.locator('.work-body .item-card').getByRole('button', { name: 'Configure', exact: true }).click();
    await expect(page.getByRole('dialog', { name: 'Edit work item' }).getByLabel('Title', { exact: true })).toHaveValue('Meal service preparation');
    await page.getByRole('button', { name: 'Close dialog', exact: true }).click();
    await page.getByRole('button', { name: 'Chat', exact: true }).click();
    await expect(page.locator('.snapshot')).toContainText('Plan agreed');
    await page.screenshot({ path: 'test-results/collaboration-desktop.png', fullPage: true });
});

test('Create event and find it on the workspace calendar', async ({ page }) => {
    await signIn(page); await newRoom(page);
    const dialog = await createItem(page, 'Event', 'Kitchen coordination call');
    const today = new Date().toLocaleDateString('en-CA');
    await dialog.getByLabel('Starts', { exact: true }).fill(`${today}T10:00`);
    await dialog.getByLabel('Ends', { exact: true }).fill(`${today}T10:30`);
    await dialog.getByLabel('Location', { exact: true }).fill('Pune office');
    await saveItem(page);
    await page.getByRole('button', { name: 'Calendar', exact: true }).click();
    await expect(page.locator('.calendar')).toContainText('Kitchen coordination call');
});

test('Direct messages are reused and subareas inherit membership', async ({ page }) => {
    await signIn(page); const room = await newRoom(page, true);
    await page.getByRole('button', { name: '+ Subarea', exact: true }).click();
    await page.getByRole('dialog').getByLabel('Name', { exact: true }).fill('Distribution route');
    await page.getByRole('dialog').getByRole('button', { name: 'Save conversation' }).click();
    await expect(page.locator('.room-header h2')).toHaveText('Distribution route');
    const areaName = new URL(page.url()).searchParams.get('space');
    await signIn(page, 'member', `/volunteering/collaboration?space=${areaName}`);
    await expect(page.locator('.room-header')).toContainText('Member');
    await expect(page.getByRole('button', { name: '+ Subarea', exact: true })).toHaveCount(0);
    await signIn(page);
    const first = await portalCall(page, API + 'start_direct', { user: users.member });
    const second = await portalCall(page, API + 'start_direct', { user: users.member });
    expect(first.name).toBe(second.name);
    expect(room.name).not.toBe(first.name);
});

test('Leaving a workspace removes known-message and attachment access', async ({ page }) => {
    await signIn(page); const room = await newRoom(page, true);
    const entry = await portalCall(page, API + 'send_message', { payload: { space: room.name, body: 'Private delivery', request_key: `file-${Date.now()}`, attachments: [{ filename: 'route.txt', content: Buffer.from('Private route').toString('base64') }] } });
    const payload = await portalCall(page, API + 'get_space', { name: room.name });
    const url = payload.entries.find((e: any) => e.name === entry.name).attachments[0].file_url;
    await portalCall(page, API + 'save_space', { name: room.name, expected_modified: payload.space.modified, payload: { members: [{ user: users.owner, access_level: 'Owner' }] } });
    await signIn(page, 'member');
    const csrf = await page.evaluate(() => (window as any).csrf_token);
    expect((await page.request.post(`/api/method/${API}get_space`, { headers: { 'X-Frappe-CSRF-Token': csrf }, data: { name: room.name } })).status()).toBe(403);
    expect((await page.request.get(url)).status()).toBe(403);
});

for (const width of [360, 390]) test(`Phone layout ${width}px opens chat and creates work without horizontal overflow`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await signIn(page);
    await page.locator('.space-link').filter({ hasText: 'Pune Community Kitchen' }).click();
    await expect(page.locator('.room-header h2')).toHaveText('Pune Community Kitchen');
    await page.getByRole('button', { name: /^Tasks/ }).click();
    await page.getByRole('button', { name: '+ Task', exact: true }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
    await page.getByRole('button', { name: 'Close dialog', exact: true }).click();
    await page.locator('.mobile-back').click();
    await expect(page.locator('.space-link').first()).toBeVisible();
    await page.screenshot({ path: `test-results/collaboration-mobile-${width}.png`, fullPage: true });
});


test('Divide tracker stages between people and retain its reminder time', async ({ page }) => {
    await signIn(page); const room = await newRoom(page, true);
    const dialog = await createItem(page, 'Tracker', 'Kitchen stage responsibilities');
    await expect(dialog.getByLabel('Tracking scale')).toHaveValue('Status');
    await expect(dialog.getByLabel('Stage 1 label', { exact: true })).toHaveCount(0);
    await dialog.getByRole('radio', { name: /Divide by stage/ }).check();
    await dialog.getByLabel('Tracking scale').selectOption('Stages');
    for (const [index, label, position] of [[1, 'Confirm menu', '10'], [2, 'Prepare meals', '60'], [3, 'Deliver meals', '100']] as const) {
        await dialog.getByRole('button', { name: '+ Add stage', exact: true }).click();
        await dialog.getByLabel(`Stage ${index} label`).fill(label);
        await dialog.getByLabel(`Stage ${index} percent`).fill(position);
    }
    await dialog.getByLabel('Stage 1 person').selectOption(users.owner);
    await dialog.getByLabel('Stage 2 person').selectOption(users.member);
    await dialog.getByLabel('Stage 3 person').selectOption(users.owner);
    await dialog.getByLabel('Reminder time (optional)').fill('10:15');
    const tracker = await saveItem(page);
    expect(tracker.assignee).toBeFalsy();
    expect(tracker.item_data.assignment_mode).toBe('Stages');
    expect(tracker.item_data.stages[1].assignee).toBe(users.member);
    expect(tracker.item_data.reminder_time).toBe('10:15');
    await page.getByRole('button', { name: /^Progress/ }).click();
    const card = page.locator('.work-body .item-card').filter({hasText: 'Kitchen stage responsibilities'});
    await expect(card).toContainText('Arjun Sharma');
    await expect(card).toContainText('Ravi Menon');
    await page.screenshot({path:'output/collaboration-stage-assignment-web.png', fullPage:true});
});

test('Share a single task with a non-member, then allow status updates without granting chat access', async ({ page }) => {
    await signIn(page); const room = await newRoom(page);
    const title = `Shared procurement follow-up ${Date.now()}`;
    await createItem(page, 'Task', title);
    let task = await saveItem(page);
    await page.getByRole('button', { name: /^Tasks/ }).click();
    let card = page.locator('.work-body .item-card').filter({hasText:title});
    await card.getByRole('button', {name:'Share',exact:true}).click();
    let dialog = page.getByRole('dialog', {name:'Share task',exact:true});
    await dialog.getByLabel('Find person',{exact:true}).fill(users.member);
    await dialog.getByRole('button',{name:'Add person',exact:true}).click();
    await dialog.getByRole('button',{name:'Save sharing',exact:true}).click();
    await expect(dialog).toHaveCount(0);
    await signIn(page,'member');
    const detail = await portalCall(page,API+'get_work_item',{name:task.name});
    expect(detail.item_only).toBeTruthy(); expect(detail.items[0].can_update).toBeFalsy();
    const denied=await page.request.post('/api/method/'+API+'get_space',{data:{name:room.name},headers:{'X-Frappe-CSRF-Token':await page.evaluate(()=>(window as any).csrf_token)}});
    expect(denied.status()).toBe(403);
    await page.getByRole('button',{name:'My collaboration work',exact:true}).click();
    await page.getByRole('button',{name:'Open progress',exact:true}).click();
    card=page.locator('.work-body .item-card').filter({hasText:title});
    await expect(card).toBeVisible(); await expect(card.getByRole('button',{name:'In progress',exact:true})).toHaveCount(0);
    await signIn(page,'owner',`/volunteering/collaboration?space=${room.name}`);
    task=(await portalCall(page,API+'get_space',{name:room.name})).items.find((i:any)=>i.name===task.name);
    task=await portalCall(page,API+'share_item',{name:task.name,expected_modified:task.modified,shares:[{user:users.member,access:'Update'}]});
    await signIn(page,'member');
    const changed=await portalCall(page,API+'update_task',{name:task.name,expected_modified:task.modified,action:'start'});
    expect(changed.status).toBe('In progress');
});


test('Tracker files upload independently, attach to progress, and remain private for viewers and signed-out users', async ({ page, browser }) => {
    await signIn(page); const room = await newRoom(page, true);
    const create = await createItem(page, 'Tracker', 'Kitchen handover evidence');
    await create.getByLabel('Tracking scale').selectOption('Percentage');
    const tracker = await saveItem(page);
    await page.getByRole('button', {name: /^Progress/}).click();
    const card = page.locator('.work-body .item-card').filter({hasText: tracker.title});
    await card.getByRole('button', {name: 'Files', exact: true}).click();
    const dialog = page.getByRole('dialog', {name: 'Tracker files', exact: true});
    await expect(dialog.getByText('No files have been added yet.')).toBeVisible();
    await dialog.getByLabel('Note (optional)', {exact: true}).fill('Quotation approved by the kitchen team');
    await dialog.getByLabel('Tracker attachments', {exact: true}).setInputFiles({name:'quotation.txt', mimeType:'text/plain', buffer:Buffer.from('Private quotation for kitchen supplies')});
    await expect(dialog.getByRole('button', {name: 'Remove quotation.txt'})).toBeVisible();
    const added = page.waitForResponse(r => r.url().endsWith(API+'add_tracker_files'));
    await dialog.getByRole('button', {name:'Upload files', exact:true}).click();
    expect((await added).ok()).toBeTruthy();
    const link = dialog.getByRole('link').filter({hasText: /quotation[0-9a-f]*\.txt/});
    await expect(link).toBeVisible();
    const fileUrl = await link.getAttribute('href');
    expect(fileUrl).toMatch(/^\/private\/files\//);
    const file = await page.request.get(fileUrl!);
    expect(file.status()).toBe(200);
    expect(await file.text()).toContain('Private quotation for kitchen supplies');
    const read = await portalCall(page, API+'get_work_item', {name:tracker.name});
    expect(read.items[0].item_data).toEqual(tracker.item_data);
    expect(read.items[0].current_effective_at).toEqual(tracker.current_effective_at);
    await expect(dialog.getByRole('button',{name:'Close dialog',exact:true})).toBeEnabled();
    await page.screenshot({path:'output/tracker-files-desktop.png', fullPage:true});
    await dialog.getByRole('button',{name:'Close dialog',exact:true}).click();
    await expect(dialog).toHaveCount(0);
    await card.getByRole('button',{name:'Update progress',exact:true}).click();
    const progress = page.getByRole('dialog',{name:'Record progress',exact:true});
    await progress.getByLabel('Progress note',{exact:true}).fill('Goods received with a signed delivery note');
    await progress.getByLabel('Tracker attachments',{exact:true}).setInputFiles({name:'delivery.txt', mimeType:'text/plain', buffer:Buffer.from('Signed delivery note: utensils received')});
    const saved = page.waitForResponse(r => r.url().endsWith(API+'record_progress'));
    await progress.getByRole('button',{name:'Post progress update',exact:true}).click();
    expect((await saved).ok()).toBeTruthy();
    await card.getByRole('button',{name:'Files',exact:true}).click();
    await expect(dialog.getByRole('link').filter({hasText:/delivery[0-9a-f]*\.txt/})).toBeVisible();
    await signIn(page, 'viewer', `/volunteering/collaboration?space=${room.name}`);
    await page.getByRole('button',{name:/^Progress/}).click();
    const viewCard = page.locator('.work-body .item-card').filter({hasText: tracker.title});
    await viewCard.getByRole('button',{name:'Files',exact:true}).click();
    await expect(dialog.getByRole('link').filter({hasText:/quotation[0-9a-f]*\.txt/})).toBeVisible();
    await expect(dialog.getByRole('button',{name:'Upload files',exact:true})).toHaveCount(0);
    expect((await page.request.get(fileUrl!)).status()).toBe(200);
    const outsider = await browser.newContext();
    try { expect((await outsider.request.get(new URL(fileUrl!,page.url()).toString())).status()).not.toBe(200); }
    finally {await outsider.close();}
});

test('Tracker file picker validates selections, allows removal and retains files on a stale-update error', async ({ page }) => {
    await signIn(page); await newRoom(page);
    await page.setViewportSize({width:390,height:844});
    const create=await createItem(page,'Tracker','File selection checks');
    await create.getByLabel('Tracking scale').selectOption('Percentage');
    const tracker=await saveItem(page);
    await page.getByRole('button',{name:/^Progress/}).click();
    const card=page.locator('.work-body .item-card').filter({hasText:tracker.title});
    await card.getByRole('button',{name:'Files',exact:true}).click();
    const dialog=page.getByRole('dialog',{name:'Tracker files',exact:true});
    await dialog.getByLabel('Tracker attachments',{exact:true}).setInputFiles({name:'unsafe.exe', mimeType:'application/octet-stream', buffer:Buffer.from('not allowed')});
    await expect(dialog.getByRole('alert')).toContainText('Choose a PDF');
    await expect(dialog.getByRole('button',{name:'Upload files',exact:true})).toBeDisabled();
    await dialog.getByLabel('Tracker attachments',{exact:true}).setInputFiles({name:'selection.txt',mimeType:'text/plain',buffer:Buffer.from('selected file')});
    await dialog.getByRole('button',{name:'Remove selection.txt',exact:true}).click();
    await expect(dialog.getByRole('button',{name:'Upload files',exact:true})).toBeDisabled();
    await dialog.getByLabel('Tracker attachments',{exact:true}).setInputFiles({name:'selection.txt',mimeType:'text/plain',buffer:Buffer.from('selected file')});
    await portalCall(page,API+'record_progress',{name:tracker.name,expected_modified:tracker.modified,note:'Changed in another session',value:15});
    await dialog.getByRole('button',{name:'Upload files',exact:true}).click();
    await expect(dialog).toContainText('This record changed');
    await expect(dialog.getByRole('button',{name:'Remove selection.txt',exact:true})).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
    await page.screenshot({path:'output/tracker-files-mobile.png', fullPage:true});
    const files=await portalCall(page,API+'get_tracker_files',{name:tracker.name});
    expect(files.files).toHaveLength(0);
});
