# Operator Runbook: Governance Deep Links

Last updated: 2026-04-05

This runbook shows how to open Synapse Wiki directly in the right review context using URL params.

## Why This Exists

Operators often need to jump into one specific action:
- review stale-page policy timeline;
- assign reviewer;
- create governance task;
- open draft inbox for one page.

Deep links reduce click-depth and make handoffs reproducible.

## URL Parameters

- `project`: workspace/project id.
- `wiki_page`: page slug (`operations/bc-omega-access-policy`).
- `core_tab`: initial tab (`wiki`, `drafts`, `tasks`).
- `wiki_focus`: target section inside core wiki.

Supported `wiki_focus` values:
- `draft_inbox`
- `policy_timeline`
- `policy_edit`
- `review_assignments`

## Canonical Examples

Local dev:

```text
http://localhost:5173/?project=omega_demo&wiki_page=operations%2Fbc-omega-access-policy&core_tab=wiki&wiki_focus=policy_timeline
```

```text
http://localhost:5173/?project=omega_demo&wiki_page=operations%2Fbc-omega-access-policy&core_tab=wiki&wiki_focus=review_assignments
```

```text
http://localhost:5173/?project=omega_demo&wiki_page=operations%2Fbc-omega-access-policy&core_tab=drafts&wiki_focus=draft_inbox
```

Hosted (replace base URL):

```text
https://<your-synapse-host>/?project=omega_demo&wiki_page=operations%2Fbc-omega-access-policy&core_tab=wiki&wiki_focus=policy_edit
```

## Right-Rail Quick Actions (Core Wiki)

Inside `Wiki` tab, page right rail provides:
- `Assign reviewer`
- `Create review task`
- `Resolve` assignment
- `Save policy` in governance panel

From lifecycle diagnostics rows:
- `Open page`
- `Policy`
- `Draft inbox`
- `Assign reviewer`
- `Create review task`

## Suggested Operator Flow

1. Open `policy_timeline` deep link.
2. Check top actor/cadence/checklist transitions.
3. Switch to `review_assignments` deep link.
4. Assign reviewer and create task if stale-risk remains.
5. If needed, open `draft_inbox` deep link and process pending drafts.

## Incident Response Playbooks

### Playbook A: Policy Rollback (P1/P2 Governance Incident)

Use when a newly published policy causes regression in agent outcomes.

1. Open policy timeline deep link:

```text
http://localhost:5173/?project=omega_demo&wiki_page=operations%2Fbc-omega-access-policy&core_tab=wiki&wiki_focus=policy_timeline
```

2. Confirm last policy actor, checklist preset, and transition spike.
3. Open page history and rollback the latest risky revision.
4. Create review task for follow-up verification.
5. Record incident note in page comments with root-cause and rollback reason.

Suggested SLA:
- acknowledge in <= 15 minutes;
- rollback or explicit reject decision in <= 60 minutes.

### Playbook B: Reviewer Assignment SLA Breach

Use when stale critical pages have no active reviewer assignment.

1. Open assignment deep link:

```text
http://localhost:5173/?project=omega_demo&wiki_page=operations%2Fbc-omega-access-policy&core_tab=wiki&wiki_focus=review_assignments
```

2. Assign owner (`Assign reviewer`) and create governance task (`Create review task`).
3. Switch to `Tasks` tab, set priority (`high` or `critical`) and due date.
4. If page has pending drafts, jump to draft inbox and process blocking items.

Suggested SLA:
- assign reviewer in <= 30 minutes for `critical` stale pages;
- first update (publish/review/archive) in <= 4 hours.

## Stale-to-Resolved Drill Pack

Use this sequence when one stale page must be moved to a resolved state quickly.

Assumption in examples:
- project: `omega_demo`
- space: `operations`
- page: `operations/bc-omega-access-policy`

### Step 1: Open scoped stale diagnostics

```text
http://localhost:5173/?project=omega_demo&wiki_space=operations&core_tab=wiki
```

Target timer:
- T+0 to T+5 min: confirm stale severity and open drafts.

### Step 2: Open policy timeline for root-cause

```text
http://localhost:5173/?project=omega_demo&wiki_space=operations&wiki_page=operations%2Fbc-omega-access-policy&core_tab=wiki&wiki_focus=policy_timeline
```

Target timer:
- T+5 to T+15 min: identify last actor/update and checklist transitions.

### Step 3: Assign reviewer + create task

```text
http://localhost:5173/?project=omega_demo&wiki_space=operations&wiki_page=operations%2Fbc-omega-access-policy&core_tab=wiki&wiki_focus=review_assignments
```

Target timer:
- T+15 to T+30 min: reviewer assignment confirmed and governance task created.

### Step 4: Clear draft blockers

```text
http://localhost:5173/?project=omega_demo&wiki_space=operations&wiki_page=operations%2Fbc-omega-access-policy&core_tab=drafts&wiki_focus=draft_inbox
```

Target timer:
- T+30 to T+90 min: pending drafts approved/rejected, page updated.

### Step 5: Verify resolved state

```text
http://localhost:5173/?project=omega_demo&wiki_space=operations&core_tab=wiki
```

Exit criteria:
- page is updated/reviewed/published (or archived with reason);
- no overdue ownerless stale item for that page;
- task has owner, due date, and next action note.

## Empty-Scope Action Rule (When Lifecycle Shows Zero Stale Pages)

Use this quick rule for the `empty_scope` suggestions shown in lifecycle diagnostics:

- `lower_threshold`:
  use when you expect stale content but current stale window is too wide (common during audits).
  Typical action: apply the `21/45` preset and re-check stale list.
- `review_open_drafts`:
  use when lifecycle says `all_open_drafts` (published pages exist but freshness is deferred).
  Typical action: go to Draft Inbox first, resolve blockers, then re-run lifecycle.
- `create_page`:
  use when lifecycle says `no_published` for the selected scope.
  Typical action: create baseline policy/process page before triage.

## Telemetry Thresholds (Action Mix Tuning)

Use `Action mix (7d)` metrics to decide if lifecycle suggestions need tuning:

- Apply rate `< 20%` with `shown_total >= 20`:
  suggestions are likely noisy or badly timed. Review default preset and action labels.
- `review_open_drafts` shown high but applied low:
  Draft Inbox flow is probably blocked (assignment/ownership/policy friction). Fix workflow before changing thresholds.
- `lower_threshold` applied dominates (`> 60%` of applied actions):
  stale window is likely too conservative for this workspace; consider narrower default stale window.
- `create_page` shown repeatedly with low apply:
  scope probably lacks ownership/bootstrap policy. Assign owner and provide template-first page creation.

## Troubleshooting

- If focus section is not visible, increase browser width (recommended >= `1440px`) or scroll the right rail.
- If policy timeline shows fallback source, API summary endpoint may be unavailable; local audit fallback is still valid.
- If quick actions are disabled, verify `Workspace` and `Your name` fields are filled.
