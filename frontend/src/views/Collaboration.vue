<template>
	<div class="collaboration">
		<div class="collab-heading">
			<div>
				<p class="eyebrow">COLLABORATION</p>
				<h1>Chat & workspaces</h1>
				<p class="text-muted">Conversations and the work you share.</p>
			</div>
			<button class="btn-primary" @click="newSpace()">+ New conversation</button>
		</div>
		<p v-if="error" role="alert" class="error-banner">
			{{ error }} <button @click="error = ''" aria-label="Dismiss error">×</button>
		</p>
		<p v-if="notice" role="status" class="notice-banner">{{ notice }}</p>
		<div v-if="loading" role="status" class="p-6 text-muted">Loading your conversations…</div>
		<div v-else-if="home" class="collab-layout" :class="{ 'room-open': roomId || personal }">
			<aside class="spaces-pane" aria-label="Your conversations">
				<button class="my-work" :class="{ selected: personal }" @click="openPersonal()">
					<Icon name="check" /> My collaboration work
				</button>
				<label class="sr-only" for="space-search">Find a conversation</label
				><input
					id="space-search"
					v-model="search"
					class="field-input my-3"
					placeholder="Find a person, group or workspace"
				/>
				<label class="text-xs text-muted flex gap-2 mb-3"
					><input type="checkbox" v-model="includeArchived" /> Include archived
					workspaces</label
				>
				<div v-for="group in grouped" :key="group.kind" class="space-group">
					<h2>{{ group.label }}</h2>
					<div
						v-for="row in group.rows"
						:key="row.name"
						class="space-nav-row"
						:style="{ '--depth': row.depth }"
					>
						<button
							v-if="children(row).length"
							class="expand-area"
							:aria-label="`${collapsed.has(row.name) ? 'Expand' : 'Collapse'} ${row.title}`"
							@click="toggleArea(row.name)"
						>
							{{ collapsed.has(row.name) ? "›" : "⌄" }}
						</button>
						<button
							class="space-link"
							:class="{ selected: row.name === roomId }"
							@click="openRoom(row.name)"
						>
							<span class="avatar">{{ initials(row.title) }}</span
							><span class="min-w-0 flex-1"
								><strong>{{ row.title }}</strong
								><small>{{
									row.archived
										? "Archived"
										: row.last_entry?.body || "Start the conversation"
								}}</small></span
							><span v-if="row.unread" class="unread">{{ row.unread }}</span>
						</button>
					</div>
				</div>
				<p v-if="!home.spaces.length" class="text-sm text-muted p-3">
					Start a direct chat or create a shared workspace.
				</p>
			</aside>
			<section class="conversation-pane" aria-label="Conversation workspace">
				<template v-if="personal">
					<div class="room-header">
						<button class="mobile-back" @click="closeRoom()">← Conversations</button>
						<h2>My collaboration work</h2>
						<input
							v-model="workDate"
							type="date"
							aria-label="Work date"
							class="field-input w-auto"
							@change="loadWork"
						/>
					</div>
					<div class="room-tabs">
						<button
							v-for="value in ['Today', 'Open progress', 'Calendar']"
							:key="value"
							:class="{ active: personalTab === value }"
							@click="personalTab = value"
						>
							{{ value }}
						</button>
					</div>
					<div class="work-body">
						<template v-if="personalTab !== 'Calendar'"
							><p class="text-sm text-muted mb-4">
								Only your assigned actions and your trackers appear here. Due and
								overdue actions are reminders; unscheduled work stays in Open
								progress.
							</p>
							<div v-for="item in personalItems" :key="item.name" class="work-card">
								<button class="text-accent text-xs" @click="viewWorkItem(item)">
									{{ item.space_title }}</button
								><ItemCard
									:item="item"
									@edit="editItem(item)"
									@action="taskAction(item, $event)"
									@progress="openProgress(item)"
									@history="showHistory(item)"
                                    @share="shareItem(item)" @files="openTrackerFiles(item)"
								/>
							</div>
							<p v-if="!personalItems.length" class="empty-state">
								Nothing in this view.
							</p></template
						><CalendarView
							v-else
							:items="work.calendar || []"
							@open="openRoom($event.space)"
						/>
					</div>
				</template>
				<template v-else-if="room">
					<div class="room-header">
						<button class="mobile-back" @click="closeRoom()">← Conversations</button>
						<div class="min-w-0 flex-1">
							<p class="eyebrow">
								{{ room.space.space_kind }} · {{ room.space.access_level }}
							</p>
							<h2>{{ room.space.title }}</h2>
							<p class="text-xs text-muted">
								{{ room.space.members.length }} members<span
									v-if="room.space.project"
								>
									· Project {{ room.space.project }}</span
								><span v-if="room.space.archived"> · Archived</span>
							</p>
						</div>
						<button
							v-if="room.space.can_manage"
							class="btn-secondary"
							@click="editSpace()"
						>
							Members & settings</button
						><button
							v-if="room.space.can_manage && !room.space.archived"
							class="btn-secondary"
							@click="newSpace(roomId)"
						>
							+ Subarea
						</button>
					</div>
					<div class="room-tabs" aria-label="Workspace views">
						<button
							v-for="value in tabs"
							:key="value"
							:class="{ active: tab === value }"
							@click="tab = value"
						>
							{{ value }}
							<span v-if="value !== 'Chat' && value !== 'Calendar'">{{
								filteredKind(value).length
							}}</span></button
						><button v-if="room.space.can_post" class="new-work" @click="newItem()">
							+ Create
						</button>
					</div>
					<template v-if="tab === 'Chat'">
						<div
							ref="thread"
							class="message-thread"
							aria-label="Message history"
							@scroll="acknowledgeVisibleMessages"
						>
							<button
								v-if="room.older_cursor"
								class="btn-secondary mx-auto block mb-5"
								@click="olderMessages"
							>
								Load older messages
							</button>
							<p v-if="!room.entries.length" class="empty-state">
								Start a conversation. You can create tasks, events, lists and
								trackers from any message.
							</p>
							<article
								v-for="entry in room.entries"
								:key="entry.name"
								class="message"
								:class="{
									mine: entry.owner === home.user,
									system: entry.entry_kind === 'System',
								}"
								:data-entry="entry.name"
							>
								<div class="message-meta">
									<strong>{{ entry.author_name }}</strong
									><span>{{ dateTime(entry.creation) }}</span
									><span v-if="entry.entry_kind !== 'Message'">{{
										entry.entry_kind
									}}</span
									><span v-if="entry.edited_at">edited</span>
								</div>
								<p v-if="entry.source_entry" class="reply-label">
									↳ Linked to an earlier message
								</p>
								<p class="message-text">{{ entry.body }}</p>
								<div v-if="entry.snapshot?.item_data" class="snapshot">
									<span
										>{{ entry.snapshot.title }} ·
										{{ trackerLabel({ item_data: entry.snapshot.item_data }) }}
										· {{ entry.snapshot.status }}</span
									><small
										>Recorded
										{{ dateTime(entry.snapshot.effective_at) }}</small
									>
								</div>
								<a
									v-for="file in entry.attachments"
									:key="file.name"
									:href="file.file_url"
									target="_blank"
									rel="noopener"
									class="file-link"
									>📎 {{ file.file_name }}</a
								>
								<div
									v-for="item in linkedItems(entry)"
									:key="item.name"
									class="linked-item"
								>
									<ItemCard
										:item="item"
										@edit="editItem(item)"
										@action="taskAction(item, $event)"
										@progress="openProgress(item)"
										@history="showHistory(item)"
                                    @share="shareItem(item)" @files="openTrackerFiles(item)"
									/>
								</div>
								<details
									v-if="room.space.can_post && !entry.is_deleted"
									class="message-options"
								>
									<summary>Actions</summary>
									<button @click="reply = entry">Reply</button
									><button
										v-for="kind in kinds"
										:key="kind"
										@click="newItem(kind, entry)"
									>
										Create {{ kind.toLowerCase() }}</button
									><button v-if="entry.can_edit" @click="editMessage(entry)">
										Edit message</button
									><button v-if="entry.can_remove" @click="removeMessage(entry)">
										Remove message
									</button>
								</details>
							</article>
						</div>
						<form v-if="room.space.can_post" class="composer" @submit.prevent="send">
							<div v-if="reply" class="reply-preview">
								Replying to {{ reply.author_name }}: {{ reply.body.slice(0, 100) }}
								<button type="button" @click="reply = null">×</button>
							</div>
							<div class="composer-top">
								<select v-model="entryKind" aria-label="Entry type">
									<option
										v-for="kind in [
											'Message',
											'Note',
											'Decision',
											'Blocker',
											'Milestone',
										]"
										:key="kind"
									>
										{{ kind }}
									</option></select
								><label class="attachment-picker"
									>📎 Attach<input
										ref="fileInput"
										type="file"
										multiple
										accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.csv,.docx,.xlsx"
										@change="chooseFiles" /></label
								><span v-if="files.length" class="text-xs text-muted">{{
									files.map((f) => f.name).join(", ")
								}}</span>
							</div>
							<label class="sr-only" for="chat-compose">Message</label
							><textarea
								id="chat-compose"
								v-model="draft"
								rows="3"
								placeholder="Write a message, decision or update…"
								maxlength="12000"
								@keydown.ctrl.enter.prevent="send"
							/>
							<div class="flex justify-between items-center">
								<span class="text-xs text-muted"
									>Private to this conversation · Ctrl+Enter to send</span
								><button class="btn-primary" :disabled="busy || !draft.trim()">
									{{ busy ? "Sending…" : "Send message" }}
								</button>
							</div>
						</form>
						<p v-else class="read-only">
							{{
								room.space.archived
									? "This workspace is archived."
									: "You have viewing access to this conversation."
							}}
						</p>
					</template>
					<div v-else class="work-body">
						<CalendarView
							v-if="tab === 'Calendar'"
							:items="room.items"
							@open="editItem"
						/><template v-else
							><div class="flex justify-between items-center mb-4">
								<p class="text-sm text-muted">
									{{
										tab === "Progress"
											? "Trackers are independent of task completion."
											: "Shared work for this conversation."
									}}
								</p>
								<button
									v-if="room.space.can_post"
									class="btn-primary"
									@click="newItem(tabKind(tab))"
								>
									+ {{ tabKind(tab) }}
								</button>
							</div>
							<div
								v-for="item in filteredKind(tab)"
								:key="item.name"
								class="work-card"
							>
								<ItemCard
									:item="item"
									@edit="editItem(item)"
									@action="taskAction(item, $event)"
									@progress="openProgress(item)"
									@history="showHistory(item)"
                                    @share="shareItem(item)" @files="openTrackerFiles(item)"
								/>
							</div>
							<p v-if="!filteredKind(tab).length" class="empty-state">
								No {{ tab.toLowerCase() }} yet.
							</p></template
						>
					</div>
				</template>
				<div v-else class="welcome-panel">
					<span class="welcome-symbol">✦</span>
					<h2>A place to work together</h2>
					<p>
						Open a conversation or create a workspace for your team. Keep decisions,
						tasks and progress connected.
					</p>
					<button class="btn-primary" @click="newSpace()">Start a conversation</button>
				</div>
			</section>
		</div>
		<div v-if="dialog" class="dialog-backdrop" @click.self="closeDialog">
			<section
				class="collab-dialog"
				role="dialog"
				aria-modal="true"
				:aria-label="dialogTitle"
			>
				<div class="dialog-header">
					<h2>{{ dialogTitle }}</h2>
					<button aria-label="Close dialog" :disabled="busy" @click="closeDialog">×</button>
				</div>
				<p v-if="dialogError" role="alert" class="error-banner">{{ dialogError }}</p>
				<form v-if="dialog === 'space'" @submit.prevent="saveSpace">
					<div class="dialog-body">
						<label v-if="!spaceForm.name && !spaceForm.parent_space"
							>Conversation type<select
								aria-label="Conversation type"
								v-model="spaceForm.space_kind"
							>
								<option>Workspace</option>
								<option>Group</option>
								<option>Direct</option>
							</select></label
						><template v-if="spaceForm.space_kind === 'Direct'"
							><label
								>Person<select
									aria-label="Person"
									v-model="spaceForm.person"
									required
								>
									<option value="">Choose a chat user</option>
									<option
										v-for="user in directory.filter(
											(u) => u.name !== home.user,
										)"
										:key="user.name"
										:value="user.name"
									>
										{{ user.full_name }} · {{ user.name }}
									</option>
								</select></label
							></template
						><template v-else
							><label
								>Name<input
									v-model="spaceForm.title"
									required
									maxlength="160"
									placeholder="e.g. Pune food distribution" /></label
							><label v-if="!spaceForm.parent_space"
								>Linked ERP project (optional)<select
									aria-label="Linked ERP project (optional)"
									v-model="spaceForm.project"
								>
									<option value="">Independent workspace</option>
									<option
										v-for="project in home.projects"
										:key="project.name"
										:value="project.name"
									>
										{{ project.project_name }}
									</option></select
								><small
									>Linking does not give members access to project
									finances.</small
								></label
							>
							<div v-if="!spaceForm.parent_space">
								<h3 class="font-semibold mt-2">Members</h3>
								<p class="text-xs text-muted">
									Owners manage the workspace. Managers manage members. Members
									contribute. Viewers read only.
								</p>
								<div
									v-for="(member, index) in spaceForm.members"
									:key="member.user"
									class="member-row"
								>
									<span>{{ personName(member.user) }}</span
									><select
										v-model="member.access_level"
										:aria-label="`Access for ${personName(member.user)}`"
									>
										<option
											v-for="level in [
												'Owner',
												'Manager',
												'Member',
												'Viewer',
											]"
											:key="level"
										>
											{{ level }}
										</option></select
									><button
										type="button"
										aria-label="Remove member"
										@click="spaceForm.members.splice(index, 1)"
									>
										×
									</button>
								</div>
								<label
									>Add person<select aria-label="Add person" v-model="addPerson">
										<option value="">Select a chat user</option>
										<option
											v-for="user in directory.filter(
												(u) =>
													!spaceForm.members.some(
														(m) => m.user === u.name,
													),
											)"
											:key="user.name"
											:value="user.name"
										>
											{{ user.full_name }} · {{ user.name }}
										</option>
									</select></label
								><button
									type="button"
									class="btn-secondary"
									:disabled="!addPerson"
									@click="
										spaceForm.members.push({
											user: addPerson,
											access_level: 'Member',
										});
										addPerson = '';
									"
								>
									Add member
								</button>
							</div>
							<p v-else class="text-sm text-muted">
								This area inherits its workspace's members and their access levels.
							</p>
							<label
								v-if="spaceForm.name && room?.space.access_level === 'Owner'"
								class="check-label"
								><input type="checkbox" v-model="spaceForm.archived" /> Archive
								workspace</label
							></template
						>
					</div>
					<div class="dialog-footer">
						<button class="btn-primary" :disabled="busy">
							{{ busy ? "Saving…" : "Save conversation" }}
						</button>
					</div>
				</form>
				<form v-else-if="dialog === 'item'" @submit.prevent="saveItem">
					<div class="dialog-body">
						<label
							>Type<select
								aria-label="Type"
								v-model="itemForm.item_kind"
								:disabled="!!itemForm.name"
							>
								<option v-for="kind in kinds" :key="kind">{{ kind }}</option>
							</select></label
						><label
							>Title<input
								v-model="itemForm.title"
								required
								maxlength="160" /></label
						><label
							>Description<textarea
								v-model="itemForm.description"
								rows="3"
								maxlength="12000"
							/></label
						><fieldset v-if="itemForm.item_kind === 'Tracker'" class="assignment-choice">
                            <legend>Who is responsible?</legend>
                            <label><input type="radio" v-model="trackerForm.assignment_mode" value="Single" @change="assignmentChanged" />
                                <span><strong>One person</strong><small>Assign the entire tracker to one person.</small></span></label>
                            <label><input type="radio" v-model="trackerForm.assignment_mode" value="Stages" @change="assignmentChanged" />
                                <span><strong>Divide by stage</strong><small>Choose a responsible person for each stage.</small></span></label>
                        </fieldset><label v-if="itemForm.item_kind === 'Task' || itemForm.item_kind === 'Tracker' && trackerForm.assignment_mode !== 'Stages'"
							>Assigned to<select
								aria-label="Assigned to"
								v-model="itemForm.assignee"
							>
								<option
									v-for="member in room.space.members.filter(
										(m) => m.chat_enabled && m.access_level !== 'Viewer',
									)"
									:key="member.user"
									:value="member.user"
								>
									{{ member.full_name }}
								</option>
							</select></label
						><label
							>Priority<select aria-label="Priority" v-model="itemForm.priority">
								<option v-for="priority in priorities" :key="priority">
									{{ priority }}
								</option>
							</select></label
						>
						<template v-if="itemForm.item_kind === 'Task'">
                            <label>Reminder time (optional)<input type="time" v-model="itemForm.item_data.reminder_time" /></label>
                            <p class="text-xs text-muted">Dated work without a time reminds at 09:00 in the portal's time zone.</p><div class="field-grid">
								<label
									>From date<input
										v-model="itemForm.from_date"
										type="date" /></label
								><label
									>Until date<input
										v-model="itemForm.until_date"
										type="date" /></label
								><label
									>Deadline (optional)<input
										v-model="itemForm.deadline"
										type="date" /></label
								><label
									>Repeat<select
										aria-label="Repeat"
										v-model="itemForm.repeat_pattern"
									>
										<option>None</option>
										<option>Daily</option>
										<option>Weekly</option>
										<option>Monthly</option>
									</select></label
								><label v-if="itemForm.repeat_pattern !== 'None'"
									>Repeat until (optional)<input
										v-model="itemForm.repeat_until"
										type="date"
								/></label>
							</div>
							<p class="text-xs text-muted">
								An action window is one task. Completing or failing a repeating
								occurrence creates its next occurrence.
							</p></template
						>
						<template v-if="itemForm.item_kind === 'Event'"
							><div class="field-grid">
								<label
									>Starts<input
										v-model="itemForm.start_at"
										type="datetime-local"
										required /></label
								><label
									>Ends<input
										v-model="itemForm.end_at"
										type="datetime-local"
										required
								/></label>
							</div>
							<label>Location<input v-model="itemForm.location" /></label>
							<fieldset>
								<legend>Participants</legend>
								<label
									v-for="member in room.space.members.filter(
										(m) => m.chat_enabled && m.access_level !== 'Viewer',
									)"
									:key="member.user"
									class="check-label"
									><input
										type="checkbox"
										v-model="itemForm.participants"
										:value="member.user"
									/>{{ member.full_name }}</label
								>
							</fieldset>
							<p class="text-xs text-muted">
								Times use the portal's local time. With no participants selected,
								the event is for the whole workspace.
							</p></template
						>
						<template v-if="itemForm.item_kind === 'List'"
							><p class="text-sm text-muted">
								Create checklist entries and nest them under another entry.
								Drag-free ordering works on phone and desktop.
							</p>
							<div
								v-for="(row, index) in listRows"
								:key="row.id"
								class="list-edit-row"
							>
								<label class="check-label"
									><input
										v-model="row.completed"
										type="checkbox"
										:aria-label="`Complete list entry ${index + 1}`" /><input
										v-model="row.content"
										:aria-label="`List entry ${index + 1}`"
										placeholder="List entry"
										required /></label
								><select
									v-model="row.parent_id"
									:aria-label="`Parent of list entry ${index + 1}`"
								>
									<option value="">Top level</option>
									<option
										v-for="candidate in listRows.filter(
											(r) => r.id !== row.id,
										)"
										:key="candidate.id"
										:value="candidate.id"
									>
										{{ candidate.content || "Untitled entry" }}
									</option>
								</select>
								<div class="flex gap-2">
									<button type="button" @click="moveRow(index, -1)">↑</button
									><button type="button" @click="moveRow(index, 1)">↓</button
									><button type="button" @click="removeListRow(row.id)">
										Remove
									</button>
								</div>
							</div>
							<button
								type="button"
								class="btn-secondary"
								@click="
									listRows.push({
										id: nonce(),
										content: '',
										parent_id: '',
										completed: false,
										priority: 'Medium',
									})
								"
							>
								+ Add list entry
							</button></template
						>
						<template v-if="itemForm.item_kind === 'Tracker'"
							><label
								>Tracking scale<select
									aria-label="Tracking scale"
									v-model="trackerForm.scale"
								>
									<option v-if="trackerForm.assignment_mode !== 'Stages'">Percentage</option>
                                    <option v-if="trackerForm.assignment_mode !== 'Stages'">Number</option>
									<option>Stages</option>
									<option>Status</option>
								</select></label
							>
							<div v-if="trackerForm.scale === 'Number'" class="field-grid">
								<label
									>Minimum<input
										type="number"
										step="any"
										v-model.number="trackerForm.minimum"
										required /></label
								><label
									>Maximum<input
										type="number"
										step="any"
										v-model.number="trackerForm.maximum"
										required /></label
								><label
									>Unit<input
										v-model="trackerForm.unit"
										placeholder="e.g. meals, chapters"
								/></label>
							</div>
							<template v-if="['Stages', 'Status'].includes(trackerForm.scale)"
								><div
									v-for="(stage, index) in trackerForm.stages"
									:key="stage.key"
									class="stage-row"
                                >
									<input
										v-model="stage.label"
										:aria-label="`Stage ${index + 1} label`"
										required
										placeholder="Stage or status"
                                    /><select v-if="trackerForm.assignment_mode === 'Stages'" v-model="stage.assignee" :aria-label="`Stage ${index + 1} person`" required>
                                        <option value="">Choose responsible person</option>
                                        <option v-for="member in room.space.members.filter(m => m.chat_enabled && m.access_level !== 'Viewer')" :value="member.user" :key="member.user">{{ member.full_name }}</option>
                                    </select><input
										v-if="trackerForm.scale === 'Stages'"
										v-model.number="stage.position"
										:aria-label="`Stage ${index + 1} percent`"
										type="number"
										min="0"
										max="100"
										required
									/><button
										type="button"
										@click="trackerForm.stages.splice(index, 1)"
									>
										×
									</button>
								</div>
								<button
									type="button"
									class="btn-secondary"
									@click="
										trackerForm.stages.push({
											key: nonce(),
											label: '',
											position: 100, assignee: '',
                                        })
									"
								>
									+ Add {{ trackerForm.scale === "Stages" ? "stage" : "status" }}
								</button></template
							><label
								>Reminder time (optional)<input type="time" v-model="trackerForm.reminder_time" /></label>
                            <p class="text-xs text-muted">Without a time, reminders use 09:00 in the portal's time zone.</p><label>Next action<input
                                    v-model="trackerForm.next_action"
									maxlength="500"
							/></label>
							<div class="field-grid">
								<label
									>Attention from<input
										type="date"
										v-model="trackerForm.attention_date" /></label
								><label
									>Attention until<input
										type="date"
										v-model="trackerForm.attention_until" /></label
								><label
									>Deadline<input type="date" v-model="itemForm.deadline"
								/></label></div
						></template>
						<p v-if="itemForm.source_entry" class="text-xs text-accent">
							Linked to the message you selected.
						</p>
					</div>
					<div class="dialog-footer">
						<button class="btn-primary" :disabled="busy">
							{{ busy ? "Saving…" : "Save work item" }}
						</button>
					</div>
				</form>
                <form v-else-if="dialog === 'share'" @submit.prevent="saveSharing">
                    <div class="dialog-body">
                        <p>Chat members can already see this item. Share it with other people without adding them to the chat.</p>
                        <p class="text-xs text-muted">Recipients need Web chat access or App chat access. View only is the default.</p>
                        <div v-for="(row,index) in shareRows" :key="row.user" class="sharing-row">
                            <strong>{{ row.full_name || row.user }}</strong>
                            <select v-model="row.access" :aria-label="`Permission for ${row.full_name || row.user}`"><option value="View">Can view</option><option value="Update">Can update status / progress</option></select>
                            <button type="button" @click="shareRows.splice(index,1)">Remove access</button>
                        </div>
                        <label>Find person<input v-model="sharePerson" aria-label="Find person" list="share-people" placeholder="Type name or email" />
                            <datalist id="share-people"><option v-for="person in shareDirectory" :key="person.name" :value="person.name">{{ person.full_name }}</option></datalist></label>
                        <button class="btn-secondary" type="button" @click="addSharePerson">Add person</button>
                    </div><div class="dialog-footer"><button class="btn-primary" :disabled="busy">Save sharing</button></div>
                </form>
                <div v-else-if="dialog === 'itemView'" class="dialog-body">
                    <ItemCard :item="selectedItem" @history="showHistory(selectedItem)" @progress="openProgress(selectedItem)" @action="taskAction(selectedItem,$event)" @share="shareItem(selectedItem)" @files="openTrackerFiles(selectedItem)" />
                </div>
                <div v-else-if="dialog === 'trackerFiles'" class="dialog-body tracker-files-panel">
                    <p class="text-sm text-muted">{{ selectedItem.title }} · Files are private to conversation members.</p>
                    <p v-if="trackerFileRestricted" class="read-only">Files are available only to members of this conversation.</p>
                    <form v-if="trackerCanAdd" @submit.prevent="postTrackerFiles" class="tracker-file-upload">
                        <label>Note (optional)<textarea v-model="trackerFileNote" maxlength="12000" rows="2" :disabled="busy" /></label>
                        <TrackerFilePicker v-model="trackerFiles" :disabled="busy" />
                        <button class="btn-primary" :disabled="busy || !trackerFiles.length">{{ busy ? 'Uploading…' : 'Upload files' }}</button>
                        <p class="text-xs text-muted">Adding files keeps the current progress unchanged.</p>
                    </form>
                    <p v-if="trackerFilesLoading" role="status">Loading files…</p>
                    <p v-else-if="!trackerFileRows.length && !trackerFileRestricted" class="text-sm text-muted">No files have been added yet.</p>
                    <a v-for="file in trackerFileRows" :key="file.name" :href="file.file_url" target="_blank" rel="noopener" class="tracker-file-link">
                        <Icon name="claim" :size="22" />
                        <span><strong>{{ file.file_name }}</strong><small>{{ fileSizeLabel(file.file_size) }} · {{ file.uploaded_by_name }} · {{ dateTime(file.creation) }}</small><span v-if="file.note">{{ file.note }}</span></span>
                    </a>
                    <button v-if="trackerFileCursor" class="btn-secondary" :disabled="trackerFilesLoading" @click="loadTrackerFiles(trackerFileCursor)">Load older files</button>
                </div>
				<form v-else-if="dialog === 'progress'" @submit.prevent="postProgress">
					<div class="dialog-body">
						<p class="text-sm text-muted">
							{{ selectedItem.title }} · current: {{ trackerLabel(selectedItem) }}
						</p>
						<label
							v-if="['Percentage', 'Number'].includes(selectedItem.item_data.scale)"
							>New value<input
								type="number"
								step="any"
								v-model="progress.value"
								:min="selectedItem.item_data.minimum"
								:max="selectedItem.item_data.maximum" /></label
						><template v-else
							><div class="stage-timeline">
								<button
									v-for="stage in selectedItem.item_data.stages"
									:key="stage.key"
									type="button"
									:class="{ chosen: progress.stage === stage.key }"
									@click="progress.stage = stage.key"
								>
									<span>{{ progress.stage === stage.key ? "●" : "○" }}</span>
									{{ stage.label }}
									<small v-if="stage.position != null"
										>{{ stage.position }}%</small
									>
								</button>
							</div>
							<label
								>Status<select aria-label="Status" v-model="progress.stage">
									<option value="">Not started</option>
									<option
										v-for="stage in selectedItem.item_data.stages"
										:key="stage.key"
										:value="stage.key"
									>
										{{ stage.label }}
									</option>
								</select></label
							></template
						><label
							>Outcome<select aria-label="Outcome" v-model="progress.outcome">
								<option>Open</option>
								<option>Completed</option>
								<option>Failed</option>
							</select></label
						><label
							>Effective date and time<input
								type="datetime-local"
								v-model="progress.effective_at"
								required /></label
						><label
							>Progress note<textarea
								v-model="progress.note"
								required
								maxlength="12000"
								rows="4"
							/></label
                        ><TrackerFilePicker v-if="selectedItem.can_add_files" v-model="trackerFiles" :disabled="busy" />
                        <label>Next action<input v-model="progress.next_action" /></label>
						<div class="field-grid">
							<label
								>Attention from<input
									v-model="progress.attention_date"
									type="date" /></label
							><label
								>Attention until<input
									v-model="progress.attention_until"
									type="date"
							/></label>
						</div>
						<p class="text-xs text-muted">
							Posting keeps a dated snapshot in chat. A backdated update does not
							replace newer progress.
						</p>
					</div>
					<div class="dialog-footer">
						<button class="btn-primary" :disabled="busy">Post progress update</button>
					</div>
				</form>
				<form v-else-if="dialog === 'schedule'" @submit.prevent="saveSchedule">
					<div class="dialog-body">
						<p>{{ selectedItem.title }}</p>
						<p class="text-sm text-muted">
							{{
								schedule.action === "snooze"
									? "Choose a date within the action window. Wake now removes the snooze."
									: "Choose a later start. The action window moves with it; the deadline stays unchanged."
							}}
						</p>
						<label
							>{{ schedule.action === "snooze" ? "Snooze until" : "New start date"
							}}<input
								type="date"
								v-model="schedule.date"
								:required="schedule.action === 'postpone'"
						/></label>
						<button
							v-if="schedule.action === 'snooze'"
							type="button"
							class="btn-secondary"
							@click="schedule.date = ''"
						>
							Wake now
						</button>
					</div>
					<div class="dialog-footer">
						<button class="btn-primary" :disabled="busy">Save schedule</button>
					</div>
				</form>
				<form v-else-if="dialog === 'message'" @submit.prevent="saveMessage">
					<div class="dialog-body">
						<label
							>Message<textarea
								v-model="messageEdit"
								rows="6"
								required
								maxlength="12000"
							/>
						</label>
					</div>
					<div class="dialog-footer">
						<button class="btn-primary" :disabled="busy">Save message</button>
					</div>
				</form>
				<div v-else-if="dialog === 'history'" class="dialog-body">
					<article v-for="entry in history" :key="entry.name" class="history-row">
						<p>{{ entry.body }}</p>
						<small
							>{{ entry.author_name }} ·
							{{ dateTime(entry.snapshot?.effective_at || entry.creation) }}</small
						>
                        <a v-for="file in entry.attachments" :key="file.name || file.file_url" :href="file.file_url" target="_blank" rel="noopener" class="tracker-history-file">{{ file.file_name }}</a>
						<p v-if="entry.snapshot?.item_data" class="text-accent">
							{{ trackerLabel({ item_data: entry.snapshot.item_data }) }} ·
							{{ entry.snapshot.status }}
						</p>
					</article>
				</div>
			</section>
		</div>
	</div>
</template>

<script setup>
import { computed, defineComponent, h, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { call } from "../lib/frappe";
import Icon from "../components/Icon.vue";
import TrackerFilePicker from "../components/TrackerFilePicker.vue";
const API = "volunteering.volunteering.collaboration.";
const route = useRoute(),
	router = useRouter();
const home = ref(null),
	room = ref(null),
	work = ref({}),
	loading = ref(true),
	busy = ref(false),
	error = ref(""),
	notice = ref("");
const roomId = computed(() => String(route.query.space || "")),
	personal = computed(() => route.query.view === "work");
const search = ref(""),
	includeArchived = ref(false),
	collapsed = ref(new Set()),
	tab = ref("Chat"),
	personalTab = ref("Today"),
	workDate = ref(new Date().toLocaleDateString("en-CA"));
const sendKey = ref(""),
	draft = ref(""),
	entryKind = ref("Message"),
	reply = ref(null),
	files = ref([]),
	thread = ref(null),
	fileInput = ref(null);
const dialog = ref(""),
	dialogError = ref(""),
	spaceForm = ref({}),
	addPerson = ref(""),
	itemForm = ref({}),
	trackerForm = ref({}),
	listRows = ref([]),
	selectedItem = ref(null),
	progress = ref({}),
	history = ref([]),
	messageEdit = ref("");
const trackerFiles = ref([]), trackerRequestKey = ref(""), trackerFileNote = ref("");
const trackerFileRows = ref([]), trackerFileCursor = ref(null), trackerFilesLoading = ref(false), trackerCanAdd = ref(false), trackerFileRestricted = ref(false);
const kinds = ["Task", "Event", "List", "Tracker"],
	tabs = ["Chat", "Tasks", "Calendar", "Lists", "Progress"],
	priorities = ["Very low", "Low", "Medium", "High", "Very high"];
const directory = computed(() => home.value?.directory || []);
const schedule = ref({ action: "", date: "" });
const shareRows = ref([]), sharePerson = ref(""), shareDirectory = ref([]);
let shareSearchVersion=0;
watch(sharePerson, async (value) => {
    const version=++shareSearchVersion;
    if (!value) {shareDirectory.value=directory.value;return;}
    await new Promise(resolve=>setTimeout(resolve,300));
    if(version!==shareSearchVersion)return;
    try {const people=await call(API+'get_directory',{query:value});if(version===shareSearchVersion)shareDirectory.value=people;}catch(e){dialogError.value=e.message;}
});
const dialogTitle = computed(
	() =>
		({
			space: spaceForm.value.name
				? "Workspace settings"
				: spaceForm.value.parent_space
					? "New subarea"
					: "New conversation",
			item: itemForm.value.name ? "Edit work item" : "Create work item",
			progress: "Record progress",
            trackerFiles: "Tracker files",
            share: "Share " + (selectedItem.value?.item_kind || "item").toLowerCase(),
            itemView: selectedItem.value?.title || "Work item",
			history: "Activity history",
			message: "Edit message",
			schedule: schedule.value.action === "snooze" ? "Snooze task" : "Postpone task",
		})[dialog.value],
);
const grouped = computed(() => {
	const spaces = home.value?.spaces || [],
		query = search.value.toLowerCase();
	const visible = spaces.filter((r) => includeArchived.value || !r.archived);
	function walk(parent, depth = 0) {
		return visible
			.filter((r) => (r.parent_space || "") === parent)
			.flatMap((r) => [
				{ ...r, depth },
				...(!collapsed.value.has(r.name) || query ? walk(r.name, depth + 1) : []),
			]);
	}
	const rows = walk("").filter((r) => !query || r.title.toLowerCase().includes(query));
	return [
		{
			kind: "Direct",
			label: "DIRECT MESSAGES",
			rows: rows.filter((r) => r.space_kind === "Direct"),
		},
		{
			kind: "work",
			label: "GROUPS & WORKSPACES",
			rows: rows.filter((r) => r.space_kind !== "Direct"),
		},
	].filter((g) => g.rows.length);
});
const personalItems = computed(() =>
	personalTab.value === "Today" ? work.value.today || [] : work.value.open_progress || [],
);
function clone(value) {
	return JSON.parse(JSON.stringify(value));
}
function nonce() {
	return crypto.randomUUID
		? crypto.randomUUID()
		: `key-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
function initials(name) {
	return String(name)
		.split(" ")
		.slice(0, 2)
		.map((s) => s[0])
		.join("")
		.toUpperCase();
}
function personName(id) {
	return (
		directory.value.find((u) => u.name === id)?.full_name ||
		room.value?.space.members.find((u) => u.user === id)?.full_name ||
		id
	);
}
function children(row) {
	return home.value.spaces.filter((r) => r.parent_space === row.name);
}
function toggleArea(id) {
	const set = new Set(collapsed.value);
	set.has(id) ? set.delete(id) : set.add(id);
	collapsed.value = set;
}
function tabKind(value) {
	return { Tasks: "Task", Lists: "List", Progress: "Tracker" }[value] || "Task";
}
function filteredKind(value) {
	return (room.value?.items || []).filter((i) => i.item_kind === tabKind(value));
}
function dateTime(value) {
	return String(value || "")
		.replace("T", " ")
		.slice(0, 16);
}
function trackerLabel(item) {
	const d = item.item_data || {};
	if (["Stages", "Status"].includes(d.scale))
		return d.stages?.find((s) => s.key === d.stage)?.label || "Not started";
	return d.value == null
		? "Not started"
		: `${d.value}${d.scale === "Percentage" ? "%" : ` ${d.unit || ""}`}`;
}
function linkedItems(entry) {
	return (room.value.items || []).filter(
		(i) =>
			i.source_entry === entry.name ||
			(i.name === entry.item && entry.entry_kind === "System" && !i.source_entry),
	);
}
function openRoom(name) {
	router.push({ path: "/collaboration", query: { space: name } });
}
function openPersonal() {
	router.push({ path: "/collaboration", query: { view: "work" } });
}
function closeRoom() {
	router.push("/collaboration");
}
async function refreshHome() {
	try {
		home.value = await call(API + "get_collaboration_home");
	} catch (error) {
		if (error.status === 403) {
			home.value = null;
			room.value = null;
			work.value = {};
			dialog.value = "";
		}
		throw error;
	}
}
async function loadWork() {
	work.value = await call(API + "get_my_work", { date: workDate.value });
}
async function loadRoom(scroll = false) {
	const id = roomId.value;
	if (!id) return;
	let result;
	try {
		result = await call(API + "get_space", { name: id });
	} catch (error) {
		if (error.status === 403 && roomId.value === id) room.value = null;
		throw error;
	}
	if (roomId.value !== id) return;
	// Preserve a loaded historical page during background refreshes.
	if (!scroll && room.value?.space.name === id) {
		const map = new Map(room.value.entries.map((e) => [e.name, e]));
		result.entries.forEach((e) => map.set(e.name, e));
		result.entries = [...map.values()].sort((a, b) => a.creation.localeCompare(b.creation));
		result.older_cursor = room.value.older_cursor;
	}
	room.value = result;
	const latest = result.entries.at(-1);
	await nextTick();
	if (roomId.value !== id) return;
	if (scroll && thread.value) thread.value.scrollTop = thread.value.scrollHeight;
	if (latest && latest.creation > result.delivered_through)
		await call(API + "mark_delivered", { space: id, entry: latest.name });
	acknowledgeVisibleMessages();
}
const pendingSeen = new Set();
async function acknowledgeVisibleMessages() {
	const current = room.value;
	const pane = thread.value;
	const latest = current?.entries.findLast((entry) => entry.owner !== home.value.user);
	if (!latest || !pane || document.visibilityState !== "visible" ||
		pane.scrollHeight - pane.scrollTop - pane.clientHeight > 12 ||
		latest.creation <= current.seen_through || pendingSeen.has(latest.name)) return;
	pendingSeen.add(latest.name);
	try {
		await call(API + "mark_seen", { space: current.space.name, entry: latest.name });
		if (room.value === current) current.seen_through = latest.creation;
	} catch {
		// Retry on the next room refresh.
	} finally {
		pendingSeen.delete(latest.name);
	}
}
watch(thread, (pane) => {
	if (!pane) return;
	pane.scrollTop = pane.scrollHeight;
	acknowledgeVisibleMessages();
}, { flush: "post" });
async function navigate() {
	error.value = "";
	reply.value = null;
	files.value = [];
	try {
		if (personal.value) await loadWork();
		else if (roomId.value) {
			room.value = null;
			sendKey.value = nonce();
			draft.value =
				localStorage.getItem(`sevamrita.chat.${home.value?.user}.${roomId.value}`) || "";
			await loadRoom(true);
		}
	} catch (e) {
		error.value = e.message;
	}
}
watch(() => route.fullPath, navigate);
watch(draft, (value) => {
	if (home.value && roomId.value)
		localStorage.setItem(`sevamrita.chat.${home.value.user}.${roomId.value}`, value);
});
async function olderMessages() {
	try {
		const older = await call(API + "get_space", {
			name: roomId.value,
			before: room.value.older_cursor,
		});
		room.value.entries = [...older.entries, ...room.value.entries];
		room.value.older_cursor = older.older_cursor;
	} catch (e) {
		error.value = e.message;
	}
}
async function mutate(fn) {
	if (busy.value) return;
	busy.value = true;
	error.value = "";
	dialogError.value = "";
	try {
		await fn();
		await refreshHome();
		if (personal.value) await loadWork();
		else await loadRoom();
	} catch (e) {
		if (dialog.value) dialogError.value = e.message;
		else error.value = e.message;
	} finally {
		busy.value = false;
	}
}
function chooseFiles(event) {
	const selected = [...event.target.files];
	if (selected.length > 5 || selected.some((f) => f.size > 10 * 1024 * 1024)) {
		error.value = "Choose at most five files, up to 10 MB each.";
		return;
	}
	files.value = selected;
}
function fileSizeLabel(size) {
    return size >= 1048576 ? `${(size / 1048576).toFixed(1)} MB` : size >= 1024 ? `${Math.ceil(size / 1024)} KB` : `${size} B`;
}
function fileBase64(file) {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => resolve(String(reader.result).split(",")[1]);
		reader.onerror = reject;
		reader.readAsDataURL(file);
	});
}
async function send() {
	if (!draft.value.trim()) return;
	const id = roomId.value,
		text = draft.value,
		uploads = [...files.value],
		source = reply.value?.name;
	await mutate(async () => {
		const attachments = await Promise.all(
			uploads.map(async (file) => ({
				filename: file.name,
				content: await fileBase64(file),
			})),
		);
		await call(API + "send_message", {
			payload: {
				space: id,
				body: text,
				entry_kind: entryKind.value,
				request_key: sendKey.value,
				source_entry: source,
				attachments,
			},
		});
		draft.value = "";
		sendKey.value = nonce();
		reply.value = null;
		files.value = [];
		if (fileInput.value) fileInput.value.value = "";
		await loadRoom(true);
	});
}
function newSpace(parent = "") {
	spaceForm.value = {
		title: "",
		space_kind: "Workspace",
		parent_space: parent,
		project: "",
		person: "",
		members: [{ user: home.value.user, access_level: "Owner" }],
	};
	addPerson.value = "";
	dialogError.value = "";
	dialog.value = "space";
}
function editSpace() {
	spaceForm.value = clone(room.value.space);
	spaceForm.value.members = spaceForm.value.members.map((m) => ({
		user: m.user,
		access_level: m.access_level,
	}));
	dialogError.value = "";
	dialog.value = "space";
}
async function saveSpace() {
	await mutate(async () => {
		const f = spaceForm.value;
		const result =
			f.space_kind === "Direct"
				? await call(API + "start_direct", { user: f.person })
				: await call(API + "save_space", {
						name: f.name || null,
						expected_modified: f.modified,
						payload: {
							title: f.title,
							space_kind: f.space_kind,
							parent_space: f.parent_space || null,
							project: f.project || null,
							...(!f.parent_space ? { members: f.members } : {}),
							...(f.name ? { archived: !!f.archived } : {}),
						},
					});
		dialog.value = "";
		openRoom(result.name);
	});
}
function assignmentChanged() {
    if (trackerForm.value.assignment_mode === 'Stages' && !['Stages','Status'].includes(trackerForm.value.scale)) {
        trackerForm.value.scale = 'Stages'; trackerForm.value.value = null; trackerForm.value.stage = null;
    }
}
async function viewWorkItem(item) {
    try { const detail = await call(API+'get_work_item',{name:item.name}); selectedItem.value=detail.items[0]; dialog.value='itemView'; } catch(e) { error.value=e.message; }
}
function shareItem(item) { selectedItem.value=item; shareRows.value=clone(item.shares || []); sharePerson.value=''; shareDirectory.value=directory.value; dialogError.value=''; dialog.value='share'; }
function addSharePerson() {
    const person = [...shareDirectory.value,...directory.value].find(p => p.name === sharePerson.value || p.full_name === sharePerson.value);
    if (!person || shareRows.value.some(p => p.user === person.name)) { dialogError.value='Choose a new person from the directory.'; return; }
    shareRows.value.push({user:person.name,full_name:person.full_name,access:'View'}); sharePerson.value='';
}
async function saveSharing() { await mutate(async () => { await call(API+'share_item',{name:selectedItem.value.name,expected_modified:selectedItem.value.modified,shares:shareRows.value}); dialog.value=''; }); }
function newItem(kind = "Task", source = null) {
	itemForm.value = {
		title: source?.body.slice(0, 160) || "",
		item_kind: kind,
		description: "",
		source_entry: source?.name || null,
		assignee: home.value.user,
		priority: "Medium",
		repeat_pattern: "None",
        participants: [], item_data: {},
    };
    trackerForm.value = { assignment_mode: "Single",
		scale: "Status",
		minimum: 0,
		maximum: 100,
		value: null,
		stages: [],
		unit: "",
		next_action: "",
	};
	listRows.value = [];
	dialogError.value = "";
	dialog.value = "item";
}
async function editItem(item) {
	if (personal.value) {
		openRoom(item.space);
		return;
	}
	if (!item.can_edit || item.item_kind === "Tracker" && !item.can_configure || !room.value.space.can_post) {
		if (item.item_kind === "Tracker") return showHistory(item);
		return;
	}
    itemForm.value = clone(item);
    itemForm.value.item_data ||= {};
    trackerForm.value = {assignment_mode: "Single", ...clone(item.item_data || {})};
	listRows.value = clone(item.item_data?.rows || []);
	for (const k of ["start_at", "end_at"])
		if (itemForm.value[k]) itemForm.value[k] = dateTime(itemForm.value[k]).replace(" ", "T");
	dialogError.value = "";
	dialog.value = "item";
}
async function saveItem() {
	await mutate(async () => {
		const f = itemForm.value;
		const payload = Object.fromEntries(
			[
				"title",
				"item_kind",
				"description",
				"source_entry",
				"assignee",
				"priority",
				"from_date",
				"until_date",
				"deadline",
				"repeat_pattern",
				"repeat_until",
				"start_at",
				"end_at",
				"location",
				"participants",
			]
				.filter((k) => f[k] !== undefined)
				.map((k) => [k, f[k] || null]),
		);
        if (f.item_kind === "Task") payload.item_data = {reminder_time: f.item_data?.reminder_time || null};
		if (f.item_kind === "List") payload.item_data = { rows: listRows.value };
		if (f.item_kind === "Tracker") payload.item_data = trackerForm.value;
		await call(API + "save_item", {
			space: roomId.value,
			payload,
			name: f.name || null,
			expected_modified: f.modified,
		});
		dialog.value = "";
	});
}
async function taskAction(item, action) {
	if (["snooze", "postpone"].includes(action)) {
		selectedItem.value = item;
		schedule.value = {
			action,
			date: item.snoozed_until || item.from_date || home.value.today,
		};
		dialogError.value = "";
		dialog.value = "schedule";
		return;
	}
	await mutate(async () => {
        const updated = await call(API + "update_task", {name:item.name,action,expected_modified:item.modified});
        if (dialog.value === 'itemView' && selectedItem.value?.name === updated.name) selectedItem.value=updated;
    });
}
async function saveSchedule() {
	await mutate(async () => {
		await call(API + "update_task", {
			name: selectedItem.value.name,
			action: schedule.value.action,
			date: schedule.value.date || null,
			expected_modified: selectedItem.value.modified,
		});
		dialog.value = "";
	});
}
function openProgress(item) {
    if (!item.can_update) return showHistory(item);
	selectedItem.value = item;
    trackerFiles.value = []; trackerRequestKey.value = nonce();
	progress.value = {
		value: item.item_data.value ?? "",
		stage: item.item_data.stage || "",
		outcome: item.status === "Failed" || item.status === "Completed" ? item.status : "Open",
		effective_at: new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
			.toISOString()
			.slice(0, 16),
		note: "",
		next_action: item.item_data.next_action || "",
		attention_date: item.item_data.attention_date || "",
		attention_until: item.item_data.attention_until || "",
	};
	dialogError.value = "";
	dialog.value = "progress";
}
async function postProgress() {
	await mutate(async () => {
		const p = progress.value;
		await call(API + "record_progress", {
			name: selectedItem.value.name,
			expected_modified: selectedItem.value.modified,
			note: p.note,
            request_key: trackerRequestKey.value,
            attachments: await trackerFilePayload(),
			value: p.value === "" ? null : p.value,
			stage: p.stage,
			outcome: p.outcome,
			effective_at: p.effective_at,
			plan: {
				next_action: p.next_action,
				attention_date: p.attention_date || null,
				attention_until: p.attention_until || null,
			},
		});
		dialog.value = "";
	});
}
async function trackerFilePayload() {
    return Promise.all(trackerFiles.value.map(async file => ({filename: file.name, content: await fileBase64(file)})));
}
async function openTrackerFiles(item) {
    selectedItem.value = item;
    trackerFiles.value = []; trackerRequestKey.value = nonce(); trackerFileNote.value = "";
    trackerFileRows.value = []; trackerFileCursor.value = null; trackerCanAdd.value = false; trackerFileRestricted.value = false;
    dialogError.value = ""; dialog.value = "trackerFiles";
    await loadTrackerFiles();
}
async function loadTrackerFiles(before = null) {
    if (trackerFilesLoading.value) return;
    trackerFilesLoading.value = true;
    const name = selectedItem.value.name;
    try {
        const result = await call(API + "get_tracker_files", {name, before});
        if (selectedItem.value?.name !== name || dialog.value !== "trackerFiles") return;
        trackerFileRows.value = [...(before ? trackerFileRows.value : []), ...result.files];
        trackerFileCursor.value = result.next_cursor;
        trackerCanAdd.value = result.can_add;
        trackerFileRestricted.value = result.restricted;
    } catch (error) {dialogError.value = error.message;}
    finally {trackerFilesLoading.value = false;}
}
async function postTrackerFiles() {
    await mutate(async () => {
        const result = await call(API + "add_tracker_files", {name: selectedItem.value.name,
            expected_modified: selectedItem.value.modified, request_key: trackerRequestKey.value,
            note: trackerFileNote.value, attachments: await trackerFilePayload()});
        selectedItem.value = result;
        trackerFiles.value = []; trackerFileNote.value = ""; trackerRequestKey.value = nonce();
        await loadTrackerFiles();
        notice.value = "Files added to the tracker.";
    });
}
async function showHistory(item) {
	try {
		const result = await call(API + "get_item_history", { name: item.name });
		history.value = result.history;
		dialog.value = "history";
	} catch (e) {
		error.value = e.message;
	}
}
function editMessage(entry) {
	selectedItem.value = entry;
	messageEdit.value = entry.body;
	dialogError.value = "";
	dialog.value = "message";
}
async function saveMessage() {
	await mutate(async () => {
		await call(API + "edit_entry", {
			name: selectedItem.value.name,
			body: messageEdit.value,
			expected_modified: selectedItem.value.modified,
		});
		dialog.value = "";
	});
}
async function removeMessage(entry) {
	if (window.confirm("Remove this message? Linked work and its history will remain."))
		await mutate(() =>
			call(API + "edit_entry", {
				name: entry.name,
				remove: true,
				expected_modified: entry.modified,
			}),
		);
}
function moveRow(index, delta) {
	const next = index + delta;
	if (next >= 0 && next < listRows.value.length)
		[listRows.value[index], listRows.value[next]] = [
			listRows.value[next],
			listRows.value[index],
		];
}
function removeListRow(id) {
	listRows.value = listRows.value
		.filter((r) => r.id !== id)
		.map((r) => (r.parent_id === id ? { ...r, parent_id: "" } : r));
}
function closeDialog() {
	if (!busy.value) {
		dialog.value = "";
		dialogError.value = "";
	}
}
let timer;
onMounted(async () => {
	document.addEventListener("visibilitychange", acknowledgeVisibleMessages);
	try {
		await refreshHome();
		await navigate();
		timer = setInterval(async () => {
			if (document.hidden || busy.value || dialog.value) return;
			try {
				await refreshHome();
				if (personal.value) await loadWork();
				else if (roomId.value) await loadRoom();
			} catch (e) {
				error.value = e.message;
			}
		}, 15000);
	} catch (e) {
		error.value = e.message;
	} finally {
		loading.value = false;
	}
});
onUnmounted(() => {
	clearInterval(timer);
	document.removeEventListener("visibilitychange", acknowledgeVisibleMessages);
});

const ItemCard = defineComponent({
	props: ["item"],
	emits: ["edit", "action", "progress", "history", "share", "files"],
	setup(props, { emit }) {
		return () => {
			const i = props.item,
				data = i.item_data || {};
			const active = ["Open", "In progress"].includes(i.status);
			const nodes = [
				h("div", { class: "item-heading" }, [
					h("span", { class: "item-kind" }, i.item_kind),
					h(
						"span",
						{ class: `item-status ${i.status === "Failed" ? "failed" : ""}` },
						i.status,
					),
				]),
				h(
					"button",
					{
						class: "item-title",
						onClick: () => emit(i.item_kind === "Tracker" ? "progress" : "edit"),
					},
					i.title,
				),
			];
			if (i.description) nodes.push(h("p", { class: "item-description" }, i.description));
			if (i.item_kind === "Tracker") {
				nodes.push(h("strong", { class: "tracker-value" }, trackerLabel(i)));
				if (data.value != null && ["Percentage", "Number"].includes(data.scale))
					nodes.push(
						h("progress", {
							max: data.maximum - data.minimum,
							value: data.value - data.minimum,
							"aria-label": `${i.title} progress`,
						}),
					);
				if (data.stages?.length)
					nodes.push(
						h(
							"div",
							{ class: "stage-chips" },
							data.stages.map((s) =>
								h("span", { class: { chosen: s.key === data.stage } }, s.label + (s.assignee_name ? " · " + s.assignee_name : "")),
							),
						),
					);
				if (data.next_action)
					nodes.push(h("p", { class: "text-sm mt-2" }, `Next: ${data.next_action}`));
			}
			if (i.item_kind === "List")
				nodes.push(
					h(
						"ul",
						{ class: "checklist-preview" },
						(data.rows || []).map((r) =>
							h(
								"li",
								{ style: { marginLeft: r.parent_id ? "18px" : "0" } },
								`${r.completed ? "☑" : "☐"} ${r.content}`,
							),
						),
					),
				);
			const meta =
				i.item_kind === "Event"
					? [dateTime(i.start_at), "to", dateTime(i.end_at), i.location]
					: [
							i.assignee_name,
							i.from_date,
							i.until_date ? `until ${i.until_date}` : "",
							i.deadline ? `Deadline ${i.deadline}` : "",
							i.snoozed_until ? `Snoozed until ${i.snoozed_until}` : "",
							i.priority,
						];
			nodes.push(h("small", { class: "item-meta" }, meta.filter(Boolean).join(" · ")));
			const actions = [];
			if (i.can_update && i.item_kind === "Task") {
				if (active)
					for (const [key, label] of [
						["start", "In progress"],
                        ["complete", "Complete"],
						["fail", "Mark failed"],
						["postpone", "Postpone"],
						["snooze", "Snooze / wake"],
					])
						actions.push(h("button", { onClick: () => emit("action", key) }, label));
				else
					actions.push(
						h("button", { onClick: () => emit("action", "reopen") }, "Reopen"),
					);
			}
            if (i.can_update && i.item_kind === "Tracker")
                actions.push(h("button", { onClick: () => emit("progress") }, "Update progress"));
            if (i.item_kind === "Tracker" ? i.can_configure : i.can_edit)
                actions.push(
					h(
						"button",
						{ onClick: () => emit("edit") },
						i.item_kind === "Tracker" ? "Configure" : "Edit",
					),
				);
            if (i.can_share) actions.push(h("button", {onClick: () => emit("share")}, "Share"));
            if (i.item_kind === "Tracker") actions.push(h("button", {onClick: () => emit("files")}, "Files"));
			actions.push(h("button", { onClick: () => emit("history") }, "History"));
			nodes.push(h("div", { class: "item-actions" }, actions));
			return h("div", { class: "item-card" }, nodes);
		};
	},
});
const CalendarView = defineComponent({
	props: ["items"],
	emits: ["open"],
	setup(props, { emit }) {
		const month = ref(new Date()),
			selected = ref(new Date().toLocaleDateString("en-CA"));
		function dayValue(date) {
			return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
		}
		function onDay(item, date) {
			const start = String(
					item.item_kind === "Event" ? item.start_at || "" : item.from_date || "",
				).slice(0, 10),
				end = String(
					item.item_kind === "Event" ? item.end_at || "" : item.until_date || start,
				).slice(0, 10);
			return (
				["Task", "Event"].includes(item.item_kind) && start && start <= date && date <= end
			);
		}
		return () => {
			const first = new Date(month.value.getFullYear(), month.value.getMonth(), 1),
				length = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
			const cells = Array.from({ length: first.getDay() }, () => h("span"));
			for (let d = 1; d <= length; d++) {
				const date = dayValue(new Date(first.getFullYear(), first.getMonth(), d)),
					count = props.items.filter((i) => onDay(i, date)).length;
				cells.push(
					h(
						"button",
						{
							class: { chosen: selected.value === date },
							onClick: () => (selected.value = date),
							"aria-label": date,
						},
						[h("strong", d), count ? h("small", `${count} items`) : null],
					),
				);
			}
			const rows = props.items.filter((i) => onDay(i, selected.value));
			return h("div", { class: "calendar" }, [
				h("div", { class: "calendar-heading" }, [
					h(
						"button",
						{
							onClick: () =>
								(month.value = new Date(
									first.getFullYear(),
									first.getMonth() - 1,
									1,
								)),
							"aria-label": "Previous month",
						},
						"←",
					),
					h("h3", first.toLocaleDateString("en-IN", { month: "long", year: "numeric" })),
					h(
						"button",
						{
							onClick: () =>
								(month.value = new Date(
									first.getFullYear(),
									first.getMonth() + 1,
									1,
								)),
							"aria-label": "Next month",
						},
						"→",
					),
				]),
				h("div", { class: "calendar-grid" }, [
					...["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => h("small", d)),
					...cells,
				]),
				h("h3", { class: "mt-5 font-semibold" }, selected.value),
				...rows.map((i) =>
					h(
						"button",
						{ class: "calendar-event", onClick: () => emit("open", i) },
						`${i.item_kind === "Event" ? "◷" : "☐"} ${i.title} · ${i.item_kind === "Event" ? dateTime(i.start_at) : i.assignee_name}`,
					),
				),
				!rows.length
					? h(
							"p",
							{ class: "text-sm text-muted mt-3" },
							"No scheduled work for this date.",
						)
					: null,
			]);
		};
	},
});
</script>

<style scoped>
.collaboration {
	max-width: 1500px;
	margin: auto;
	color: #20343d;
}
.collab-heading {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 16px;
	margin-bottom: 22px;
}
.collab-heading h1 {
	font-size: 27px;
	font-weight: 750;
}
.eyebrow {
	font-size: 10px;
	letter-spacing: 0.12em;
	color: #61808c;
	font-weight: 700;
}
.collab-layout {
	display: grid;
	grid-template-columns: 290px minmax(0, 1fr);
	height: calc(100dvh - 215px);
	min-height: 600px;
	border: 1px solid #dde5e9;
	border-radius: 20px;
	overflow: hidden;
	background: #fff;
	box-shadow: 0 8px 28px #213d4c06;
}
.spaces-pane > input {
	display: block;
	width: 100%;
	padding: 11px 12px;
	border: 1px solid #dce5e9;
	border-radius: 10px;
	background: #fff;
	font-size: 13px;
}
.collaboration .btn-primary {
	background: #08745e;
	color: #fff;
}
.spaces-pane {
	background: #f8fafb;
	border-right: 1px solid #e3eaed;
	padding: 16px;
	overflow: auto;
}
.my-work {
	display: flex;
	gap: 8px;
	align-items: center;
	font-weight: 650;
	width: 100%;
	padding: 12px;
	border-radius: 12px;
	background: #eaf1fb;
	color: #355b86;
}
.space-group h2 {
	font-size: 10px;
	font-weight: 750;
	letter-spacing: 0.1em;
	color: #7a8b93;
	margin: 24px 4px 9px;
}
.space-nav-row {
	position: relative;
	padding-left: calc(var(--depth) * 13px);
}
.space-link {
	width: 100%;
	display: flex;
	align-items: center;
	gap: 10px;
	text-align: left;
	padding: 12px 8px;
	border-radius: 12px;
}
.space-link:hover {
	background: #edf3f4;
}
.space-link.selected {
	background: #dcefe9;
}
.space-link strong {
	font-size: 13px;
	display: block;
	white-space: nowrap;
	text-overflow: ellipsis;
	overflow: hidden;
}
.space-link small {
	font-size: 11px;
	color: #74848b;
	display: block;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
	margin-top: 3px;
}
.avatar {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 34px;
	height: 34px;
	border-radius: 11px;
	background: #e2e9f5;
	color: #45618c;
	font-size: 11px;
	font-weight: 750;
	flex-shrink: 0;
}
.unread {
	background: #127761;
	color: white;
	font-size: 10px;
	border-radius: 20px;
	padding: 2px 6px;
}
.expand-area {
	position: absolute;
	left: calc(var(--depth) * 13px - 7px);
	top: 21px;
	font-size: 18px;
	z-index: 1;
}
.conversation-pane {
	display: flex;
	flex-direction: column;
	min-width: 0;
	min-height: 0;
}
.room-header {
	padding: 20px 24px;
	display: flex;
	align-items: center;
	gap: 12px;
	border-bottom: 1px solid #e4eaed;
	flex-wrap: wrap;
}
.room-header h2 {
	font-size: 20px;
	font-weight: 750;
	overflow-wrap: anywhere;
}
.room-tabs {
	display: flex;
	gap: 4px;
	align-items: center;
	padding: 8px 20px;
	border-bottom: 1px solid #e4eaed;
	overflow-x: auto;
	flex-shrink: 0;
}
.room-tabs button {
	white-space: nowrap;
	padding: 9px 12px;
	border-radius: 9px;
	font-size: 13px;
	color: #6b7f87;
}
.room-tabs .active {
	color: #0b725d;
	background: #e3f2ec;
	font-weight: 700;
}
.room-tabs .new-work {
	margin-left: auto;
	color: #0b725d;
	font-weight: 700;
}
.message-thread {
	flex: 1;
	overflow-y: auto;
	padding: 24px;
	background: #f5f8fa;
	display: flex;
	flex-direction: column;
	gap: 20px;
	min-height: 140px;
}
.message {
	align-self: flex-start;
	max-width: min(85%, 680px);
	padding: 15px 18px;
	border: 1px solid #e4eaee;
	border-radius: 16px 16px 16px 4px;
	background: white;
	overflow-wrap: anywhere;
}
.message.mine {
	align-self: flex-end;
	border-radius: 16px 16px 4px 16px;
	background: #e8f4ef;
	border-color: #d6eae0;
}
.message.system {
	background: #f0f3f7;
	font-size: 13px;
}
.message-meta {
	display: flex;
	align-items: center;
	flex-wrap: wrap;
	gap: 8px;
	font-size: 10px;
	color: #7c8b93;
	margin-bottom: 7px;
}
.message-meta strong {
	font-size: 12px;
	color: #455d6b;
}
.message-text {
	white-space: pre-wrap;
	line-height: 1.65;
	font-size: 14px;
}
.reply-label {
	font-size: 11px;
	border-left: 3px solid #8eb3ab;
	padding-left: 8px;
	color: #6b8286;
	margin-bottom: 8px;
}
.message-options {
	margin-top: 10px;
	font-size: 11px;
	color: #648078;
}
.message-options summary {
	cursor: pointer;
}
.message-options button {
	padding: 7px 8px;
	text-decoration: underline;
}
.snapshot {
	padding: 10px 0;
	font-size: 12px;
	display: flex;
	flex-direction: column;
	color: #5d748a;
	gap: 4px;
}
.file-link {
	display: block;
	color: #1c705e;
	text-decoration: underline;
	font-size: 12px;
	margin-top: 10px;
}
.composer {
	padding: 16px 24px;
	border-top: 1px solid #e3eaed;
	background: #fff;
}
.composer textarea {
	width: 100%;
	border: 1px solid #dce5e9;
	border-radius: 12px;
	padding: 12px;
	font-size: 16px;
	resize: vertical;
	min-height: 80px;
	margin: 8px 0;
}
.composer-top {
	display: flex;
	align-items: center;
	gap: 12px;
	flex-wrap: wrap;
}
.composer-top select {
	font-size: 12px;
	color: #5e737b;
}
.attachment-picker {
	font-size: 12px;
	color: #426d65;
	cursor: pointer;
}
.attachment-picker input {
	display: none;
}
.reply-preview {
	padding: 9px;
	background: #f2f7f6;
	font-size: 12px;
	color: #4b6b64;
	display: flex;
	justify-content: space-between;
}
.work-body {
	overflow: auto;
	padding: 24px;
	flex: 1;
}
.work-card {
	border: 1px solid #e1e8eb;
	border-radius: 15px;
	padding: 18px;
	margin-bottom: 14px;
}
.linked-item {
	background: #ffffffb0;
	border: 1px solid #d8e7df;
	border-radius: 12px;
	margin-top: 12px;
	padding: 13px;
}
.read-only {
	padding: 15px;
	text-align: center;
	color: #788890;
	font-size: 13px;
	background: #f5f7f9;
}
.welcome-panel {
	margin: auto;
	text-align: center;
	max-width: 430px;
	padding: 36px;
}
.welcome-panel h2 {
	font-size: 23px;
	font-weight: 700;
	margin: 15px 0;
}
.welcome-panel p {
	color: #82939b;
	line-height: 1.8;
	margin-bottom: 24px;
}
.welcome-symbol {
	font-size: 50px;
	color: #6aaa9b;
}
.empty-state {
	color: #8a9aa3;
	text-align: center;
	font-size: 14px;
	padding: 40px 15px;
}
.error-banner,
.notice-banner {
	padding: 12px 16px;
	border-radius: 12px;
	margin-bottom: 14px;
	font-size: 13px;
	background: #fff0ed;
	color: #993b2c;
	overflow-wrap: anywhere;
}
.error-banner button {
	float: right;
}
.notice-banner {
	background: #e8f5ee;
	color: #186449;
}
.mobile-back {
	display: none;
}
.dialog-backdrop {
	position: fixed;
	inset: 0;
	z-index: 80;
	background: #172f4166;
	backdrop-filter: blur(3px);
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 16px;
}
.collab-dialog {
	background: white;
	width: 100%;
	max-width: 640px;
	border-radius: 20px;
	max-height: 92dvh;
	display: flex;
	flex-direction: column;
	overflow: auto;
	box-shadow: 0 24px 90px #12273533;
}
.dialog-header,
.dialog-footer {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 20px 24px;
	border-bottom: 1px solid #e4eaed;
	position: sticky;
	top: 0;
	background: white;
	z-index: 2;
}
.dialog-header h2 {
	font-size: 20px;
	font-weight: 750;
}
.dialog-header > button {
	font-size: 25px;
}
.dialog-footer {
	border-top: 1px solid #e4eaed;
	border-bottom: 0;
	position: sticky;
	bottom: 0;
	justify-content: flex-end;
}
.dialog-body {
	padding: 22px 24px;
	display: flex;
	flex-direction: column;
	gap: 17px;
}
.collab-dialog label {
	display: flex;
	flex-direction: column;
	font-size: 13px;
	font-weight: 600;
	gap: 7px;
}
.collab-dialog input:not([type="checkbox"]),
.collab-dialog select,
.collab-dialog textarea {
	border: 1px solid #d9e3e8;
	border-radius: 10px;
	padding: 11px 12px;
	width: 100%;
	font-size: 16px;
	font-weight: 400;
	min-width: 0;
	background: #fcfdfd;
}
.collab-dialog small {
	font-size: 11px;
	font-weight: 400;
	color: #7f8e97;
}
.field-grid {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 16px;
}
.collab-dialog .check-label {
	display: flex;
	flex-direction: row;
	align-items: center;
	font-size: 13px;
	font-weight: 400;
	gap: 8px;
}
.member-row {
	display: flex;
	align-items: center;
	gap: 12px;
	font-size: 13px;
}
.member-row span {
	flex: 1;
	overflow-wrap: anywhere;
}
.member-row select {
	width: 120px;
	padding: 8px;
}
.stage-row {
	display: flex;
	gap: 8px;
	align-items: center;
}
.stage-row input:nth-child(2) {
	width: 90px;
}
.list-edit-row {
	padding: 13px;
	border: 1px solid #dde6e9;
	border-radius: 12px;
	display: flex;
	flex-direction: column;
	gap: 8px;
}
.list-edit-row button {
	font-size: 12px;
	padding: 7px;
}
.stage-timeline {
	display: flex;
	flex-direction: column;
	gap: 7px;
}
.stage-timeline button {
	display: flex;
	gap: 10px;
	padding: 12px;
	text-align: left;
	border: 1px solid #e1e8ed;
	border-radius: 10px;
}
.stage-timeline .chosen {
	background: #e3f2ec;
	border-color: #63a392;
}
.history-row {
	border-bottom: 1px solid #e3e9ed;
	padding: 14px 0;
	white-space: pre-wrap;
}
.history-row small {
	display: block;
	margin-top: 7px;
}
.collaboration :deep(.item-heading) {
	display: flex;
	gap: 10px;
	align-items: center;
	justify-content: space-between;
}
.collaboration :deep(.item-kind) {
	font-size: 10px;
	letter-spacing: 0.06em;
	text-transform: uppercase;
	color: #7d9098;
}
.collaboration :deep(.item-status) {
	font-size: 10px;
	border-radius: 8px;
	background: #f0f4f6;
	color: #5a737e;
	padding: 3px 7px;
}
.collaboration :deep(.item-status.failed) {
	background: #fce9e5;
	color: #9f4739;
}
.collaboration :deep(.item-title) {
	display: block;
	font-size: 16px;
	font-weight: 700;
	text-align: left;
	margin: 7px 0;
	overflow-wrap: anywhere;
}
.collaboration :deep(.item-description) {
	white-space: pre-wrap;
	font-size: 13px;
	color: #6c818c;
	margin-bottom: 8px;
}
.collaboration :deep(.item-meta) {
	display: block;
	font-size: 11px;
	color: #81939c;
	line-height: 1.8;
	margin-top: 8px;
}
.collaboration :deep(.item-actions) {
	display: flex;
	flex-wrap: wrap;
	gap: 10px;
	font-size: 11px;
	color: #176a59;
	margin-top: 10px;
}
.collaboration :deep(.item-actions button) {
	min-height: 32px;
	text-decoration: underline;
}
.collaboration :deep(.tracker-value) {
	color: #176a59;
	font-size: 18px;
	display: block;
	margin: 8px 0;
}
.collaboration :deep(progress) {
	width: 100%;
	height: 9px;
	accent-color: #167c68;
}
.collaboration :deep(.stage-chips) {
	display: flex;
	flex-wrap: wrap;
	gap: 5px;
}
.collaboration :deep(.stage-chips span) {
	font-size: 10px;
	padding: 5px;
	border-radius: 7px;
	background: #edf1f5;
	color: #7b8b97;
}
.collaboration :deep(.stage-chips .chosen) {
	background: #d7eee4;
	color: #17634e;
}
.collaboration :deep(.checklist-preview) {
	font-size: 13px;
	line-height: 1.8;
	margin-top: 9px;
}
.collaboration :deep(.calendar-heading) {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: 20px;
	font-size: 17px;
	font-weight: 700;
}
.collaboration :deep(.calendar-heading button) {
	padding: 12px;
}
.collaboration :deep(.calendar-grid) {
	display: grid;
	grid-template-columns: repeat(7, minmax(0, 1fr));
	gap: 5px;
}
.collaboration :deep(.calendar-grid > small) {
	text-align: center;
	color: #8796a0;
	font-size: 10px;
}
.collaboration :deep(.calendar-grid button) {
	display: flex;
	flex-direction: column;
	align-items: center;
	border: 1px solid #e3eaee;
	border-radius: 10px;
	padding: 12px 3px;
	min-height: 64px;
	font-size: 13px;
	gap: 5px;
}
.collaboration :deep(.calendar-grid .chosen) {
	background: #e0f1e9;
	border-color: #72a695;
}
.collaboration :deep(.calendar-grid small) {
	font-size: 9px;
	color: #39816c;
}
.collaboration :deep(.calendar-event) {
	display: block;
	text-align: left;
	padding: 14px;
	background: #f1f6f8;
	border-radius: 10px;
	margin-top: 10px;
	font-size: 13px;
	width: 100%;
}
@media (max-width: 900px) {
	.collab-layout {
		grid-template-columns: 230px minmax(0, 1fr);
	}
	.room-header {
		padding: 16px;
	}
	.message {
		max-width: 95%;
	}
	.room-header .btn-secondary {
		font-size: 11px;
		padding: 7px;
	}
	.work-body,
	.message-thread {
		padding: 16px;
	}
}
@media (max-width: 640px) {
	.collab-heading {
		align-items: flex-start;
		margin-bottom: 14px;
	}
	.collab-heading h1 {
		font-size: 22px;
	}
	.collab-heading .btn-primary {
		font-size: 12px;
		max-width: 120px;
	}
	.collab-heading .text-muted {
		font-size: 12px;
	}
	.collab-layout {
		display: block;
		min-height: 560px;
		height: calc(100dvh - 220px);
	}
	.spaces-pane {
		height: 100%;
		border: 0;
	}
	.conversation-pane {
		height: 100%;
		display: none;
	}
	.room-open .spaces-pane {
		display: none;
	}
	.room-open .conversation-pane {
		display: flex;
	}
	.mobile-back {
		display: block;
		color: #1d7664;
		font-size: 12px;
		width: 100%;
		text-align: left;
	}
	.room-header h2 {
		font-size: 17px;
	}
	.room-header {
		gap: 9px;
	}
	.room-tabs {
		padding: 7px;
	}
	.room-tabs button {
		font-size: 12px;
		padding: 9px;
	}
	.composer {
		padding: 12px;
	}
	.composer .text-xs {
		font-size: 10px;
		max-width: 60%;
	}
	.message-thread {
		gap: 14px;
	}
	.message {
		padding: 12px;
	}
	.message-text {
		font-size: 14px;
	}
	.field-grid {
		grid-template-columns: 1fr;
	}
	.dialog-body,
	.dialog-header,
	.dialog-footer {
		padding: 18px;
	}
	.collab-dialog {
		max-height: 95dvh;
	}
	.work-body {
		padding: 14px;
	}
	.member-row {
		gap: 5px;
	}
	.member-row select {
		width: 100px;
	}
	.collaboration :deep(.calendar-grid button) {
		min-height: 52px;
		padding: 8px 1px;
	}
	.collaboration :deep(.calendar-grid small) {
		font-size: 8px;
	}
}
</style>

<style scoped>
.assignment-choice {display:grid;gap:12px;padding:16px;border:1px solid #d9e5e1;border-radius:14px}.assignment-choice label{display:flex;align-items:center;gap:12px;background:#f0f7f4;border-radius:10px;padding:14px}.assignment-choice input{width:auto}.assignment-choice small{display:block;margin-top:4px;color:#637378}.stage-row{display:flex;flex-wrap:wrap;padding:12px;background:#f4f8f6;border-radius:12px}.stage-row input:first-child{min-width:140px;flex:1}.stage-row select{min-width:180px;flex:1}.sharing-row{display:grid;gap:10px;padding:14px;border:1px solid #d9e5e1;border-radius:12px}
.tracker-files-panel { display: grid; gap: 16px; }
.tracker-file-upload { display: grid; gap: 12px; padding: 16px; border: 1px solid #dfe8e5; border-radius: 14px; background: #f8fbfa; }
.tracker-file-link { display: flex; gap: 12px; padding: 14px; border: 1px solid #e1e7e9; border-radius: 12px; color: #146b58; overflow-wrap: anywhere; }
.tracker-file-link > span { display: grid; gap: 5px; min-width: 0; }
.tracker-file-link small { color: #68777d; }
.tracker-file-upload button:disabled, .dialog-header button:disabled { opacity: .45; cursor: not-allowed; }
.tracker-history-file { display: block; margin: 8px 0; color: #146b58; overflow-wrap: anywhere; }
</style>
