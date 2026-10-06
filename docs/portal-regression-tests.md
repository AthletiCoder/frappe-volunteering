# Portal regression tests

Run against the local `sevamrita.local` demo site only. The desktop regression
suite submits test projects, advances, claims, and donations and creates local
accounting entries. It refuses non-local base URLs.

```sh
npm run test:e2e:portal
npm run test:e2e:portal:mobile
```

Set `BASE_URL=http://127.0.0.1:8001` if the local site uses a different port.
The portal suite defaults to port 8001; the mobile suite also uses the local
site. Both run serially to avoid overloading a single development bench.

The desktop suite covers role-based navigation; project proposal, approval and
financial visibility; advance requests, hierarchy, freezes, disbursement and
returns; bank-account approval; invoice creation and signatures; single- and
multi-invoice claims; receipt review, approval, classification and payment;
and general/CSR donations. The mobile suite audits those forms and management
workspaces at 360px and 390px for clipped controls, horizontal overflow, small
primary targets and inputs that trigger mobile focus zoom.

Also run the Frappe backend suite from the local bench before deployment:

```sh
bench --site sevamrita.local run-tests --app volunteering --test-category unit
bench --site sevamrita.local run-tests --app volunteering --test-category integration
```

Do not interpret a browser-only pass as proof that backend accounting and
permission tests passed. Preserve the failing output and investigate any
backend crash or failure before release.

The older `playwright.config.ts` suite is separate. It includes legacy Desk
routes and vendor-payment scenarios that are not implemented in the current
Home portal. Its full run is not a substitute for the local-only portal suite,
and a portal-suite pass must not be described as a pass of every historical
Desk E2E spec.
