# Volunteering frontend (Frappe UI SPA)

Vue SPA for Home, Budget Health, and Advance Portal. App overview: [../README.md](../README.md).

```bash
cd apps/volunteering/frontend
yarn
yarn build
bench --site <site> clear-cache
```

Routes (after build):

- `/volunteering/home`
- `/volunteering/budget-health`
- `/volunteering/advances`

Desk **Home** and Help icons open `/volunteering/home`. Bookmarks to My Work / My Expenses redirect there.
