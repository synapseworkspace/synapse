# Wiki UX Roles and Metrics

Synapse core wiki mode uses a simple human-first role model and three UX funnel metrics.

## Friendly Roles

1. **Viewer**
   - Can read published pages and inspect context.
2. **Editor**
   - Can create/edit pages and propose updates.
3. **Approver**
   - Can review drafts and publish trusted changes.
4. **Admin**
   - Can manage workspace policies, ownership, and role mappings.

Notes:
- Internal RBAC claims (`viewer`, `editor`, `reviewer`, `owner`, `admin`) map to these labels in the UI.
- Teams can keep stricter policy enforcement in API/enterprise mode without exposing technical role jargon in core UX.

## UX Funnel Metrics (Core Mode)

Synapse tracks these session/project metrics in UI:

1. **TTFV** (Time to First View)
   - Time from session start to opening first wiki page.
2. **Time to First Publish**
   - Time from session start to first successful publish action.
3. **Click Depth to First Publish**
   - Number of page-open actions before first publish.

Storage:
- Metrics are persisted in browser local storage per project key (`synapse:wiki_ux_metrics:<project_id>`).
- Used for product UX optimization, not governance/audit decisions.
