# HR & attendance wiki

## If pages 404

Wiki v3 treats an empty role table as **logged-in only**. Guests see “Page not found”.
After migrate, Sevamrita Wiki space gets **Guest / Employee Read** so `/help/...` links work.

Also **restart `bench start`** after installing wiki so web workers load the app.

## View (website)

| Topic | URL |
|-------|-----|
| HR home | `/help/hr/home` |
| Daily Work Log | `/help/hr/daily-work-log` |
| Attendance | `/help/hr/attendance` |
| Work From Home | `/help/hr/work-from-home` |
| Leave | `/help/hr/leave` |
| Manager guide | `/help/hr/manager-guide` |
| HR settings | `/help/hr/settings` |
| How to spend | `/help/accounts/how-to-spend` |
| Tally → ERPNext | `/help/accounts/tally-to-erpnext` |

Space hub: `/help` (redirects to first page).

## Edit (Desk)

Use **Wiki Document** (not the deprecated Wiki Page).

Or open the Wiki app UI: `/wiki` → space **Sevamrita Wiki**.

## Seed

`volunteering.volunteering.wiki_setup.ensure_help_wikis` runs on migrate.
