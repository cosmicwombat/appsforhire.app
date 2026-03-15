# Team-Apps Modernization — Context & Checklist Prompt

> Paste this into a new Cowork session with the `team-apps` folder mounted.
> This prompt brings forward everything learned in the `app_for_hire` (AppsForHire) project
> and maps it to the team-apps architecture so Claude can help you execute the upgrade.

---

## What This Is

You are helping modernize the **Tekmetric Team-Apps** internal tool platform.

A parallel project — **AppsForHire** (a client PWA-as-a-service platform) — has recently been overhauled with a mature access control, admin, and deployment workflow. We want to apply those same patterns here, adapted for an internal company context.

The key insight is that the two platforms are structurally identical but with different hierarchies:

| AppsForHire | Team-Apps Equivalent |
|-------------|----------------------|
| appsforhire.app (marketing/landing) | Company portal (`pwa/index.html`) — currently public |
| Customer portals (`/portal/`) | Department portals (Sales, CS, Support, Engineering, Exec) |
| Client email OTP via CF Access | Company SSO (Google Workspace / Azure AD) via CF Access |
| Admin panel (appsforhire-admin) | Admin portal — **does not yet exist** |
| Per-client Access policy | Per-department SSO role/group policy |
| `publish` flow (auto repo, DNS, Access, portal cascade) | App promotion flow (currently manual PR → Infra review) |
| Portal cascade (push config to all client repos) | Department cascade (push updated app list to all department portals) |
| `data.json` (source of truth for customers/apps) | `apps.json` + `APPS[]` arrays in portal files (currently split/manual) |
| `CLAUDE_CONTEXT.md` + plugin | `GENERAL_INSTRUCTIONS.md` + a new team-apps plugin |
| Cowork app-builder skill | Same pattern — team-apps-specific Cowork plugin |
| Co-author onboarding | Developer onboarding for internal contributors |

---

## Current State of Team-Apps

- **Hosting:** GitHub Pages at `rkeller-tekmetric.github.io/team-apps/pwa/`
- **Auth:** None — the portal is publicly accessible by URL. The `beta-auth/` folder and `exec-portal/` suggest partial access control exists but is not unified.
- **App catalog:** Hardcoded `APPS[]` arrays duplicated across `pwa/index.html` and `pwa/beta/index.html`. No single source of truth.
- **Promotion:** Manual PR process — change `status:"beta"` to `status:"live"` in both files, requires Infra review.
- **Department portals:** `exec-portal/` exists as a standalone page. No other department portals.
- **Admin:** No admin panel. App management done by editing HTML files directly.
- **Developer workflow:** Manual — edit files, commit, push, GitHub Actions deploys.
- **Compliance:** Strong — `GENERAL_INSTRUCTIONS.md` has PII filtering, CPNI, usage tracking, dual report mode, security checklist.

---

## What We Want to Build

### 1. Unified Access Control (Company SSO via Cloudflare Access)

Replace the current public-URL-only access model with proper authentication:

- **Company portal** (`pwa/index.html`) → protected by company SSO (Google Workspace SAML or Azure AD) via Cloudflare Access
- **Department portals** → each department gets its own CF Access policy scoped to that team's SSO group
- **Admin portal** → restricted to Infra team / app owners only (smaller SSO group policy)
- **Beta page** → restricted to internal contributors (same as admin, or a broader "all staff" policy)
- **Exec portal** → `exec-portal/` already exists — migrate it to a proper CF Access policy scoped to the Leadership group

CF Access SSO setup (different from AppsForHire's OTP):
- Identity provider: Google Workspace (SAML) or Azure AD (OIDC) — whichever Tekmetric uses
- Policy type: "Include → Emails ending in @tekmetric.com" (or group-based if Azure AD groups are configured)
- Per-department: "Include → Group → [department-group-id]"
- Session duration: 8h (workday-length, same logic as AppsForHire's 6h for clients)

### 2. Department Portals

Each department gets a `/portal/{department}/` page that shows only that team's apps — analogous to AppsForHire's customer portals. Departments to create:

| Department | Slug | Apps (current) |
|------------|------|----------------|
| Sales | `sales` | Tek Trek Agent, Four Pillars |
| Customer Success | `cs` | Tek-Intelligence (Gong), VoC Health |
| Support | `support` | Tek-Intelligence (Intercom), Capacity Planner |
| Engineering / Infra | `infra` | DialPlan Discovery, all beta apps |
| Executive | `exec` | Four Pillars, all production summaries |

Each department portal:
- Shows only that team's apps as cards
- Links back to the main portal
- Has its own CF Access policy (scoped to that team's SSO group)
- Has a "My Apps" page style matching the existing dark design system
- Is auto-generated from a single source-of-truth config (see #3)

### 3. Single Source of Truth: `apps.json`

Replace the duplicated `APPS[]` arrays in HTML files with a single `apps.json` that all portals read dynamically. Structure mirrors AppsForHire's `data.json`:

```json
{
  "departments": [
    {
      "name": "Customer Success",
      "slug": "cs",
      "sso_group": "cs-team@tekmetric.com",
      "theme_color": "#0d9488",
      "apps": [
        {
          "slug": "tek-intelligence-gong",
          "title": "Tek-Intelligence",
          "subtitle": "Gong call analysis",
          "icon": "🧠",
          "url": "https://rkeller-tekmetric.github.io/team-apps/pwa/apps/gong-query.html",
          "status": "live",
          "worker": "gong-insights-proxy",
          "launched": "March 2026"
        }
      ]
    }
  ],
  "generated": "2026-03-14"
}
```

Benefits: One place to add an app. Portals read it at runtime. Admin panel writes it (see #4). No more duplicated `APPS[]` arrays.

### 4. Admin Portal

A single-page admin dashboard — analogous to the AppsForHire admin panel — for managing the app catalog without editing HTML:

**Dashboard tab:** MRR equivalent → app count, active departments, worker health
**Apps tab:** List all apps with status badges. Mark beta/live. Link to app + worker.
**Departments tab:** Manage department portal configs. Add/remove apps per department.
**Access tab:** Two functions — (1) **Sanity check**: call CF API to list policies per department and display every allowed email, so you can verify who has access at a glance. (2) **Add user**: add an email to a department's CF Access policy. See CF Access policy gotcha below — both app-scoped and reusable policy endpoints must be handled.
**Deploy tab:** Trigger portal cascade — regenerate all department portals from `apps.json` and push to GitHub.

Auth: The admin portal itself is protected by a CF Access policy scoped to Infra team.

**Write operations** use the GitHub API (Personal Access Token stored in `localStorage`) and a Cloudflare Worker admin secret — same pattern as AppsForHire.

**Preflight check:** Before any write operation (status change, portal cascade), check the repo for commits in the last 10 minutes and warn if recent activity is detected (prevents conflicts between two admins).

### 5. Cowork App-Builder Workflow

Replace the current manual "copy a template file, edit it, push it" workflow with a Cowork-based flow — same as AppsForHire's 🛠️ New App button:

1. Admin portal → **New App** button → fill in name, department, worker type, APIs needed
2. Admin portal generates a Cowork prompt (pre-filled with team-apps context, design system, compliance requirements from `GENERAL_INSTRUCTIONS.md`, API patterns)
3. Developer opens a new Cowork session with the team-apps folder mounted and the **team-apps plugin** installed
4. Paste the prompt → Claude builds the app following all GENERAL_INSTRUCTIONS rules:
   - Usage tracking (`recordUsage()`)
   - PII filtering (`sanitizeForAI()`)
   - Dual report mode
   - Security checklist
   - CORS locked to GitHub Pages domain
5. After review: commit, push, app auto-deploys via GitHub Actions to the Beta page
6. Admin portal → mark as Live → portal cascade updates all department portals

### 6. Team-Apps Plugin (Cowork)

A Cowork plugin parallel to `appsforhire.plugin`, containing:

- **`skills/app-builder`** — full platform context: department list, workers, design system, compliance rules (GENERAL_INSTRUCTIONS condensed), API patterns, security checklist
- **`commands/new-app`** — scaffold a new app from template
- **`commands/push-portal`** — push portal cascade to GitHub
- **`commands/health-check`** — check all workers and their API connections
- **`commands/promote`** — generate a promotion PR for an app
- **`hooks/`** — load platform context at session start

The plugin's context file is a direct copy of a `TEAM_APPS_CONTEXT.md` (the team-apps equivalent of `CLAUDE_CONTEXT.md`) — kept in sync by rebuilding the plugin whenever context changes.

### 7. Git Workflow Hardening

Apply the same safe git workflow used in AppsForHire:

```bash
# Before every session:
git stash && git pull --rebase && git stash pop

# Before any deploy:
# (Admin portal preflight check handles this automatically)
```

Add a `CONTRIBUTING.md` that documents:
- App slug ownership per developer
- No simultaneous deploys
- Announce deploys in #infra Slack channel before running portal cascade
- Branch protection already exists — maintain it

---

## Upgrade Checklist

Work through these in order. Each item is a discrete task that can be done in a separate Cowork session.

### Phase 1 — Foundation

- [ ] **1.1** Create `TEAM_APPS_CONTEXT.md` — the single source of truth for platform context (mirrors `CLAUDE_CONTEXT.md` from AppsForHire). Include: department list, workers inventory, design system tokens, compliance rules summary, git workflow, gotchas.
- [ ] **1.2** Create `apps.json` — migrate all `APPS[]` entries from `pwa/index.html` and `pwa/beta/index.html` into a unified JSON structure with department groupings.
- [ ] **1.3** Update `pwa/index.html` and `pwa/beta/index.html` to fetch `apps.json` at runtime instead of using hardcoded arrays. Verify no regression in rendering.

### Phase 2 — Access Control

- [ ] **2.1** Set up Cloudflare Access for the main portal — configure SSO identity provider (Google Workspace or Azure AD), create a "Tekmetric Staff" Access application for `rkeller-tekmetric.github.io/team-apps/pwa/`.
- [ ] **2.2** Migrate `exec-portal/` to a proper CF Access policy scoped to the Leadership SSO group.
- [ ] **2.3** Create CF Access applications and SSO-group policies for each department portal (Sales, CS, Support, Infra, Exec).
- [ ] **2.4** Create a CF Access application for the future admin portal (Infra team only).
- [ ] **2.5** Set session duration to 8 hours on all CF Access applications.

### Phase 3 — Department Portals

- [ ] **3.1** Design the department portal template — adapt the AppsForHire `/portal/index.html` pattern to team-apps design system and branding.
- [ ] **3.2** Create `pwa/portal/{slug}/index.html` and `customer-config.js` (or equivalent) for each department: `sales`, `cs`, `support`, `infra`, `exec`.
- [ ] **3.3** Populate each department portal from `apps.json` — list only that department's apps.
- [ ] **3.4** Add "← All Apps" back-link from each department portal to the main portal.
- [ ] **3.5** Write a `push_portals.py` equivalent (or extend the GitHub Actions deploy) to cascade `apps.json` changes to all department portals automatically.

### Phase 4 — Admin Portal

- [ ] **4.1** Scaffold the admin portal at `admin/index.html` (or a separate GitHub Pages repo). Use the AppsForHire admin panel as the reference architecture.
- [ ] **4.2** Implement **Dashboard tab** — app count, department count, worker health check (call `/api/health` on each worker).
- [ ] **4.3** Implement **Apps tab** — read `apps.json`, display all apps with status. Allow marking beta/live (writes to `apps.json` via GitHub API).
- [ ] **4.4** Implement **Departments tab** — show department configs, allow adding/removing apps per department, trigger portal cascade.
- [ ] **4.5** Implement **Access tab** — two parts:
  - *Sanity check view*: `GET /accounts/{id}/access/apps` → for each department app, `GET /access/apps/{uid}/policies` → display allowed emails. Reference `scripts/check_access_emails.py` in app_for_hire for the pattern.
  - *Add user*: build the email input + slug selection UI. The write operation must try the app-scoped policy endpoint first (`PUT /access/apps/{uid}/policies/{pid}`) and fall back to the account-level reusable policy endpoint (`PUT /access/policies/{pid}`) if CF returns error code 12130 — CF silently uses reusable policies for some apps and the two endpoints are not interchangeable. Reference `scripts/add_access_email.py` in app_for_hire for the working implementation.
- [ ] **4.6** Add **publish preflight check** — before any write, check GitHub API for commits in last 10 minutes, soft-warn if activity detected.
- [ ] **4.7** Implement **New App modal** — form that generates a Cowork prompt pre-filled with team-apps context, compliance requirements, and the chosen worker/API types.

### Phase 5 — Cowork Plugin

- [ ] **5.1** Write `TEAM_APPS_CONTEXT.md` (if not already done in 1.1) — this becomes the plugin's context file.
- [ ] **5.2** Create the `team-apps.plugin` — scaffold with `skills/app-builder`, `commands/` (new-app, push-portal, health-check, promote), and `hooks/` (session start context load).
- [ ] **5.3** Write the `app-builder` skill — include all rules from `GENERAL_INSTRUCTIONS.md` as the skill's non-negotiables: usage tracking, PII filtering, dual report mode, CORS, security checklist. Make it impossible to forget these when building.
- [ ] **5.4** Write a `CONTRIBUTING.md` for new developers — mirrors `CO-AUTHOR-ONBOARDING.md` from AppsForHire but for internal contributors: GitHub access, CF token, plugin install, git workflow, slug ownership.
- [ ] **5.5** Package and install the plugin. Test a full app-build session end-to-end.

### Phase 6 — Workflow Integration

- [ ] **6.1** Wire the admin portal's **New App** button to generate Cowork prompts that reference the plugin's app-builder skill.
- [ ] **6.2** Add a **post-publish prompt** to the admin portal — after marking an app live, show a copyable Cowork prompt to run the portal cascade and update `apps.json`.
- [ ] **6.3** Update `GENERAL_INSTRUCTIONS.md` Section 8 ("Adding a New App") to reflect the new Cowork-based workflow instead of manual file editing.
- [ ] **6.4** Document the full lifecycle in `CONTRIBUTING.md`: New App → Cowork build → Beta → Infra review → Live → portal cascade.

---

## Key Differences from AppsForHire to Keep in Mind

**SSO vs OTP:** Team-apps uses company SSO (Google/Azure AD) not email OTP. CF Access policy type will be "Include → Emails ending in @tekmetric.com" or "Include → Group → [azure-group-id]" rather than individual email addresses.

**CF Access reusable policy gotcha:** Cloudflare Access has two policy types — app-scoped policies (attached to a single app, editable via `PUT /access/apps/{uid}/policies/{pid}`) and reusable policies (account-level, shared across apps, editable via `PUT /access/policies/{pid}`). Trying to update a reusable policy through the app endpoint returns error code 12130 "can not update reusable policies through this endpoint" with no other warning. Any script or admin portal feature that modifies Access policies must try the app-scoped endpoint first and fall back to the account-level endpoint on a 12130 error. The read endpoint (`GET /access/apps/{uid}/policies`) returns both types — you cannot tell them apart until you try to write.

**Sharing credentials with new contributors:** Use [onetimesecret.com](https://onetimesecret.com) for one-time burn links when sharing the admin secret or a new contributor's CF API token. Never send secrets over email or Slack in plain text. Each contributor should generate their own GitHub Personal Access Token and CF API token — only the shared `ADMIN_SECRET` is ever passed between people.

**No per-app repos:** All team-apps apps live in one repo (`team-apps`), not separate `client-*` repos. The publish flow doesn't create new repos — it updates `apps.json` and triggers a portal cascade within the same repo.

**GitHub Actions CI/CD already exists:** Team-apps already auto-deploys on push. The admin portal's "deploy" action just needs to commit + push changes to `apps.json` and portal files — GitHub Actions handles the rest.

**Compliance requirements are heavier:** Every app must satisfy `GENERAL_INSTRUCTIONS.md` — usage tracking, PII filtering, dual report mode, CPNI compliance. The Cowork app-builder skill must enforce all of these as non-negotiable rules (not optional suggestions).

**Usage tracking is a first-class citizen:** AppsForHire tracks rate limits. Team-apps tracks API cost via `USAGE_STATS` KV. The app-builder skill must always include `recordUsage()` in every new worker it creates.

**Beta → Production gate exists and should stay:** The Infra PR review process is valuable for compliance. The new workflow adds Cowork-based building and admin portal management *around* this gate, not instead of it.

---

## Reference Files in This Session

When building anything for team-apps, consult:
- `GENERAL_INSTRUCTIONS.md` — compliance rules, PII filtering, security checklist, API inventory (non-negotiable)
- `USAGE_TRACKING.md` — KV schema and recordUsage() implementation pattern
- `pwa/index.html` — current production portal (app catalog, design system)
- `pwa/beta/index.html` — current beta portal
- `exec-portal/` — existing exec portal (reference for department portal pattern)
- `beta-auth/` — existing auth experiments (understand before replacing)

---

*Generated from AppsForHire project learnings — March 2026.*
*Maintained by Robert Keller. Feed forward to team-apps Cowork sessions as needed.*
