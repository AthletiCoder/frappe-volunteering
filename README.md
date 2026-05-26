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
