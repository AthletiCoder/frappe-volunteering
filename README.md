### Volunteering

Track volunteers, events, participation, and reciprocation in one focused workflow for NGO operations.

### Features

#### Core DocTypes

- **Volunteer**: Stores personal and employment details for each volunteer, with automatic phone normalization for clean matching and deduping.
- **NGO Event**: Manages event planning and execution stages (`Planned`, `Registrations`, `Shipping`, `Followup`, `Closed`).
- **Participation**: Captures event registrations, attendance, logistics details (kits, shipping, logging), and volunteer linkage.
- **Participation Extra Detail**: Adds dynamic question-and-answer rows per participation for campaign-specific data.
- **Gift Hamper**: Defines hamper templates by tier (`Standard`, `Reminder`, `Deluxe`) with cost rollups.
- **Gift Hamper Item**: Child table for hamper item breakdown (item, qty, unit cost, amount).
- **Reciprocation**: Tracks hamper allocation and delivery status per volunteer per event.

#### Workflow Highlights

- **Smart volunteer linking**: Participation uses phone matching to link to an existing volunteer, or auto-creates one when needed.
- **Event-triggered automation**: Moving an event to `Shipping` can trigger reciprocation creation for eligible volunteers.
- **Volunteer tiering logic**: Volunteer status is updated based on recent participation patterns (for example, Active/Star/Inactive behavior).
- **Operational tracking**: Participation records support end-to-end follow-up from registration to shipping and logging.

#### Web Form Template (Event Registration)

- **Published registration form**: A ready-to-use public form for event signups.
- **Custom interactive inputs**: Includes campaign-focused fields such as WhatsApp confirmation, kit count, collection method, and optional organizing interest.
- **Referral support**: Reads referral from URL params and stores it in `referred_by`.
- **Validation-first UX**: Enforces required fields (for example, WhatsApp confirmation and delivery address when residential delivery is selected).
- **Structured payload mapping**: Writes answers into `Participation` and `Participation Extra Detail` so data remains reportable and clean.

#### Reporting and Access

- **Dynamic event report**: `Generic Event Participation Report` builds columns dynamically from extra-detail questions for the selected event.
- **Role-aware access model**: Supports `NGO Admin`, `NGO Coordinator`, and `NGO Member` with DocType-level permissions and row-level visibility controls on key records.

### Volunteer ratings (for Relationship Managers)

This section explains how to record and use volunteer ratings after an event.

#### Who can rate

- Each **Volunteer** has an assigned **Relationship Manager** (`Volunteer.relationship_manager`).
- Only that Relationship Manager can enter or change the rating and comment on a **Participation** record.
- **NGO Admin** and **System Manager** can also edit ratings when needed.

#### When to rate

Rate at the **end of the event**, after follow-up work is done:

1. Complete distribution and logging details on the Participation (kits delivered, hours logged, etc.).
2. Set **Logging Status** to **Logged**.
3. The form will prompt you to add a **Rating** and **Relationship Manager Comment**.
4. Save the Participation.

A rating is **required** once Logging Status is **Logged**.

#### What you are rating

- Use the **Rating** field (1–5 stars) for **overall communication ease** with the volunteer during that event.
- Add context in **Relationship Manager Comment** (follow-up quality, responsiveness, issues, positives).

This is separate from **Volunteer Status** (Active / Star / Inactive), which is based on how often someone participates, not how easy they are to work with.

#### Before you save

- **Kits Delivered** must be greater than **zero** before a rating can be saved.
- **Hours Logged** should reflect actual volunteer effort for that event.

#### How expected hours and effective rating work

The system compares logged hours to expected hours for the kits delivered:

- **Expected hours** = `Kits Delivered` × **Hours Per Kit**
- **Hours Per Kit** comes from the **Project** linked to the event (`NGO Event` → `Project`). If not set on the project, the default is **0.5** hours per kit.

Example: 10 kits delivered, Hours Per Kit = 0.5 → expected hours = 5. If the volunteer logged 5 hours, there is no adjustment. If they logged less or more, the **Effective Rating** on that Participation may move slightly down or up (within 1–5), based on your star rating.

On each Participation you will see (read-only after save):

| Field | Meaning |
|-------|---------|
| **Expected Hours** | Target hours for kits delivered |
| **Hours Delta** | Hours Logged minus Expected Hours |
| **Effective Rating** | Final score for this event (1–5) after the hours adjustment |

#### Volunteer profile score

Open the **Volunteer** record to see the rolled-up score:

| Field | Meaning |
|-------|---------|
| **Effective Rating** | Weighted average from the volunteer’s **last 3 rated events** (most recent event counts the most) |
| **Rated Events Count** | How many rated events were used (1–3) |
| **Rating Last Updated** | When the profile score was last recalculated |

Weights for the last three rated events (newest first): **50%**, **30%**, **20%**. Only participations with a rating are included.

#### Quick checklist per participation

- [ ] Kits Delivered is correct and greater than zero
- [ ] Hours Logged is entered
- [ ] Logging Status = **Logged**
- [ ] Rating (1–5) and comment added
- [ ] Save — confirm **Effective Rating** on Participation and **Effective Rating** on Volunteer

#### Tips

- Set **Hours Per Kit** on the event’s **Project** if a campaign needs a different effort expectation than the default (0.5).
- Use comments for anything the number alone cannot capture; they help future Relationship Managers and coordinators.
- Re-save a Participation after changing kits, hours, or rating to refresh the volunteer’s profile score.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app volunteering
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/volunteering
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
