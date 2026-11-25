<template>
	<div class="sf-app" :data-theme="resolvedTheme">
		<template v-if="!user || !allowed">
			<main class="sign-in">
				<div class="brand-mark">S<span>web</span></div>
				<p class="eyebrow">SEVAMRITA</p>
				<h1>SF Tasks <span>PWA</span></h1>
				<p class="intro">Your conversations.<br />Your team’s next steps.</p>
				<form class="login-card" @submit.prevent="login">
					<h2>Welcome back</h2>
					<p>Sign in with your Sevamrita account.</p>
					<label
						>Email<input
							v-model="credentials.usr"
							type="email"
							autocomplete="username"
							required
							placeholder="you@sevamrita.org"
					/></label>
					<label
						>Password<input
							v-model="credentials.pwd"
							type="password"
							autocomplete="current-password"
							required
					/></label>
					<p v-if="loginError" class="error" role="alert">{{ loginError }}</p>
					<p v-if="user && !allowed" class="error">
						App chat access is required. Ask your administrator to enable it for
						{{ user }}.
					</p>
					<button class="primary wide" :disabled="busy">
						{{ busy ? "Signing in…" : "Sign in" }}
					</button>
					<button type="button" class="text-button" @click="overlay = 'reset'">
						Forgot password?
					</button>
				</form>
				<p class="footnote">
					A separate web app. Your Android app and ERP Home remain available.
				</p>
			</main>
		</template>
		<template v-else>
			<header class="app-header">
				<button
					v-if="roomId || selected || view === 'search'"
					class="icon-button"
					aria-label="Back"
					@click="goBack"
				>
					←
				</button>
				<div class="header-title">
					<span v-if="room" class="overline">{{ room.space.space_kind }}</span>
					<h1>{{ pageTitle }}</h1>
					<small v-if="room">{{
						room.space.members.map((p) => p.full_name).join(", ")
					}}</small>
				</div>
				<button
					class="icon-button"
					aria-label="Search"
					@click="navigate({ view: 'search', in: roomId || undefined })"
				>
					<SvgIcon name="search" />
				</button>
				<button
					v-if="queue.length"
					class="icon-button queue-button"
					:aria-label="`Outbox: ${queue.length} unsent changes`"
					@click="navigate({ view: 'outbox' })"
				>
					{{ queue.length }}
				</button>
				<button
					class="icon-button"
					aria-label="Settings"
					@click="navigate({ view: 'settings' })"
				>
					<SvgIcon name="settings" />
				</button>
			</header>
			<div v-if="!online || !serverReachable" class="connection-note" role="status">
				Connection unavailable · saved content is available. Changes stay in your Outbox.
			</div>
			<div v-else-if="authExpired" class="connection-note error" role="alert">
				Your session expired. <button @click="reauth">Sign in again</button>
			</div>
			<div v-if="notice" class="toast" role="status">
				{{ notice }}<button aria-label="Dismiss" @click="notice = ''">×</button>
			</div>
			<div v-if="error" class="error-banner" role="alert">
				{{ error }}<button aria-label="Dismiss error" @click="error = ''">×</button>
			</div>
			<div v-if="updateReady" class="update-note">
				A new version is ready. Your saved drafts will be kept.<button
					@click="activateUpdate"
				>
					Update
				</button>
			</div>

			<main
				class="page"
				:class="{ 'conversation-page': roomId && roomTab === 'Chat' && !selected }"
			>
				<template v-if="selected">
					<section class="detail-heading">
						<p class="eyebrow">
							{{ selected.item_kind }} ·
							{{ room?.space.title || selected.space_title }}
						</p>
						<h2>{{ selected.title }}</h2>
						<span class="status-pill" :class="trackerState(selected)">{{
							selected.status
						}}</span>
					</section>
					<template v-if="selected.item_kind === 'Tracker'">
						<section class="card progress-summary">
							<div>
								<small>Progress</small
								><strong>{{ progressOf(selected).label }}</strong
								><ProgressBar :item="selected" />
							</div>
							<div :class="{ 'needs-me': pendingWith(selected)?.user === user }">
								<small>Pending with</small
								><strong>{{
									person(
										pendingWith(selected)?.user,
										pendingWith(selected)?.full_name,
									) || "No pending action"
								}}</strong>
							</div>
						</section>
						<nav class="tabs" aria-label="Tracker sections">
							<button
								v-for="tab in [
									'Workflow',
									'Details',
									'Updates',
									'Comments',
									'Files',
								]"
								:class="{ active: detailTab === tab }"
								@click="setDetailTab(tab)"
							>
								{{ tab }}
							</button>
						</nav>
						<section v-if="detailTab === 'Workflow'" class="card">
							<div class="section-heading">
								<h3>
									{{
										progressOf(selected).stages.length
											? "Workflow"
											: "Current progress"
									}}
								</h3>
								<button
									v-if="selected.can_update"
									class="primary compact"
									@click="openProgress(selected)"
								>
									Update progress
								</button>
							</div>
							<ol v-if="progressOf(selected).stages.length" class="stage-timeline">
								<li
									v-for="(stage, index) in progressOf(selected).stages"
									:class="{
										done:
											index < progressOf(selected).index ||
											selected.status === 'Completed',
										current: index === progressOf(selected).index,
									}"
								>
									<span class="stage-dot">{{
										index < progressOf(selected).index ||
										selected.status === "Completed"
											? "✓"
											: index + 1
									}}</span>
									<div>
										<strong>{{ stage.label }}</strong
										><small>{{
											selected.item_data.assignment_mode === "Stages"
												? person(stage.assignee, stage.assignee_name)
												: person(selected.assignee, selected.assignee_name)
										}}</small
										><small
											v-if="
												index === progressOf(selected).index &&
												OPEN.has(selected.status)
											"
											:class="{
												'needs-me': pendingWith(selected)?.user === user,
											}"
											>Current stage{{
												pendingWith(selected)?.user === user
													? " · Pending with you"
													: ""
											}}</small
										>
									</div>
								</li>
							</ol>
							<div v-else class="big-progress">
								{{ progressOf(selected).label }}<ProgressBar :item="selected" />
							</div>
							<p v-if="selected.item_data.next_action" class="next-action">
								<small>Next action</small>{{ selected.item_data.next_action }}
							</p>
							<p class="muted">{{ dateRange(selected) }}</p>
						</section>
						<section v-if="detailTab === 'Details'" class="card prose">
							<h3>About this tracker</h3>
							<p>{{ selected.description || "No description added." }}</p>
							<dl>
								<dt>Owner</dt>
								<dd>{{ person(selected.owner) }}</dd>
								<dt>Priority</dt>
								<dd>{{ selected.priority }}</dd>
								<dt>Dates</dt>
								<dd>{{ dateRange(selected) || "Not scheduled" }}</dd>
							</dl>
						</section>
						<section v-if="detailTab === 'Comments'" class="card">
							<h3>Conversation</h3>
							<p v-if="itemOnly" class="muted">
								Comments are private to the chat’s members.
							</p>
							<template v-else
								><article
									v-for="comment in comments.comments || []"
									class="comment"
								>
									<strong>{{ comment.author_name }}</strong
									><small>{{ prettyDate(comment.creation, true) }}</small>
									<p>{{ comment.body }}</p>
								</article>
								<button
									v-if="comments.next_cursor"
									class="text-button"
									@click="loadComments(comments.next_cursor)"
								>
									Earlier comments
								</button>
								<form v-if="comments.can_comment" @submit.prevent="postComment">
									<label
										>Add a comment<textarea
											v-model="commentDraft"
											required
											maxlength="12000"
											rows="3"
										></textarea></label
									><MentionPicker
										:members="room?.space.members || []"
										@choose="commentDraft += mention($event)"
									/><button class="primary">Post comment</button>
								</form></template
							>
						</section>
						<section v-if="detailTab === 'Files'" class="card">
							<div class="section-heading">
								<h3>Supporting files</h3>
								<button
									v-if="selected.can_add_files"
									class="primary compact"
									@click="openFiles"
								>
									Add files
								</button>
							</div>
							<p v-if="itemOnly" class="muted">Files are private to chat members.</p>
							<template v-else
								><FileRow
									v-for="file in trackerFiles.files || []"
									:file="file"
									@open="openFile"
									@save="saveFile"
								/>
								<p v-if="!trackerFiles.files?.length" class="empty-inline">
									No supporting files yet.
								</p>
								<button
									v-if="trackerFiles.next_cursor"
									class="text-button"
									@click="loadFiles(trackerFiles.next_cursor)"
								>
									More files
								</button></template
							>
						</section>
						<section v-if="detailTab === 'Updates'" class="card">
							<h3>Update history</h3>
							<article v-for="entry in history" class="history-row">
								<small
									>{{ entry.author_name }} ·
									{{ prettyDate(entry.creation, true) }}</small
								><strong v-if="entry.snapshot?.item_data">{{
									progressOf({
										item_data: entry.snapshot.item_data,
										status: entry.snapshot.status,
									}).label
								}}</strong>
								<p>{{ entry.body }}</p>
								<FileRow
									v-for="file in entry.attachments"
									:file="file"
									@open="openFile"
									@save="saveFile"
								/>
							</article>
						</section>
					</template>
					<template v-else>
						<section class="card prose">
							<p>{{ selected.description || "No description added." }}</p>
							<p class="muted">{{ dateRange(selected) }}</p>
							<p v-if="selected.assignee">
								Assigned to {{ person(selected.assignee, selected.assignee_name) }}
							</p>
							<label v-if="selected.item_kind === 'Task' && selected.can_update"
								>Status<select
									:value="selected.status"
									@change="changeTask(selected, $event.target.value)"
								>
									<option
										v-for="status in [
											'Open',
											'In progress',
											'Completed',
											'Failed',
										]"
									>
										{{ status }}
									</option>
								</select></label
							>
							<div v-if="selected.item_kind === 'Task'" class="subtasks">
								<h3>Subtasks</h3>
								<div
									v-for="sub in selected.item_data.subtasks || []"
									class="subtask"
								>
									<div>
										<strong>{{ sub.title }}</strong
										><small
											>{{ person(sub.assignee)
											}}{{
												sub.deadline
													? " · " + prettyDate(sub.deadline)
													: ""
											}}</small
										>
									</div>
									<select
										v-if="selected.can_update || sub.assignee === user"
										:value="sub.status"
										:aria-label="`Status of ${sub.title}`"
										@change="subtaskStatus(sub, $event.target.value)"
									>
										<option>Open</option>
										<option>In progress</option>
										<option>Completed</option></select
									><span v-else>{{ sub.status }}</span>
								</div>
								<p v-if="!selected.item_data.subtasks?.length" class="muted">
									No subtasks.
								</p>
							</div>
							<ul v-if="selected.item_kind === 'List'" class="check-list">
								<li
									v-for="row in selected.item_data.rows"
									:style="{ paddingLeft: row.parent_id ? '24px' : 0 }"
								>
									<label
										><input
											type="checkbox"
											:checked="row.completed"
											:disabled="!selected.can_edit"
											@change="toggleList(row)"
										/>{{ row.content }}</label
									>
								</li>
							</ul>
							<p v-if="selected.item_kind === 'Event'">
								{{ prettyDate(selected.start_at, true) }} —
								{{ prettyDate(selected.end_at, true) }}<br />{{
									selected.location
								}}
							</p>
						</section>
					</template>
					<div class="detail-actions">
						<button
							v-if="
								selected.can_edit &&
								(selected.item_kind !== 'Tracker' || selected.can_configure)
							"
							class="secondary"
							@click="editItem(selected)"
						>
							Edit {{ selected.item_kind.toLowerCase() }}</button
						><button v-if="selected.can_share" class="secondary" @click="openShare">
							Share</button
						><button
							v-if="selected.item_kind === 'Task' && selected.can_update"
							class="secondary"
							@click="openSchedule"
						>
							Schedule / snooze</button
						><button
							v-if="selected.item_kind !== 'Tracker'"
							class="secondary"
							@click="showHistory"
						>
							History
						</button>
					</div>
				</template>

				<template v-else-if="roomId && room">
					<nav class="tabs room-tabs" aria-label="Conversation sections">
						<button
							v-for="tab in ['Chat', 'Tasks', 'Trackers', 'Calendar', 'Lists']"
							:class="{ active: roomTab === tab }"
							@click="setRoomTab(tab)"
						>
							{{ tab }}</button
						><button
							aria-label="Conversation notifications"
							@click="overlay = 'room-notifications'"
						>
							<SvgIcon name="bell" /></button
						><button
							v-if="room.space.can_manage"
							aria-label="Conversation settings"
							@click="editSpace"
						>
							•••
						</button>
					</nav>
					<template v-if="roomTab === 'Chat'">
						<div
							ref="thread"
							class="thread"
							aria-label="Messages"
							@scroll="seenVisible"
						>
							<button
								v-if="room.older_cursor"
								class="older-button"
								@click="olderMessages"
							>
								Earlier messages
							</button>
							<p v-if="!room.entries.length" class="empty-inline">
								Start the conversation.
							</p>
							<article
								v-for="entry in room.entries"
								:key="entry.name"
								:data-entry="entry.name"
								class="message"
								:class="{
									mine: entry.owner === user,
									system: entry.entry_kind === 'System',
									superseded:
										entry.entry_kind === 'Progress' &&
										room.current_progress?.[entry.item] !== entry.name,
									highlight: route.entry === entry.name,
								}"
							>
								<template v-if="entry.entry_kind === 'System'"
									><button v-if="entry.item" @click="openItemById(entry.item)">
										{{ entry.body }}</button
									><span v-else>{{ entry.body }}</span></template
								>
								<template v-else>
									<small v-if="entry.owner !== user" class="author">{{
										entry.author_name
									}}</small>
									<button
										v-if="entry.source_entry"
										class="reply-chip"
										@click="jumpToEntry(entry.source_entry)"
									>
										↩ Reply to an earlier message
									</button>
									<button
										v-if="entry.snapshot?.item_data"
										class="tracker-message"
										@click="openItemById(entry.item)"
									>
										<strong>{{ entry.snapshot.title }}</strong
										><ProgressBar
											:item="{
												title: entry.snapshot.title,
												item_data: entry.snapshot.item_data,
												status: entry.snapshot.status,
											}"
										/><span>{{
											progressOf({ item_data: entry.snapshot.item_data })
												.label
										}}</span
										><small v-if="entry.snapshot.pending_with?.user"
											>Pending with
											{{
												person(
													entry.snapshot.pending_with.user,
													entry.snapshot.pending_with.full_name,
												)
											}}</small
										><small
											v-if="
												room.current_progress?.[entry.item] !== entry.name
											"
											>Earlier update</small
										>
									</button>
									<button v-if="!entry.is_deleted && entry.snapshot?.attachment_tracker" class="tracker-message"
										@click="openItemById(entry.item)">
										<small>Files for tracker</small><strong>{{ entry.snapshot.attachment_tracker.title }}</strong>
									</button>
									<p class="message-body">{{ entry.body }}</p>
									<FileRow
										v-for="file in entry.attachments"
										:file="file"
										@open="openFile"
										@save="saveFile"
									/>
									<footer>
										<small v-if="entry.edited_at">edited</small
										><time>{{ timeOnly(entry.creation) }}</time
										><button
											v-if="entry.owner === user"
											class="ticks"
											:class="{ seen: receipt(entry, room) === 3 }"
											aria-label="Message delivery information"
											@click="messageInfo(entry)"
										>
											{{ receipt(entry, room) === 1 ? "✓" : "✓✓" }}</button
										><button
											aria-label="Message actions"
											@click="
												entryMenu = entry;
												overlay = 'message';
											"
										>
											⌄
										</button>
									</footer>
								</template>
							</article>
							<article v-for="row in pendingMessages" class="message mine pending">
								<p>{{ row.payload.payload.body }}</p>
								<small>{{
									row.status === "attention"
										? "Needs attention — open Outbox"
										: "Waiting to send"
								}}</small>
							</article>
						</div>
						<form v-if="room.space.can_post" class="composer" @submit.prevent="send">
							<div v-if="reply" class="reply-preview">
								Replying to {{ reply.author_name
								}}<button
									type="button"
									aria-label="Cancel reply"
									@click="reply = null"
								>
									×</button
								><small>{{ reply.body.slice(0, 120) }}</small>
							</div>
							<div v-if="messageFiles.length" class="file-preview">
								<span v-for="(file, index) in messageFiles"
									>{{ file.name
									}}<button
										type="button"
										:aria-label="`Remove ${file.name}`"
										@click="messageFiles.splice(index, 1)"
									>
										×
									</button></span
								>
							</div>
							<div class="compose-line">
								<label class="icon-button attach-button" aria-label="Attach files"
									><SvgIcon name="clip" /><input
										type="file"
										multiple
										:accept="acceptFiles"
										@change="chooseMessageFiles" /></label
								><textarea
									v-model="draft"
									aria-label="Message"
									placeholder="Message"
									rows="1"
									maxlength="12000"
									@keydown.ctrl.enter.prevent="send"
								></textarea
								><button
									type="button"
									class="icon-button"
									aria-label="Mention someone"
									@click="showMentions = !showMentions"
								>
									@</button
								><button
									class="send-button"
									aria-label="Send message"
									:disabled="sending || !draft.trim()"
								>
									➤
								</button>
							</div>
							<MentionPicker
								v-if="showMentions"
								:members="room.space.members"
								@choose="
									draft += mention($event);
									showMentions = false;
								"
							/>
						</form>
						<p v-else class="read-only">
							{{
								room.space.archived
									? "This conversation is archived."
									: "You have viewing access."
							}}
						</p>
					</template>
					<template v-else
						><div class="section-heading">
							<h2>{{ roomTab }}</h2>
							<button
								v-if="room.space.can_post"
								class="primary compact"
								@click="createItem(tabKind(roomTab))"
							>
								+ Create
							</button>
						</div>
						<WorkCard
							v-for="item in roomItems"
							:key="item.name"
							:item="item"
							:user="user"
							@open="openItem"
							@status="changeTask"
						/>
						<p v-if="!roomItems.length" class="empty-inline">
							Nothing here yet.
						</p></template
					>
				</template>

				<p v-else-if="roomId" class="empty-inline">
					{{
						online
							? "Opening conversation…"
							: "Open this conversation online once to save it for offline use."
					}}
				</p>
				<template v-else-if="view === 'chats'">
					<div class="list-toolbar">
						<label class="search-field"
							><SvgIcon name="search" /><input
								v-model="search"
								placeholder="Search conversations"
								aria-label="Find a conversation" /></label
						><button
							class="icon-button"
							aria-label="New conversation"
							@click="newSpace"
						>
							<SvgIcon name="plus" />
						</button>
					</div>
					<div class="filter-chips">
						<button
							v-for="value in ['All', 'Unread', 'Archived']"
							:class="{ active: chatFilter === value }"
							@click="chatFilter = value"
						>
							{{ value }}
						</button>
					</div>
					<section class="chat-list">
						<button
							v-for="space in spaces"
							:key="space.name"
							class="chat-row"
							@click="navigate({ space: space.name })"
						>
							<span class="avatar" :style="avatarStyle(space.title)">{{
								initials(space.title)
							}}</span
							><span class="chat-copy"
								><strong>{{ space.title }}</strong
								><small>{{
									space.last_entry?.body || "Start a conversation"
								}}</small
								><em v-if="space.parent_space"
									>Area ·
									{{
										home.spaces.find((p) => p.name === space.parent_space)
											?.title
									}}</em
								></span
							><span class="chat-trailing"
								><small>{{ prettyDate(space.last_entry?.creation) }}</small
								><b v-if="space.unread" class="count-badge">{{ space.unread }}</b
								><small v-if="space.access_level === 'Viewer'"
									>View only</small
								></span
							>
						</button>
						<p v-if="!spaces.length" class="empty-inline">
							{{
								home
									? "No conversations in this view."
									: "Sign in online once to load your conversations."
							}}
						</p>
					</section>
					<button class="fab" aria-label="Create conversation" @click="newSpace">
						<SvgIcon name="plus" />
					</button>
				</template>

				<template v-else-if="view === 'trackers'">
					<div class="dashboard-intro">
						<p class="eyebrow">KEEP THINGS MOVING</p>
						<h2>My trackers</h2>
					</div>
					<div class="stats-grid">
						<button class="stat stat-blue" @click="trackerFilter = 'All'">
							<SvgIcon name="layers" /><strong>{{ allTrackers.length }}</strong
							><small>All trackers</small></button
						><button class="stat stat-red" @click="trackerFilter = 'My actions'">
							<SvgIcon name="person" /><strong>{{ myPending.length }}</strong
							><small>Pending with me</small></button
						><button class="stat stat-green" @click="trackerFilter = 'Completed'">
							<SvgIcon name="check" /><strong>{{
								allTrackers.filter((t) => t.status === "Completed").length
							}}</strong
							><small>Completed</small>
						</button>
					</div>
					<div class="section-heading">
						<h3>Your trackers</h3>
						<select v-model="trackerFilter" aria-label="Filter trackers">
							<option
								v-for="f in [
									'Open',
									'All',
									'My actions',
									'Waiting on others',
									'Completed',
								]"
							>
								{{ f }}
							</option>
						</select>
					</div>
					<section
						v-for="group in trackerGroups"
						:key="group.name"
						class="tracker-group"
					>
						<h3>
							{{ group.title }}<span>{{ group.items.length }}</span>
						</h3>
						<WorkCard
							v-for="item in group.items"
							:key="item.name"
							:item="item"
							:user="user"
							@open="openItem"
						/>
					</section>
					<p v-if="!trackerGroups.length" class="empty-inline">
						No trackers in this view.
					</p>
					<button class="fab" aria-label="Create tracker" @click="pickSpace('Tracker')">
						<SvgIcon name="plus" />
					</button>
				</template>

				<template v-else-if="view === 'tasks' || view === 'calendar'">
					<div class="section-heading">
						<h2>{{ view === "tasks" ? "My tasks" : "Calendar" }}</h2>
						<input
							v-if="view === 'calendar'"
							v-model="workDate"
							type="date"
							aria-label="Calendar date"
							@change="refreshWork"
						/>
					</div>
					<div v-if="view === 'tasks'" class="filter-chips">
						<button
							v-for="f in ['Open', 'Today', 'All']"
							:class="{ active: taskFilter === f }"
							@click="taskFilter = f"
						>
							{{ f }}
						</button>
					</div>
					<WorkCard
						v-for="item in visibleWork"
						:key="item.name"
						:item="item"
						:user="user"
						@open="openItem"
						@status="changeTask"
					/>
					<p v-if="!visibleWork.length" class="empty-inline">
						Nothing scheduled in this view.
					</p>
					<button
						class="fab"
						:aria-label="view === 'tasks' ? 'Create task' : 'Create event'"
						@click="pickSpace(view === 'tasks' ? 'Task' : 'Event')"
					>
						<SvgIcon name="plus" />
					</button>
				</template>

				<template v-else-if="view === 'mentions'">
					<div class="section-heading">
						<h2>My mentions</h2>
						<label class="inline-check"
							><input
								v-model="unreadMentions"
								type="checkbox"
								@change="loadMentions()"
							/>Unread only</label
						>
					</div>
					<button
						v-for="entry in mentions.mentions || []"
						class="mention-row card"
						@click="openMention(entry)"
					>
						<small>{{ entry.space_title }} · {{ entry.author_name }}</small>
						<p>{{ entry.body }}</p>
						<span v-if="entry.unread" class="count-badge">New</span></button
					><button
						v-if="mentions.next_cursor"
						class="secondary"
						@click="loadMentions(mentions.next_cursor)"
					>
						More mentions
					</button>
					<p v-if="!mentions.mentions?.length" class="empty-inline">
						You’re all caught up.
					</p>
				</template>

				<template v-else-if="view === 'search'">
					<form class="search-form" @submit.prevent="runSearch">
						<label
							>Search your conversations<input
								v-model="query"
								minlength="2"
								required
								placeholder="Messages, tasks, trackers or files"
								autofocus
						/></label>
						<div class="row">
							<select v-model="searchKind" aria-label="Search category">
								<option
									v-for="kind in [
										'All',
										'Messages',
										'Tasks',
										'Trackers',
										'Files',
									]"
								>
									{{ kind }}
								</option></select
							><button class="primary">Search</button>
						</div>
					</form>
					<button
						v-for="result in searchResults.results || []"
						class="card search-result"
						@click="openSearchResult(result)"
					>
						<small>{{ result.kind }} · {{ result.space_title }}</small
						><strong>{{ result.title }}</strong></button
					><button
						v-if="searchResults.next_cursor"
						class="secondary"
						@click="runSearch(searchResults.next_cursor)"
					>
						More results
					</button>
					<p v-if="searched && !searchResults.results?.length" class="empty-inline">
						No matching results.
					</p>
				</template>

				<template v-else-if="view === 'outbox'">
					<div class="section-heading">
						<h2>
							Outbox <span>{{ queue.length }}</span>
						</h2>
						<button class="secondary compact" @click="syncNow">Retry pending</button>
					</div>
					<p class="muted">
						Saved on this device. A conflicting change needs your review before it can
						be sent.
					</p>
					<article v-for="row in queue" class="card outbox-row">
						<span
							class="status-pill"
							:class="row.status === 'attention' ? 'needs-me' : ''"
							>{{
								row.status === "attention" ? "Needs attention" : "Waiting to send"
							}}</span
						>
						<h3>
							{{
								row.payload.payload?.title ||
								row.payload.payload?.body ||
								row.payload.note ||
								row.method.replaceAll("_", " ")
							}}
						</h3>
						<p>{{ row.error }}</p>
						<small>{{ prettyDate(new Date(row.created).toISOString(), true) }}</small>
						<div class="row">
							<button
								v-if="row.status === 'attention'"
								class="secondary"
								@click="reviewQueued(row)"
							>
								Review current record</button
							><button class="text-button danger" @click="discardQueued(row)">
								Discard
							</button>
						</div>
					</article>
					<p v-if="!queue.length" class="empty-inline">Everything has been sent.</p>
				</template>

				<template v-else-if="view === 'settings'">
					<section class="profile-card card">
						<span class="avatar">{{ initials(fullName || user) }}</span>
						<div>
							<h2>{{ fullName || user }}</h2>
							<p>{{ user }}</p>
							<small>SF Tasks PWA · separate from the Android app</small>
						</div>
					</section>
					<section class="card settings-card">
						<h3>Appearance</h3>
						<label
							>Theme<select v-model="settings.theme" @change="saveSettings">
								<option>System</option>
								<option>Light</option>
								<option>Dark</option>
							</select></label
						>
					</section>
					<section class="card settings-card">
						<h3>Notifications</h3>
						<p class="muted">{{ pushStatus }}</p>
						<button class="secondary" @click="enablePush">
							Enable / refresh notifications</button
						><label
							>Notify me about<select
								v-model="settings.notifications"
								@change="saveSettings"
							>
								<option value="All">All activity</option>
								<option value="Mentions">Mentions and assignments</option>
								<option value="Mute">Mute</option>
							</select></label
						>
						<div class="form-grid">
							<label
								>Quiet hours from<input
									v-model="settings.quiet_from"
									type="time"
									@change="saveSettings" /></label
							><label
								>Until<input
									v-model="settings.quiet_until"
									type="time"
									@change="saveSettings"
							/></label>
						</div>
					</section>
					<section class="card settings-card">
						<h3>Offline & storage</h3>
						<p class="muted">{{ storageInfo }}</p>
						<button class="secondary" @click="persistStorage">
							Keep offline data on this device</button
						><button class="secondary" @click="navigate({ view: 'outbox' })">
							Outbox · {{ queue.length }}</button
						><button
							class="secondary"
							@click="
								overlay = 'saved-files';
								loadSavedFiles();
							"
						>
							Saved files
						</button>
					</section>
					<section class="card settings-card">
						<h3>Install & updates</h3>
						<p class="muted">
							{{
								installPrompt
									? "Install a separate SF Tasks PWA icon on this device."
									: "Use your browser’s “Install app” or “Add to Home Screen” menu."
							}}
						</p>
						<button v-if="installPrompt" class="primary" @click="install">
							Install SF Tasks PWA</button
						><button class="secondary" @click="checkUpdate">Check for updates</button>
					</section>
					<button class="secondary danger wide" @click="overlay = 'logout'">
						Sign out & remove offline data
					</button>
				</template>
			</main>
			<nav v-if="!roomId && !selected" class="bottom-nav" aria-label="Main navigation">
				<button
					v-for="tab in mainTabs"
					:class="{ active: view === tab.view }"
					@click="navigate({ view: tab.view })"
				>
					<SvgIcon :name="tab.icon" /><span>{{ tab.title }}</span
					><b v-if="tab.view === 'mentions' && mentions.unread_count">{{
						mentions.unread_count
					}}</b>
				</button>
			</nav>
		</template>

		<dialog ref="dialogElement" class="full-screen-form" @cancel.prevent="closeOverlay">
			<header class="form-header">
				<button class="icon-button" aria-label="Close form" @click="closeOverlay">
					←
				</button>
				<h2>{{ overlayTitle }}</h2>
				<span class="form-spacer"></span
				><button
					v-if="
						['item', 'space', 'progress', 'files', 'share', 'edit-message'].includes(
							overlay,
						)
					"
					class="primary compact"
					:disabled="busy"
					@click="submitOverlay"
				>
					{{ busy ? "Saving…" : "Save" }}
				</button>
			</header>
			<p v-if="formError" class="error-banner" role="alert">{{ formError }}</p>
			<form class="form-content" @submit.prevent="submitOverlay">
				<template v-if="overlay === 'item'">
					<p class="muted">{{ room?.space.title }} · {{ form.item_kind }}</p>
					<label
						>Title<input
							v-model="form.title"
							required
							maxlength="160"
							placeholder="What needs to happen?" /></label
					><label
						>Description<textarea
							v-model="form.description"
							rows="3"
							maxlength="12000"
							placeholder="A little context for your team"
						></textarea>
					</label>
					<div class="form-grid">
						<label
							v-if="
								form.item_kind !== 'Tracker' ||
								form.item_data.assignment_mode === 'Single'
							"
							>Assigned to<select v-model="form.assignee">
								<option v-for="p in contributors" :value="p.user">
									{{ p.full_name }}
								</option>
							</select></label
						><label
							>Priority<select v-model="form.priority">
								<option v-for="p in priorities">{{ p }}</option>
							</select></label
						>
					</div>
					<template v-if="form.item_kind === 'Tracker'">
						<section class="form-section">
							<h3>How will you measure progress?</h3>
							<label
								>Measure progress by<select
									v-model="form.item_data.scale"
									@change="trackerScaleChanged"
								>
									<option>Status</option>
									<option>Stages</option>
									<option>Percentage</option>
									<option>Number</option>
								</select></label
							>
							<template v-if="['Status', 'Stages'].includes(form.item_data.scale)"
								><label
									>Responsibility<select
										v-model="form.item_data.assignment_mode"
									>
										<option value="Single">
											One person for the entire tracker
										</option>
										<option value="Stages">
											Assign each stage separately
										</option>
									</select></label
								>
								<div
									v-for="(stage, index) in form.item_data.stages"
									:key="stage.key"
									class="stage-editor"
								>
									<div class="section-heading">
										<strong
											>{{
												form.item_data.scale === "Status"
													? "Status"
													: "Stage"
											}}
											{{ index + 1 }}</strong
										><button
											type="button"
											class="text-button danger"
											@click="form.item_data.stages.splice(index, 1)"
										>
											Remove
										</button>
									</div>
									<label
										>Name<input
											v-model="stage.label"
											required
											maxlength="100"
											placeholder="Enter your own stage name" /></label
									><label v-if="form.item_data.scale === 'Stages'"
										>Progress percentage<input
											v-model.number="stage.position"
											type="number"
											min="0"
											max="100"
											required /></label
									><label v-if="form.item_data.assignment_mode === 'Stages'"
										>Responsible person<select
											v-model="stage.assignee"
											required
										>
											<option value="">Choose a person</option>
											<option v-for="p in contributors" :value="p.user">
												{{ p.full_name }}
											</option>
										</select></label
									>
								</div>
								<button type="button" class="secondary" @click="addStage">
									+ Add
									{{ form.item_data.scale === "Status" ? "status" : "stage" }}
								</button></template
							>
							<template v-else
								><div v-if="form.item_data.scale === 'Number'" class="form-grid">
									<label
										>Starting number<input
											v-model.number="form.item_data.minimum"
											type="number"
											required /></label
									><label
										>Target number<input
											v-model.number="form.item_data.maximum"
											type="number"
											required /></label
									><label
										>Unit<input
											v-model="form.item_data.unit"
											maxlength="40"
											placeholder="e.g. meals"
									/></label></div
							></template>
						</section>
						<label
							>Next action<textarea
								v-model="form.item_data.next_action"
								rows="2"
								maxlength="500"
							></textarea>
						</label>
						<div class="form-grid">
							<label
								>Needs attention from<input
									v-model="form.item_data.attention_date"
									type="date" /></label
							><label
								>Until (optional)<input
									v-model="form.item_data.attention_until"
									type="date"
							/></label>
						</div>
						<label
							>Reminder time (optional)<input
								v-model="form.item_data.reminder_time"
								type="time"
							/><small
								>Without a time, reminders are scheduled for 9 AM in the ERP
								timezone.</small
							></label
						>
					</template>
					<template v-if="form.item_kind === 'Task'"
						><div class="form-grid">
							<label>Start date<input v-model="form.from_date" type="date" /></label
							><label
								>End of action window<input
									v-model="form.until_date"
									type="date" /></label
							><label>Deadline<input v-model="form.deadline" type="date" /></label
							><label
								>Reminder time<input
									v-model="form.item_data.reminder_time"
									type="time" /></label
							><label
								>Repeat<select v-model="form.repeat_pattern">
									<option>None</option>
									<option>Daily</option>
									<option>Weekly</option>
									<option>Monthly</option>
								</select></label
							><label v-if="form.repeat_pattern !== 'None'"
								>Repeat until<input v-model="form.repeat_until" type="date"
							/></label>
						</div>
						<section class="form-section">
							<div class="section-heading">
								<h3>Subtasks</h3>
								<button type="button" class="text-button" @click="addSubtask">
									+ Add
								</button>
							</div>
							<div
								v-for="(sub, index) in form.item_data.subtasks"
								:key="sub.id"
								class="stage-editor"
							>
								<label
									>Subtask title<input
										v-model="sub.title"
										required
										maxlength="160"
								/></label>
								<div class="form-grid">
									<label
										>Assigned to<select v-model="sub.assignee">
											<option value="">Unassigned</option>
											<option v-for="p in contributors" :value="p.user">
												{{ p.full_name }}
											</option>
										</select></label
									><label
										>Deadline<input v-model="sub.deadline" type="date"
									/></label>
								</div>
								<button
									type="button"
									class="text-button danger"
									@click="form.item_data.subtasks.splice(index, 1)"
								>
									Remove
								</button>
							</div>
						</section></template
					>
					<template v-if="form.item_kind === 'Event'"
						><div class="form-grid">
							<label
								>Starts<input
									v-model="form.start_at"
									type="datetime-local"
									required /></label
							><label
								>Ends<input v-model="form.end_at" type="datetime-local" required
							/></label>
						</div>
						<label>Location<input v-model="form.location" maxlength="160" /></label>
						<fieldset>
							<legend>Participants</legend>
							<label v-for="p in room?.space.members || []" class="inline-check"
								><input
									v-model="form.participants"
									type="checkbox"
									:value="p.user"
								/>{{ p.full_name }}</label
							>
						</fieldset></template
					>
					<template v-if="form.item_kind === 'List'"
						><section
							v-for="(row, index) in form.item_data.rows"
							:key="row.id"
							class="stage-editor"
						>
							<label
								>Entry {{ index + 1
								}}<input v-model="row.content" required maxlength="2000"
							/></label>
							<div class="row">
								<label
									>Within<select v-model="row.parent_id">
										<option :value="null">Top level</option>
										<option
											v-for="parent in form.item_data.rows.filter(
												(p) => p.id !== row.id,
											)"
											:value="parent.id"
										>
											{{ parent.content || "Untitled entry" }}
										</option>
									</select></label
								><label
									>Priority<select v-model="row.priority">
										<option v-for="p in priorities">{{ p }}</option>
									</select></label
								>
							</div>
							<button
								type="button"
								class="text-button danger"
								@click="removeListRow(index)"
							>
								Remove
							</button>
						</section>
						<button
							type="button"
							class="secondary"
							@click="
								form.item_data.rows.push({
									id: id(),
									content: '',
									completed: false,
									parent_id: null,
									priority: 'Medium',
								})
							"
						>
							+ Add list entry
						</button></template
					>
				</template>
				<template v-if="overlay === 'space'">
					<label v-if="!spaceForm.name && !spaceForm.parent_space"
						>Conversation type<select v-model="spaceForm.space_kind">
							<option>Direct</option>
							<option>Group</option>
							<option>Workspace</option>
						</select></label
					><label v-if="spaceForm.space_kind !== 'Direct'"
						>Name<input
							v-model="spaceForm.title"
							required
							maxlength="160"
							placeholder="Name your conversation" /></label
					><label v-if="!spaceForm.parent_space"
						>Find people<input
							v-model="peopleQuery"
							placeholder="Type a name or email"
							@input="findPeople" /></label
					><template v-if="spaceForm.space_kind === 'Direct'"
						><button
							type="button"
							v-for="person in directory.filter((p) => p.name !== user)"
							class="person-pick"
							:class="{ selected: directPerson === person.name }"
							@click="directPerson = person.name"
						>
							{{ person.full_name }}<small>{{ person.name }}</small>
						</button></template
					><template v-else-if="!spaceForm.parent_space"
						><div
							v-for="p in directory.filter(
								(p) => !spaceForm.members.some((m) => m.user === p.name),
							)"
							class="person-pick"
						>
							<span>{{ p.full_name }}</span
							><button
								type="button"
								class="text-button"
								@click="
									spaceForm.members.push({
										user: p.name,
										access_level: 'Member',
									})
								"
							>
								Add
							</button>
						</div>
						<h3>Members</h3>
						<div v-for="(member, index) in spaceForm.members" class="member-row">
							<span>{{ person(member.user) }}</span
							><select
								v-model="member.access_level"
								:aria-label="`Access for ${person(member.user)}`"
							>
								<option v-for="level in ['Owner', 'Manager', 'Member', 'Viewer']">
									{{ level }}
								</option></select
							><button
								type="button"
								class="text-button danger"
								@click="spaceForm.members.splice(index, 1)"
							>
								Remove
							</button>
						</div></template
					><label v-if="home?.projects.length && spaceForm.space_kind !== 'Direct'"
						>Linked project (optional)<select v-model="spaceForm.project">
							<option value="">No project</option>
							<option v-for="p in home.projects" :value="p.name">
								{{ p.project_name }}
							</option>
						</select></label
					><label
						v-if="spaceForm.name && room?.space.access_level === 'Owner'"
						class="inline-check"
						><input v-model="spaceForm.archived" type="checkbox" />Archive
						conversation</label
					><button
						v-if="spaceForm.name && room?.space.can_manage"
						type="button"
						class="secondary"
						@click="newArea"
					>
						Create a subarea
					</button>
				</template>
				<template v-if="overlay === 'progress'"
					><h3>{{ selected.title }}</h3>
					<label v-if="['Status', 'Stages'].includes(selected.item_data.scale)"
						>Current {{ selected.item_data.scale === "Status" ? "status" : "stage"
						}}<select v-model="progress.stage">
							<option :value="null">Not started</option>
							<option v-for="stage in selected.item_data.stages" :value="stage.key">
								{{ stage.label }}
							</option>
						</select></label
					><label v-else
						>Current value<input
							v-model.number="progress.value"
							type="number"
							:min="selected.item_data.minimum"
							:max="selected.item_data.maximum"
							step="any"
							required /></label
					><label
						>Tracker outcome<select v-model="progress.outcome">
							<option>Open</option>
							<option>Completed</option>
							<option>Failed</option>
						</select></label
					><label
						>Progress message<textarea
							v-model="progress.note"
							required
							rows="3"
							maxlength="12000"
							placeholder="What changed?"
						></textarea></label
					><label
						>Effective date & time (optional)<input
							v-model="progress.effective_at"
							type="datetime-local" /></label
					><label
						>Next action<textarea
							v-model="progress.next_action"
							maxlength="500"
							rows="2"
						></textarea>
					</label>
					<div class="form-grid">
						<label
							>Attention date<input
								v-model="progress.attention_date"
								type="date" /></label
						><label
							>Until<input v-model="progress.attention_until" type="date"
						/></label>
					</div>
					<label v-if="selected.can_add_files"
						>Supporting files<input
							type="file"
							multiple
							:accept="acceptFiles"
							@change="formFiles = Array.from($event.target.files)" /></label
				></template>
				<template v-if="overlay === 'files'"
					><h3>{{ selected.title }}</h3>
					<label
						>Supporting files<input
							type="file"
							required
							multiple
							:accept="acceptFiles"
							@change="formFiles = Array.from($event.target.files)"
					/></label>
					<p class="muted">Up to five files · 10 MB each.</p>
					<label
						>Note (optional)<textarea
							v-model="fileNote"
							rows="3"
							maxlength="12000"
						></textarea></label
				></template>
				<template v-if="overlay === 'share'"
					><p class="muted">
						Share this item without granting access to the rest of the chat.
					</p>
					<label>Find a person<input v-model="peopleQuery" @input="findPeople" /></label>
					<div
						v-for="p in directory.filter(
							(p) => !shares.some((s) => s.user === p.name),
						)"
						class="person-pick"
					>
						<span>{{ p.full_name }}</span
						><button
							type="button"
							class="text-button"
							@click="shares.push({ user: p.name, access: 'View' })"
						>
							Add
						</button>
					</div>
					<div v-for="(p, index) in shares" class="member-row">
						<span>{{ person(p.user) }}</span
						><select v-model="p.access">
							<option>View</option>
							<option>Update</option></select
						><button
							type="button"
							class="text-button danger"
							@click="shares.splice(index, 1)"
						>
							Remove
						</button>
					</div></template
				>
				<template v-if="overlay === 'message'"
					><p>{{ entryMenu.body }}</p>
					<div class="action-menu">
						<button
							type="button"
							@click="
								reply = entryMenu;
								closeOverlay();
							"
						>
							Reply</button
						><button
							v-if="entryMenu.can_edit"
							type="button"
							@click="
								editText = entryMenu.raw_body || entryMenu.body;
								overlay = 'edit-message';
							"
						>
							Edit message</button
						><button
							v-if="entryMenu.can_remove"
							type="button"
							class="danger"
							@click="removeMessage"
						>
							Remove message</button
						><button
							v-for="kind in ['Task', 'Tracker', 'Event', 'List']"
							type="button"
							@click="createItem(kind, entryMenu)"
						>
							Create {{ kind.toLowerCase() }}
						</button>
					</div></template
				>
				<template v-if="overlay === 'edit-message'"
					><label
						>Message<textarea
							v-model="editText"
							required
							rows="5"
							maxlength="12000"
						></textarea></label
					><MentionPicker
						:members="room?.space.members || []"
						@choose="editText += mention($event)"
				/></template>
				<template v-if="overlay === 'room-notifications'"
					><h3>{{ room?.space.title }}</h3>
					<label
						>Notifications for this conversation<select
							v-model="settings.chats[roomId]"
							@change="saveSettings"
						>
							<option :value="undefined">Use general setting</option>
							<option value="All">All activity</option>
							<option value="Mentions">Mentions and assignments</option>
							<option value="Mute">Mute</option>
						</select></label
					>
					<p class="muted">
						This changes notifications for your browser only.
					</p></template
				>
				<template v-if="overlay === 'receipts'"
					><div v-for="p in receipts" class="member-row">
						<span>{{ p.full_name }}</span
						><strong :class="{ seen: p.status === 3 }">{{
							p.status === 3 ? "Read" : p.status === 2 ? "Delivered" : "Sent"
						}}</strong>
					</div>
					<p v-if="!receipts.length" class="muted">No other recipients.</p></template
				>
				<template v-if="overlay === 'pick-space'"
					><p class="muted">
						Choose the conversation for this {{ createKind.toLowerCase() }}.
					</p>
					<button
						type="button"
						v-for="space in home?.spaces.filter((s) => s.can_post) || []"
						class="person-pick"
						@click="createInSpace(space.name)"
					>
						{{ space.title }}<span>›</span>
					</button></template
				>
				<template v-if="overlay === 'schedule'"
					><label
						>Action<select v-model="schedule.action">
							<option value="postpone">Move the start date later</option>
							<option value="snooze">Snooze until</option>
						</select></label
					><label>Date<input v-model="schedule.date" type="date" required /></label
					><button class="primary">Save schedule</button
					><button
						type="button"
						class="secondary"
						@click="
							schedule.date = null;
							saveSchedule();
						"
					>
						Clear snooze
					</button></template
				>
				<template v-if="overlay === 'history'"
					><article v-for="entry in history" class="history-row">
						<small
							>{{ entry.author_name }} ·
							{{ prettyDate(entry.creation, true) }}</small
						>
						<p>{{ entry.body }}</p>
					</article></template
				>
				<template v-if="overlay === 'file-preview'"
					><PdfPreview
						v-if="previewType === 'application/pdf'"
						:key="previewURL"
						:url="previewURL"
					/><img
						v-else-if="previewType.startsWith('image/')"
						class="file-image"
						:src="previewURL"
						:alt="previewName"
					/>
					<p v-else class="muted">
						Download this file to open it in your preferred app.
					</p>
					<a class="primary" :href="previewURL" :download="previewName"
						>Download {{ previewName }}</a
					></template
				>
				<template v-if="overlay === 'saved-files'"
					><p class="muted">Saved only for this account on this device.</p>
					<div v-for="file in savedFiles" class="member-row">
						<button type="button" class="text-button" @click="openSavedFile(file)">
							{{ file.name }}</button
						><button
							type="button"
							class="text-button danger"
							@click="removeSavedFile(file)"
						>
							Remove
						</button>
					</div>
					<p v-if="!savedFiles.length">No files saved.</p></template
				>
				<template v-if="overlay === 'logout'"
					><h3>Sign out?</h3>
					<p>
						This removes this account’s offline conversations, drafts, files and unsent
						changes from this device.
					</p>
					<p v-if="queue.length" class="error">
						You have {{ queue.length }} unsent changes. Send or review them before
						signing out.
					</p>
					<button type="button" class="primary danger" @click="logout">
						Sign out and remove local data
					</button></template
				>
				<template v-if="overlay === 'reset'"
					><label
						>Account email<input v-model="resetEmail" type="email" required /></label
					><button class="primary">Send password reset email</button></template
				>
				<button
					v-if="
						['item', 'space', 'progress', 'files', 'share', 'edit-message'].includes(
							overlay,
						)
					"
					class="primary wide form-save"
					:disabled="busy"
				>
					{{ busy ? "Saving…" : "Save" }}
				</button>
			</form>
		</dialog>
	</div>
</template>

<script setup>
import {
	computed,
	defineAsyncComponent,
	defineComponent,
	h,
	nextTick,
	onMounted,
	onUnmounted,
	ref,
	watch,
} from "vue";
import ProgressBar from "./ProgressBar.vue";
import {
	OPEN,
	id,
	copy,
	pendingWith,
	progressOf,
	trackerState,
	receipt,
	prettyDate,
	safeFileURL,
	filterTrackers,
	newItem,
	itemPayload,
	mergeConversation,
} from "./model.js";
import { call, request, session, filePayload, PWA_API } from "./api.js";
import * as store from "./storage.js";
import { flush } from "./sync.js";

const PdfPreview = defineAsyncComponent({
	loader: () => import("./PdfPreview.vue"),
	errorComponent: {
		render: () =>
			h(
				"p",
				{ class: "muted", role: "status" },
				"The PDF preview is unavailable. Download the file to open it.",
			),
	},
});

const user = ref(null),
	allowed = ref(false),
	fullName = ref(""),
	home = ref(null),
	room = ref(null),
	work = ref({}),
	online = ref(navigator.onLine),
	serverReachable = ref(true),
	authExpired = ref(false),
	error = ref(""),
	notice = ref(""),
	busy = ref(false),
	loginError = ref("");
const credentials = ref({ usr: "", pwd: "" }),
	resetEmail = ref(""),
	route = ref(readRoute()),
	roomTab = ref("Chat"),
	detailTab = ref("Workflow"),
	selected = ref(null),
	itemOnly = ref(false);
const view = computed(() => route.value.view || "chats"),
	roomId = computed(() => route.value.space || "");
const search = ref(""),
	chatFilter = ref("All"),
	trackerFilter = ref("Open"),
	taskFilter = ref("Open"),
	workDate = ref(localDay());
const draft = ref(""),
	messageFiles = ref([]),
	reply = ref(null),
	sending = ref(false),
	queue = ref([]),
	thread = ref(null),
	showMentions = ref(false);
const form = ref({}),
	spaceForm = ref({}),
	progress = ref({}),
	shares = ref([]),
	schedule = ref({}),
	formFiles = ref([]),
	fileNote = ref(""),
	peopleQuery = ref(""),
	directory = ref([]),
	directPerson = ref("");
const comments = ref({}),
	commentDraft = ref(""),
	trackerFiles = ref({}),
	history = ref([]),
	mentions = ref({}),
	unreadMentions = ref(false),
	receipts = ref([]),
	entryMenu = ref({}),
	editText = ref("");
const query = ref(""),
	searchKind = ref("All"),
	searchResults = ref({}),
	searched = ref(false),
	createKind = ref("Task"),
	savedFiles = ref([]);
const settings = ref({
		theme: "System",
		notifications: "All",
		quiet_from: "",
		quiet_until: "",
		chats: {},
	}),
	dark = ref(matchMedia("(prefers-color-scheme: dark)").matches),
	storageInfo = ref("Saved data opens instantly; unsent work stays in the Outbox."),
	pushStatus = ref("Notifications are not enabled for this browser.");
const previewURL = ref(""),
	previewName = ref(""),
	previewType = ref("");
const overlay = ref(""),
	dialogElement = ref(null),
	formError = ref(""),
	installPrompt = ref(null),
	updateReady = ref(false);
let registration,
	timer,
	searchSequence = 0,
	refreshing = false,
	syncing = false,
	draftSave = Promise.resolve(),
	sequence = 0,
	activeView = 0,
	restoringDraft = false;
const acceptFiles = ".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.csv,.docx,.xlsx";
const priorities = ["Very low", "Low", "Medium", "High", "Very high"];
const mainTabs = [
	{ view: "chats", title: "Chats", icon: "chat" },
	{ view: "tasks", title: "Tasks", icon: "check" },
	{ view: "trackers", title: "Trackers", icon: "layers" },
	{ view: "mentions", title: "Mentions", icon: "at" },
	{ view: "calendar", title: "Calendar", icon: "calendar" },
];
const resolvedTheme = computed(() =>
	settings.value.theme === "System"
		? dark.value
			? "dark"
			: "light"
		: settings.value.theme.toLowerCase(),
);
const spaces = computed(() =>
	[...(home.value?.spaces || [])]
		.sort((a, b) =>
			(b.last_entry?.creation || b.modified || "").localeCompare(
				a.last_entry?.creation || a.modified || "",
			),
		)
		.filter(
			(s) =>
				(chatFilter.value === "Archived" ? s.archived : !s.archived) &&
				(chatFilter.value !== "Unread" || s.unread) &&
				(s.title + " " + (s.last_entry?.body || ""))
					.toLowerCase()
					.includes(search.value.toLowerCase()),
		),
);
const allTrackers = computed(() => work.value.trackers || []),
	myPending = computed(() =>
		allTrackers.value.filter((t) => pendingWith(t)?.user === user.value),
	);
const trackerGroups = computed(() => {
	const groups = new Map();
	for (const item of filterTrackers(allTrackers.value, trackerFilter.value, user.value)) {
		if (!groups.has(item.space))
			groups.set(item.space, { name: item.space, title: item.space_title, items: [] });
		groups.get(item.space).items.push(item);
	}
	return [...groups.values()];
});
const visibleWork = computed(() =>
	view.value === "calendar"
		? (work.value.calendar || []).filter((i) => {
				const start = String(i.start_at || i.from_date || "").slice(0, 10),
					end = String(i.end_at || i.until_date || start).slice(0, 10);
				return start <= workDate.value && end >= workDate.value;
			})
		: taskFilter.value === "Today"
			? (work.value.today || []).filter((i) => i.item_kind === "Task")
			: (taskFilter.value === "All"
					? work.value.tasks || work.value.open_progress || []
					: work.value.open_progress || []
				).filter((i) => i.item_kind === "Task"),
);
const roomItems = computed(() =>
	(room.value?.items || []).filter((i) => i.item_kind === tabKind(roomTab.value)),
);
const pendingMessages = computed(() =>
	queue.value.filter(
		(r) => r.method === "send_message" && r.payload.payload.space === roomId.value,
	),
);
const contributors = computed(() =>
	(room.value?.space.members || []).filter((p) => p.access_level !== "Viewer" && p.chat_enabled),
);
const pageTitle = computed(() =>
	selected.value
		? selected.value.item_kind
		: room.value && roomId.value
			? room.value.space.title
			: {
					chats: "SF Tasks PWA",
					tasks: "My tasks",
					trackers: "My trackers",
					calendar: "Calendar",
					mentions: "My mentions",
					settings: "Settings",
					outbox: "Outbox",
					search: "Search",
				}[view.value] || "SF Tasks PWA",
);
const overlayTitle = computed(
	() =>
		({
			item: `${form.value.name ? "Edit" : "New"} ${form.value.item_kind?.toLowerCase() || "work item"}`,
			space: spaceForm.value.name ? "Conversation settings" : "New conversation",
			progress: "Update progress",
			files: "Add supporting files",
			share: "Share item",
			message: "Message actions",
			"edit-message": "Edit message",
			receipts: "Message info",
			"room-notifications": "Conversation notifications",
			"pick-space": "Choose conversation",
			schedule: "Schedule task",
			history: "History",
			"file-preview": previewName.value || "File preview",
			"saved-files": "Saved files",
			logout: "Sign out",
			reset: "Reset password",
		})[overlay.value] || "SF Tasks",
);

function localDay() {
	return new Date().toLocaleDateString("en-CA");
}
function readRoute() {
	return Object.fromEntries(new URLSearchParams(location.search));
}
function navigate(value, replace = false) {
	const query = new URLSearchParams(
		Object.entries(value).filter(([, v]) => v != null && v !== ""),
	);
	window.history[replace ? "replaceState" : "pushState"](
		{},
		"",
		`/sf-tasks/${query.size ? "?" + query : ""}`,
	);
	route.value = readRoute();
	void loadRoute();
}
function goBack() {
	if (overlay.value) {
		closeOverlay();
		return;
	}
	if (selected.value) {
		navigate(roomId.value ? { space: roomId.value } : { view: "trackers" });
		return;
	}
	if (roomId.value || view.value === "search") {
		navigate({ view: "chats" });
		return;
	}
	navigate({ view: "chats" });
}
function person(uid, fallback) {
	return (
		home.value?.directory?.find((p) => p.name === uid)?.full_name ||
		room.value?.space.members?.find((p) => p.user === uid)?.full_name ||
		fallback ||
		uid ||
		""
	);
}
function initials(name) {
	return String(name || "SF")
		.split(/[\s.@]+/)
		.slice(0, 2)
		.map((p) => p[0])
		.join("")
		.toUpperCase();
}
function avatarStyle(title) {
	let n = 0;
	for (const c of title) n = (n + c.charCodeAt(0)) % 5;
	return { "--avatar-hue": [159, 220, 285, 31, 185][n] };
}
function dateRange(item) {
	const d = item.item_data || {};
	const start = item.item_kind === "Tracker" ? d.attention_date : item.from_date,
		end = item.item_kind === "Tracker" ? d.attention_until : item.until_date;
	return [
		start ? `${prettyDate(start)}${end && end !== start ? " – " + prettyDate(end) : ""}` : "",
		item.deadline ? "Due " + prettyDate(item.deadline) : "",
	]
		.filter(Boolean)
		.join(" · ");
}
function timeOnly(value) {
	return new Date(String(value).replace(" ", "T")).toLocaleTimeString([], {
		hour: "2-digit",
		minute: "2-digit",
	});
}
function tabKind(tab) {
	return { Tasks: "Task", Trackers: "Tracker", Lists: "List", Calendar: "Event" }[tab] || "Task";
}
function mention(p) {
	return `@[${p.full_name}](${p.user}) `;
}
function tell(message) {
	notice.value = message;
}
async function guarded(action) {
	try {
		error.value = "";
		return await action();
	} catch (e) {
		if (
			!e.status &&
			(["AbortError", "TimeoutError"].includes(e.name) ||
				(e instanceof TypeError && /fetch|network|connection/i.test(e.message)))
		) {
			serverReachable.value = false;
		} else error.value = e.message;
		if (e.status === 401) authExpired.value = true;
		return null;
	}
}
async function cached(method, args, key) {
	const account = user.value;
	try {
		const result = await call(method, args);
		if (account !== user.value) throw new Error("The signed-in account changed.");
		if (!args.before) await store.write(account, key, result);
		serverReachable.value = true;
		return result;
	} catch (e) {
		if (!e.status) {
			serverReachable.value = false;
			const saved = await store.read(account, key);
			if (saved && !args.before) return saved;
		}
		throw e;
	}
}
async function loadRoute({ cacheOnly = false } = {}) {
	const token = ++activeView;
	selected.value = null;
	itemOnly.value = false;
	room.value = null;
	roomTab.value = route.value.tab || "Chat";
	detailTab.value = "Workflow";
	if (!user.value || !allowed.value) return;
	const account = user.value;
	if (route.value.item) {
		const cachedItem = await store.read(account, `item:${route.value.item}`);
		if (token !== activeView) return;
		if (cachedItem) selected.value = cachedItem;
		const itemView = await store.read(account, `item-view:${route.value.item}`);
		if (token !== activeView) return;
		if (itemView) {
			room.value = itemView;
			itemOnly.value = itemView.item_only;
		}
		if (online.value && !cacheOnly)
			await guarded(async () => {
				const data = await fetchItemView(route.value.item, roomId.value);
				await store.write(account, `item-view:${route.value.item}`, data);
				if (token !== activeView) return;
				room.value = data;
				itemOnly.value = data.item_only;
				selected.value = data.items[0];
				await store.write(account, `item:${selected.value.name}`, selected.value);
			});
	} else if (roomId.value) {
		const name = roomId.value,
			snapshot = await store.read(account, `room:${name}`);
		if (token !== activeView) return;
		room.value = snapshot;
		await restoreDraft(name);
		await nextTick();
		if (thread.value) thread.value.scrollTop = thread.value.scrollHeight;
		if (online.value && !cacheOnly) await refreshRoom(!snapshot, token);
	} else if (view.value === "mentions" && !cacheOnly) await loadMentions();
	if (view.value === "outbox") await loadQueue();
}
async function fetchItemView(name, space) {
	if (space) {
		try {
			const data = await call("get_space", { name: space, item: name });
			const found = data.items.find((item) => item.name === name);
			if (found) return { ...data, items: [found], item_only: false };
		} catch (e) {
			if (e.status !== 403) throw e;
		}
	}
	return call("get_work_item", { name });
}
async function refreshHome() {
	const data = await cached("get_collaboration_home", {}, "home");
	home.value = data;
	directory.value = data.directory;
	for (const s of data.spaces.filter((s) => s.delivery_pending && s.last_entry)) {
		await call("mark_delivered", { space: s.name, entry: s.last_entry.name });
	}
}
async function refreshWork() {
	work.value = await request(PWA_API + "get_work", { date: workDate.value });
	await store.write(user.value, "work", work.value);
}
async function refreshRoom(scroll = false, token = activeView) {
	const name = roomId.value;
	if (!name || route.value.item) return;
	try {
		const data = await cached(
			"get_space",
			{ name, entry: route.value.entry || null },
			`room:${name}`,
		);
		if (token !== activeView || name !== roomId.value) return;
		room.value = mergeConversation(room.value, data);
		await store.write(user.value, `room:${name}`, room.value);
		for (const item of data.items) await store.write(user.value, `item:${item.name}`, item);
		await nextTick();
		if (scroll && thread.value) thread.value.scrollTop = thread.value.scrollHeight;
		if (route.value.entry)
			thread.value
				?.querySelector(`[data-entry="${CSS.escape(route.value.entry)}"]`)
				?.scrollIntoView({ block: "center" });
		await seenVisible();
	} catch (e) {
		if (e.status === 403) {
			await store.remove(user.value, `room:${name}`);
			room.value = null;
		}
		throw e;
	}
}
async function refresh() {
	if (
		!user.value ||
		!allowed.value ||
		!online.value ||
		refreshing ||
		document.visibilityState === "hidden"
	)
		return;
	refreshing = true;
	try {
		await sessionCheck();
		await Promise.all([refreshHome(), refreshWork()]);
		if (roomId.value && !selected.value) await refreshRoom(false);
		if (selected.value && !overlay.value) {
			const data = await fetchItemView(selected.value.name, roomId.value);
			selected.value = data.items[0];
			room.value = data;
			itemOnly.value = data.item_only;
			await store.write(user.value, `item:${selected.value.name}`, selected.value);
			await store.write(user.value, `item-view:${selected.value.name}`, data);
		}
	} catch (e) {
		if (!e.status) serverReachable.value = false;
		else if (e.status === 401) authExpired.value = true;
		else if (e.status === 403) {
			await store.clearSnapshots(user.value);
			home.value = null;
			work.value = {};
			room.value = null;
			selected.value = null;
			error.value = e.message;
		}
	} finally {
		refreshing = false;
	}
}
async function sessionCheck() {
	const s = await session();
	if (s.user !== user.value || !s.allowed) {
		authExpired.value = true;
		await store.clearSnapshots(user.value);
		if (!s.allowed && s.user === user.value) {
			allowed.value = false;
			await store.write(user.value, "identity", {
				full_name: fullName.value,
				blocked: true,
			});
		}
		throw Object.assign(new Error("Sign in to this account again to continue."), {
			status: 401,
		});
	}
	authExpired.value = false;
	serverReachable.value = true;
	return s;
}
async function login() {
	busy.value = true;
	loginError.value = "";
	try {
		await request("login", { usr: credentials.value.usr, pwd: credentials.value.pwd });
		credentials.value.pwd = "";
		await boot(true);
	} catch (e) {
		loginError.value = e.message;
	} finally {
		busy.value = false;
	}
}
function reauth() {
	credentials.value.usr = user.value;
	user.value = null;
	allowed.value = false;
	home.value = null;
	room.value = null;
	selected.value = null;
}
async function boot(force = false) {
	try {
		if (!force) {
			const account = await store.activeAccount();
			const identity = account ? await store.read(account, "identity") : null;
			if (account && !identity?.blocked) {
				user.value = account;
				allowed.value = true;
				fullName.value = identity?.full_name || account;
				await restore();
				await loadRoute({ cacheOnly: true });
			}
		}
		const s = await session();
		if (!s.user) {
			if (force) throw new Error("Please sign in.");
			if (user.value) authExpired.value = true;
			return;
		}
		user.value = s.user;
		allowed.value = s.allowed;
		fullName.value = s.full_name;
		if (!s.allowed) {
			await store.clearSnapshots(s.user);
			try {
				await store.write(s.user, "identity", { full_name: s.full_name, blocked: true });
			} catch {}
			return;
		}
		await store.activate(s.user);
		await store.write(s.user, "identity", { full_name: s.full_name, blocked: false });
		await restore();
		await loadRoute();
		await refresh();
		await syncNow();
	} catch (e) {
		if (!force && !e.status) {
			const account = await store.activeAccount();
			if (account && !(await store.read(account, "identity"))?.blocked) {
				user.value = account;
				allowed.value = true;
				fullName.value = (await store.read(account, "identity"))?.full_name || account;
				await restore();
				await loadRoute({ cacheOnly: true });
			}
		} else if (force) throw e;
	}
}
async function restore() {
	home.value = await store.read(user.value, "home");
	work.value = (await store.read(user.value, "work")) || {};
	settings.value = { ...settings.value, ...(await store.read(user.value, "settings")) };
	await loadQueue();
}
async function restoreDraft(name) {
	restoringDraft = true;
	draft.value = (await store.read(user.value, `draft:${name}`)) || "";
	await nextTick();
	restoringDraft = false;
}
watch(draft, (value) => {
	if (restoringDraft || !user.value || !roomId.value) return;
	const account = user.value,
		key = `draft:${roomId.value}`;
	draftSave = draftSave
		.then(() => store.write(account, key, value))
		.catch(() => {
			error.value =
				"Could not save your draft. Free some device storage before leaving this page.";
		});
});
watch(
	form,
	(value) => {
		if (overlay.value === "item" && user.value && !value.name) {
			const account = user.value,
				key = `form:${roomId.value}:${value.item_kind}`,
				snapshot = copy(value);
			draftSave = draftSave
				.then(() => store.write(account, key, snapshot))
				.catch(() => {
					formError.value =
						"Could not save this draft. Free device storage before leaving.";
				});
		}
	},
	{ deep: true },
);
watch(overlay, async (value) => {
	await nextTick();
	if (value && !dialogElement.value.open) {
		dialogElement.value.showModal();
		dialogElement.value.querySelector("input,textarea,select,button")?.focus();
	} else if (!value && dialogElement.value?.open) dialogElement.value.close();
});
function closeOverlay() {
	overlay.value = "";
	formError.value = "";
	if (previewURL.value) {
		URL.revokeObjectURL(previewURL.value);
		previewURL.value = "";
	}
}
async function loadQueue() {
	if (user.value) queue.value = await store.outbox(user.value);
}
async function queueAction(method, payload, clearDraft = null) {
	await store.enqueue(user.value, method, payload, clearDraft);
	await loadQueue();
	try {
		await registration?.sync?.register("sf-tasks-outbox");
	} catch {}
	void syncNow();
}
async function handleSynced(row, result) {
	await loadQueue();
	if (result?.item_kind) {
		if (selected.value?.name === result.name) selected.value = result;
		if (room.value && room.value.space.name === result.space) {
			const index = room.value.items.findIndex((item) => item.name === result.name);
			if (index >= 0) room.value.items[index] = result;
			else room.value.items.unshift(result);
		}
		await store.write(user.value, `item:${result.name}`, result);
	}
	if (
		row.method === "send_message" &&
		row.payload.payload.space === roomId.value &&
		!selected.value
	) {
		await refreshRoom(true);
	}
	if (row.method === "post_comment" && detailTab.value === "Comments") await loadComments();
	if (row.method === "add_tracker_files" && detailTab.value === "Files") await loadFiles();
}
async function syncNow() {
	if (!user.value || syncing || !online.value || authExpired.value) return;
	syncing = true;
	try {
		await flush(user.value, handleSynced);
		await loadQueue();
		await refresh();
	} catch (e) {
		if (e.status === 401) authExpired.value = true;
		else if (e.status === 403) error.value = e.message;
	} finally {
		syncing = false;
	}
}
async function send() {
	if (sending.value || !draft.value.trim()) return;
	sending.value = true;
	await guarded(async () => {
		const attachments = await filePayload(messageFiles.value);
		await draftSave;
		await queueAction(
			"send_message",
			{
				payload: {
					space: roomId.value,
					body: draft.value,
					entry_kind: "Message",
					request_key: id(),
					source_entry: reply.value?.name || null,
					attachments,
				},
			},
			`draft:${roomId.value}`,
		);
		draft.value = "";
		messageFiles.value = [];
		reply.value = null;
		await nextTick();
		if (thread.value) thread.value.scrollTop = thread.value.scrollHeight;
	});
	sending.value = false;
}
function chooseMessageFiles(event) {
	messageFiles.value = Array.from(event.target.files || []);
	event.target.value = "";
}
async function seenVisible() {
	if (
		!room.value ||
		!thread.value ||
		!online.value ||
		document.visibilityState !== "visible" ||
		overlay.value ||
		selected.value
	)
		return;
	const pane = thread.value.getBoundingClientRect();
	let last;
	for (const entry of room.value.entries) {
		const element = thread.value.querySelector(`[data-entry="${CSS.escape(entry.name)}"]`);
		if (element) {
			const r = element.getBoundingClientRect();
			if (r.top >= pane.top && r.bottom <= pane.bottom + 2) last = entry;
		}
	}
	if (last && (!room.value.seen_through || last.creation > room.value.seen_through)) {
		await call("mark_seen", { space: roomId.value, entry: last.name });
		room.value.seen_through = last.creation;
	}
}
async function olderMessages() {
	await guarded(async () => {
		const data = await call("get_space", {
			name: roomId.value,
			before: room.value.older_cursor,
		});
		room.value.entries = [...data.entries, ...room.value.entries];
		room.value.older_cursor = data.older_cursor;
		await store.write(user.value, `room:${roomId.value}`, room.value);
	});
}
function jumpToEntry(name) {
	navigate({ space: roomId.value, entry: name });
}
function setRoomTab(tab) {
	navigate({ space: roomId.value, tab });
}
function openItem(item) {
	navigate({ space: item.space, item: item.name });
}
function openItemById(name) {
	navigate({ space: roomId.value, item: name });
}
async function setDetailTab(tab) {
	detailTab.value = tab;
	if (tab === "Comments") await loadComments();
	if (tab === "Files") await loadFiles();
	if (tab === "Updates") await loadHistory();
}
async function newSpace() {
	formError.value = "";
	spaceForm.value = {
		title: "",
		space_kind: "Group",
		members: [{ user: user.value, access_level: "Owner" }],
		project: "",
		archived: false,
	};
	directory.value = home.value?.directory || [];
	directPerson.value = "";
	overlay.value = "space";
}
function editSpace() {
	spaceForm.value = {
		name: room.value.space.name,
		title: room.value.space.title,
		space_kind: room.value.space.space_kind,
		parent_space: room.value.space.parent_space,
		members: room.value.space.members.map((p) => ({
			user: p.user,
			access_level: p.access_level,
		})),
		project: room.value.space.project,
		archived: room.value.space.archived,
		modified: room.value.space.modified,
	};
	overlay.value = "space";
}
function newArea() {
	spaceForm.value = { title: "", space_kind: "Area", parent_space: roomId.value, members: [] };
}
async function findPeople() {
	const token = ++searchSequence;
	await new Promise((resolve) => setTimeout(resolve, 200));
	if (token !== searchSequence) return;
	await guarded(async () => {
		const result = await call("get_directory", { query: peopleQuery.value });
		if (token === searchSequence) directory.value = result;
	});
}
function pickSpace(kind) {
	createKind.value = kind;
	overlay.value = "pick-space";
}
async function createInSpace(name) {
	navigate({ space: name });
	await loadRoute();
	createItem(createKind.value);
}
async function createItem(kind, source = null) {
	form.value = source
		? newItem(kind, user.value, source)
		: (await store.read(user.value, `form:${roomId.value}:${kind}`)) ||
			newItem(kind, user.value);
	formError.value = "";
	overlay.value = "item";
}
function editItem(item) {
	form.value = copy(item);
	if (form.value.item_kind === "Event")
		for (const f of ["start_at", "end_at"])
			form.value[f] = String(form.value[f] || "").replace(" ", "T");
	overlay.value = "item";
}
function addStage() {
	const d = form.value.item_data;
	d.stages.push({
		key: id(),
		label: "",
		position:
			d.scale === "Stages"
				? Math.min(100, d.stages.length ? Number(d.stages.at(-1).position) + 10 : 0)
				: null,
		assignee: "",
	});
}
function trackerScaleChanged() {
	const d = form.value.item_data;
	d.stage = null;
	d.value = null;
	if (["Number", "Percentage"].includes(d.scale)) {
		d.assignment_mode = "Single";
		d.stages = [];
		d.minimum = 0;
		d.maximum = 100;
	} else
		for (const [i, s] of d.stages.entries())
			s.position =
				d.scale === "Stages" ? Math.round((i / (d.stages.length - 1 || 1)) * 100) : null;
}
function addSubtask() {
	form.value.item_data.subtasks.push({
		id: id(),
		title: "",
		assignee: form.value.assignee || user.value,
		deadline: null,
		status: "Open",
	});
}
function removeListRow(index) {
	const rows = form.value.item_data.rows,
		key = rows[index].id;
	for (const row of rows) if (row.parent_id === key) row.parent_id = null;
	rows.splice(index, 1);
}
async function saveItem() {
	const f = form.value;
	if (!f.title.trim()) throw new Error("Enter a title.");
	if (
		f.item_kind === "Tracker" &&
		["Status", "Stages"].includes(f.item_data.scale) &&
		!f.item_data.stages.length
	)
		throw new Error("Add at least one status or stage.");
	if (f.item_kind === "Tracker" && f.item_data.stages?.some((s) => !s.label.trim()))
		throw new Error("Give every stage a name.");
	const payload = itemPayload(f);
	await draftSave;
	await queueAction("save_item", {
		space: roomId.value,
		payload,
		name: f.name || null,
		expected_modified: f.modified || null,
	});
	if (!f.name) await store.remove(user.value, `form:${roomId.value}:${f.item_kind}`);
	closeOverlay();
	tell(
		online.value
			? "Saved to Outbox; it will appear after sending."
			: "Saved offline. It will send when you reconnect.",
	);
}
async function changeTask(item, status) {
	await guarded(async () => {
		await queueAction("update_task", {
			name: item.name,
			action: {
				Open: "reopen",
				"In progress": "start",
				Completed: "complete",
				Failed: "fail",
			}[status],
			expected_modified: item.modified,
		});
		tell("Status change saved.");
	});
}
async function subtaskStatus(sub, status) {
	await guarded(async () => {
		await queueAction("update_subtask", {
			name: selected.value.name,
			subtask: sub.id,
			status,
			expected_modified: selected.value.modified,
		});
	});
}
function openProgress(item) {
	selected.value = item;
	progress.value = {
		stage: item.item_data.stage || null,
		value: item.item_data.value,
		outcome: OPEN.has(item.status) ? "Open" : item.status,
		note: "",
		next_action: item.item_data.next_action || "",
		attention_date: item.item_data.attention_date || "",
		attention_until: item.item_data.attention_until || "",
		effective_at: "",
	};
	formFiles.value = [];
	overlay.value = "progress";
}
async function saveProgress() {
	if (!progress.value.note.trim()) throw new Error("Add a progress message.");
	const d = progress.value;
	await queueAction("record_progress", {
		name: selected.value.name,
		expected_modified: selected.value.modified,
		note: d.note,
		...(["Status", "Stages"].includes(selected.value.item_data.scale)
			? { stage: d.stage }
			: { value: d.value }),
		outcome: d.outcome,
		effective_at: d.effective_at || null,
		plan: {
			next_action: d.next_action,
			attention_date: d.attention_date || null,
			attention_until: d.attention_until || null,
		},
		attachments: await filePayload(formFiles.value),
		request_key: id(),
	});
	closeOverlay();
	tell("Progress update saved.");
}
async function toggleList(row) {
	await guarded(async () => {
		const payload = itemPayload(selected.value);
		payload.item_data.rows.find((r) => r.id === row.id).completed = !row.completed;
		await queueAction("save_item", {
			space: selected.value.space,
			payload,
			name: selected.value.name,
			expected_modified: selected.value.modified,
		});
	});
}
async function loadHistory() {
	await guarded(async () => {
		const data =
			online.value && serverReachable.value
				? await cached(
						"get_item_history",
						{ name: selected.value.name },
						`history:${selected.value.name}`,
					)
				: await store.read(user.value, `history:${selected.value.name}`);
		history.value = data?.history || [];
	});
}
async function showHistory() {
	await loadHistory();
	overlay.value = "history";
}
async function loadComments(before = null) {
	if (itemOnly.value) return;
	await guarded(async () => {
		const data =
			online.value && serverReachable.value
				? await cached(
						"get_comments",
						{ name: selected.value.name, before },
						`comments:${selected.value.name}`,
					)
				: await store.read(user.value, `comments:${selected.value.name}`);
		if (data)
			comments.value = before
				? { ...data, comments: [...comments.value.comments, ...data.comments] }
				: data;
	});
}
async function postComment() {
	await guarded(async () => {
		const text = commentDraft.value.trim();
		if (!text) return;
		await queueAction("post_comment", {
			name: selected.value.name,
			body: text,
			request_key: id(),
		});
		commentDraft.value = "";
		tell("Comment saved.");
		if (online.value) {
			await syncNow();
			await loadComments();
		}
	});
}
function openFiles() {
	formFiles.value = [];
	fileNote.value = "";
	overlay.value = "files";
}
async function loadFiles(before = null) {
	if (itemOnly.value) return;
	await guarded(async () => {
		const data =
			online.value && serverReachable.value
				? await cached(
						"get_tracker_files",
						{ name: selected.value.name, before },
						`files:${selected.value.name}`,
					)
				: await store.read(user.value, `files:${selected.value.name}`);
		if (data)
			trackerFiles.value = before
				? { ...data, files: [...trackerFiles.value.files, ...data.files] }
				: data;
	});
}
async function saveTrackerFiles() {
	if (!formFiles.value.length) throw new Error("Select at least one file.");
	await queueAction("add_tracker_files", {
		name: selected.value.name,
		expected_modified: selected.value.modified,
		attachments: await filePayload(formFiles.value),
		note: fileNote.value,
		request_key: id(),
	});
	closeOverlay();
	tell("Files saved to your Outbox.");
}
function openShare() {
	shares.value = copy(selected.value.shares || []).map((s) => ({
		user: s.user,
		access: s.access,
	}));
	directory.value = home.value?.directory || [];
	overlay.value = "share";
}
async function saveShare() {
	await call("share_item", {
		name: selected.value.name,
		shares: shares.value,
		expected_modified: selected.value.modified,
	});
	closeOverlay();
	await loadRoute();
}
function openSchedule() {
	schedule.value = { action: "snooze", date: null };
	overlay.value = "schedule";
}
async function saveSchedule() {
	await queueAction("update_task", {
		name: selected.value.name,
		action: schedule.value.date ? schedule.value.action : "snooze",
		date: schedule.value.date || null,
		expected_modified: selected.value.modified,
	});
	closeOverlay();
}
async function messageInfo(entry) {
	await guarded(async () => {
		receipts.value = (await call("get_message_info", { name: entry.name })).recipients;
		overlay.value = "receipts";
	});
}
async function removeMessage() {
	await guarded(async () => {
		await call("edit_entry", {
			name: entryMenu.value.name,
			remove: true,
			expected_modified: entryMenu.value.modified,
		});
		closeOverlay();
		await refreshRoom();
	});
}
async function loadMentions(before = null) {
	await guarded(async () => {
		const data =
			online.value && serverReachable.value
				? await cached(
						"get_mentions",
						{ before, unread_only: unreadMentions.value },
						"mentions",
					)
				: await store.read(user.value, "mentions");
		if (data)
			mentions.value = before
				? { ...data, mentions: [...mentions.value.mentions, ...data.mentions] }
				: data;
	});
}
async function openMention(entry) {
	if (online.value) await guarded(() => call("mark_mention_seen", { entry: entry.name }));
	navigate({ space: entry.space, entry: entry.name });
}
async function runSearch(before = null) {
	await guarded(async () => {
		const data = await call("search_conversation", {
			query: query.value,
			space: route.value.in || null,
			kind: searchKind.value,
			before: typeof before === "string" ? before : null,
		});
		searchResults.value =
			typeof before === "string"
				? { ...data, results: [...searchResults.value.results, ...data.results] }
				: data;
		searched.value = true;
	});
}
function openSearchResult(row) {
	if (row.kind === "File") {
		openFile({ file_url: row.file_url, file_name: row.title });
		return;
	}
	navigate(
		row.kind === "Message"
			? { space: row.space, entry: row.name }
			: { space: row.space, item: row.item },
	);
}
async function openFile(file) {
	await guarded(async () => {
		const url = safeFileURL(file.file_url);
		if (!url) throw new Error("Invalid private file link.");
		const saved = await store.read(user.value, `file:${url}`);
		if (!online.value || !serverReachable.value) {
			if (!saved) throw new Error("Save this file offline while connected first.");
			return openSavedFile(saved);
		}
		await sessionCheck();
		const response = await fetch(url, {
			credentials: "same-origin",
			cache: "no-store",
			redirect: "error",
		});
		if (!response.ok) throw new Error("This file is not available to your account.");
		showBlob(await response.blob(), file.file_name);
	});
}
function showBlob(blob, name = "Attachment") {
	if (previewURL.value) URL.revokeObjectURL(previewURL.value);
	previewURL.value = URL.createObjectURL(blob);
	previewType.value = blob.type;
	previewName.value = name;
	overlay.value = "file-preview";
}
async function saveFile(file) {
	await guarded(async () => {
		await sessionCheck();
		const url = safeFileURL(file.file_url);
		if (!url) throw new Error("Invalid private file link.");
		const response = await fetch(url, {
			credentials: "same-origin",
			cache: "no-store",
			redirect: "error",
		});
		if (!response.ok) throw new Error("Unable to save this file.");
		const blob = await response.blob();
		if (blob.size > 10485760) throw new Error("Offline files must be at most 10 MB.");
		const content = await filePayload([new File([blob], file.file_name)]);
		await store.write(user.value, `file:${url}`, {
			name: file.file_name,
			url,
			type: blob.type,
			content: content[0].content,
		});
		tell("Saved for offline access.");
	});
}
async function loadSavedFiles() {
	savedFiles.value = await store.list(user.value, "file:");
}
function openSavedFile(file) {
	const bytes = Uint8Array.from(atob(file.content), (c) => c.charCodeAt(0));
	showBlob(new Blob([bytes], { type: file.type }), file.name);
}
async function removeSavedFile(file) {
	await store.remove(user.value, `file:${file.url}`);
	await loadSavedFiles();
}
async function discardQueued(row) {
	if (!confirm("Discard this unsent change from this device?")) return;
	await store.remove(user.value, `queue:${row.id}`);
	await loadQueue();
}
function reviewQueued(row) {
	if (row.payload.name) navigate({ item: row.payload.name });
	else if (row.payload.space || row.payload.payload?.space)
		navigate({ space: row.payload.space || row.payload.payload.space });
	tell(
		"Review the current record. Discard the old Outbox change before saving a corrected version.",
	);
}
async function saveSettings() {
	try {
		await store.write(user.value, "settings", settings.value);
		if (
			registration &&
			typeof Notification !== "undefined" &&
			Notification.permission === "granted"
		) {
			const sub = await registration.pushManager.getSubscription();
			if (sub) await registerPush(sub);
		}
	} catch (e) {
		error.value = e.message;
	}
}
async function registerPush(sub) {
	let binding = await store.read(user.value, "push-binding");
	if (!binding) {
		binding = id();
		await store.write(user.value, "push-binding", binding);
	}
	await request("volunteering.volunteering.tasks_web_push.subscribe", {
		subscription: sub.toJSON(),
		binding,
		preferences: {
			mode: settings.value.notifications,
			quiet_from: settings.value.quiet_from,
			quiet_until: settings.value.quiet_until,
			chats: settings.value.chats || {},
		},
	});
	pushStatus.value = "Notifications enabled for this browser.";
}
async function enablePush() {
	await guarded(async () => {
		if (!registration || !("PushManager" in window) || !("Notification" in window))
			throw new Error(
				"This browser cannot enable web notifications here. Use a supported browser over HTTPS.",
			);
		if ((await Notification.requestPermission()) !== "granted")
			throw new Error("Allow notifications in your browser settings to enable them.");
		const config = await request("volunteering.volunteering.tasks_web_push.get_config");
		if (!config.enabled) throw new Error("Web notifications are disabled on this site.");
		const bytes = Uint8Array.from(
			atob(config.public_key.replace(/-/g, "+").replace(/_/g, "/")),
			(c) => c.charCodeAt(0),
		);
		const sub =
			(await registration.pushManager.getSubscription()) ||
			(await registration.pushManager.subscribe({
				userVisibleOnly: true,
				applicationServerKey: bytes,
			}));
		await registerPush(sub);
	});
}
async function persistStorage() {
	const kept = await navigator.storage?.persist?.();
	storageInfo.value = kept
		? "Persistent storage granted. Clearing browser data still removes offline copies."
		: "The browser did not grant persistent storage. Keep the ERP as the permanent record.";
}
async function logout() {
	busy.value = true;
	try {
		if (!online.value)
			throw new Error("Connect to the internet to sign out of your ERP session safely.");
		const binding = await store.read(user.value, "push-binding");
		if (binding && online.value)
			await request("volunteering.volunteering.tasks_web_push.unsubscribe", { binding });
		const sub = await registration?.pushManager?.getSubscription();
		await sub?.unsubscribe();
		await request("logout", {});
		await store.forget(user.value);
		location.replace("/sf-tasks/");
	} catch (e) {
		error.value = e.message;
		closeOverlay();
	} finally {
		busy.value = false;
	}
}
async function submitOverlay() {
	const content = dialogElement.value?.querySelector("form");
	if (content && !content.reportValidity()) return;
	busy.value = true;
	formError.value = "";
	try {
		switch (overlay.value) {
			case "item":
				await saveItem();
				break;
			case "space": {
				if (!online.value)
					throw new Error(
						"Connect to the internet to change conversations or membership.",
					);
				let result;
				if (spaceForm.value.space_kind === "Direct") {
					if (!directPerson.value) throw new Error("Choose a person.");
					result = await call("start_direct", { user: directPerson.value });
				} else {
					const f = spaceForm.value;
					result = await call("save_space", {
						payload: {
							title: f.title,
							space_kind: f.space_kind,
							parent_space: f.parent_space || null,
							project: f.project || null,
							...(!f.parent_space ? { members: f.members } : {}),
							archived: f.archived || false,
						},
						name: f.name || null,
						expected_modified: f.modified || null,
					});
				}
				closeOverlay();
				await refreshHome();
				navigate({ space: result.name });
				break;
			}
			case "progress":
				await saveProgress();
				break;
			case "files":
				await saveTrackerFiles();
				break;
			case "share":
				await saveShare();
				break;
			case "schedule":
				await saveSchedule();
				break;
			case "edit-message":
				await call("edit_entry", {
					name: entryMenu.value.name,
					body: editText.value,
					expected_modified: entryMenu.value.modified,
				});
				closeOverlay();
				await refreshRoom();
				break;
			case "reset":
				await request("frappe.core.doctype.user.user.reset_password", {
					user: resetEmail.value,
				});
				closeOverlay();
				tell("If the account is eligible, a password reset email will be sent.");
				break;
		}
	} catch (e) {
		formError.value = e.message;
	} finally {
		busy.value = false;
	}
}
async function install() {
	if (!installPrompt.value) return;
	await installPrompt.value.prompt();
	await installPrompt.value.userChoice;
	installPrompt.value = null;
}
async function checkUpdate() {
	await registration?.update();
	tell(updateReady.value ? "A new version is ready." : "The PWA update check is complete.");
}
async function activateUpdate() {
	await draftSave;
	registration?.waiting?.postMessage({ type: "ACTIVATE" });
}
function onInstall(event) {
	event.preventDefault();
	installPrompt.value = event;
}
function onPop() {
	if (overlay.value) closeOverlay();
	route.value = readRoute();
	void loadRoute();
}
function onVisibility() {
	if (document.visibilityState === "visible") {
		online.value = navigator.onLine;
		void refresh();
		void syncNow();
	}
}
function onOnline() {
	online.value = true;
	void refresh();
	void syncNow();
}
function onOffline() {
	online.value = false;
}
onMounted(async () => {
	window.addEventListener("popstate", onPop);
	window.addEventListener("online", onOnline);
	window.addEventListener("offline", onOffline);
	window.addEventListener("beforeinstallprompt", onInstall);
	document.addEventListener("visibilitychange", onVisibility);
	matchMedia("(prefers-color-scheme: dark)").addEventListener(
		"change",
		(event) => (dark.value = event.matches),
	);
	if ("serviceWorker" in navigator && isSecureContext) {
		try {
			registration = await navigator.serviceWorker.register(
				"/api/method/" + PWA_API + "service_worker",
				{ scope: "/sf-tasks/", type: "module", updateViaCache: "none" },
			);
			updateReady.value = !!registration.waiting;
			registration.addEventListener("updatefound", () => {
				const worker = registration.installing;
				worker?.addEventListener("statechange", () => {
					if (worker.state === "installed" && registration.active)
						updateReady.value = true;
				});
			});
			navigator.serviceWorker.addEventListener("controllerchange", () => {
				if (updateReady.value) location.reload();
			});
			navigator.serviceWorker.addEventListener("message", (event) => {
				if (event.data?.type === "OUTBOX_CHANGED") {
					void loadQueue();
					void refresh();
				}
				if (event.data?.type === "PUSH_REFRESH") void refresh();
			});
		} catch (e) {
			error.value = "Offline installation is unavailable: " + e.message;
		}
	}
	await boot();
	timer = setInterval(() => {
		if (
			roomId.value &&
			!selected.value &&
			document.visibilityState === "visible" &&
			!overlay.value
		)
			void guarded(() => refreshRoom());
		if (++sequence % 4 === 0) {
			void refresh();
			void syncNow();
		}
	}, 5000);
});
onUnmounted(() => {
	clearInterval(timer);
	window.removeEventListener("popstate", onPop);
	window.removeEventListener("online", onOnline);
	window.removeEventListener("offline", onOffline);
	window.removeEventListener("beforeinstallprompt", onInstall);
	document.removeEventListener("visibilitychange", onVisibility);
});

const iconPaths = {
	bell: "M18 8a6 6 0 0 0-12 0v7l-2 3h16l-2-3V8ZM10 21h4",
	chat: "M21 11.5a8 8 0 0 1-8.5 8 9 9 0 0 1-4-.9L3 20l1.4-5A8 8 0 1 1 21 11.5Z",
	check: "m9 11 3 3 8-9M4 5h2M4 12h2M4 19h2M10 20h10",
	layers: "m12 3 10 5-10 5L2 8l10-5Zm-9 10 9 5 9-5M3 18l9 5 9-5",
	calendar: "M4 5h16v16H4V5Zm3-3v6m10-6v6M4 10h16",
	at: "M16 8v7c0 3 5 2 5-3a9 9 0 1 0-4 7M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
	search: "m16 16 5 5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
	settings: "M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-6 0v6",
	plus: "M12 4v16M4 12h16",
	person: "M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0M4 21v-2a8 8 0 0 1 16 0v2",
	clip: "m8 13 7-7a3 3 0 0 1 4 4l-9 9a5 5 0 0 1-7-7L14 1",
};
const SvgIcon = defineComponent({
	props: { name: String },
	setup: (props) => () =>
		h(
			"svg",
			{
				viewBox: "0 0 24 24",
				fill: "none",
				stroke: "currentColor",
				"stroke-width": 1.8,
				"stroke-linecap": "round",
				"stroke-linejoin": "round",
				"aria-hidden": true,
			},
			[h("path", { d: iconPaths[props.name] || iconPaths.chat })],
		),
});
const MentionPicker = defineComponent({
	props: { members: Array },
	emits: ["choose"],
	setup:
		(props, { emit }) =>
		() =>
			h("details", { class: "mention-picker" }, [
				h("summary", "Mention someone"),
				...(props.members || [])
					.filter((p) => p.chat_enabled)
					.map((p) =>
						h(
							"button",
							{ type: "button", onClick: () => emit("choose", p) },
							p.full_name,
						),
					),
			]),
});
const FileRow = defineComponent({
	props: { file: Object },
	emits: ["open", "save"],
	setup:
		(props, { emit }) =>
		() =>
			h("div", { class: "file-row" }, [
				h(
					"button",
					{
						type: "button",
						class: "file-open",
						onClick: () => emit("open", props.file),
					},
					["↗ ", props.file.file_name],
				),
				h(
					"button",
					{
						type: "button",
						class: "file-save",
						"aria-label": `Save ${props.file.file_name} offline`,
						onClick: () => emit("save", props.file),
					},
					"↓",
				),
			]),
});
const WorkCard = defineComponent({
	props: { item: Object, user: String },
	emits: ["open", "status"],
	setup:
		(props, { emit }) =>
		() => {
			const item = props.item,
				tracker = item.item_kind === "Tracker",
				pending = pendingWith(item),
				mine = pending?.user === props.user;
			return h(
				"article",
				{
					class: [
						"work-card",
						tracker ? trackerState(item) : "",
						mine ? "pending-me" : "",
					],
				},
				[
					h("button", { class: "work-card-main", onClick: () => emit("open", item) }, [
						h("div", { class: "work-card-title" }, [
							h("strong", item.title),
							h("span", { class: "status-pill" }, item.status),
							h("span", { class: "chevron" }, "›"),
						]),
						tracker ? h(ProgressBar, { item }) : null,
						tracker ? h("p", { class: "stage-label" }, progressOf(item).label) : null,
						h(
							"small",
							{ class: mine ? "needs-me" : "muted" },
							pending?.user
								? mine
									? "Pending with you"
									: `Pending with ${pending.full_name || pending.user}`
								: item.status,
						),
						h("small", { class: "work-dates" }, dateRange(item)),
					]),
					!tracker && item.item_kind === "Task" && item.can_update
						? h(
								"select",
								{
									"aria-label": `Status of ${item.title}`,
									value: item.status,
									onChange: (event) => emit("status", item, event.target.value),
								},
								["Open", "In progress", "Completed", "Failed"].map((s) =>
									h("option", { value: s }, s),
								),
							)
						: null,
				],
			);
		},
});
</script>
