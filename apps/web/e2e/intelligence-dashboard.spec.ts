import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

const HAS_ADVANCED_UI = false;

async function fillFirstVisibleLabel(page: Page, labels: string[], value: string): Promise<boolean> {
  for (const label of labels) {
    const locator = page.getByLabel(label);
    const count = await locator.count();
    for (let i = 0; i < count; i += 1) {
      const input = locator.nth(i);
      const visible = await input.isVisible().catch(() => false);
      if (!visible) continue;
      await input.fill(value);
      return true;
    }
  }
  return false;
}

async function openDashboard(page: Page, mode: "core" | "advanced" = "core") {
  await page.setViewportSize({ width: 1720, height: 1100 });
  await page.goto("/");
  const apiUrlField = page.getByLabel("API URL");
  if ((await apiUrlField.count()) > 0) {
    await apiUrlField.fill("http://127.0.0.1:18180");
  }
  const projectFilled = await fillFirstVisibleLabel(page, ["Workspace", "Project ID"], "omega_demo");
  if (!projectFilled) {
    const settingsButton = page.getByRole("button", { name: "Settings", exact: true }).first();
    if ((await settingsButton.count()) > 0) {
      await settingsButton.click();
      await fillFirstVisibleLabel(page, ["Project ID"], "omega_demo");
      await page.keyboard.press("Escape");
    }
  }
  const reviewerFilled = await fillFirstVisibleLabel(page, ["Reviewer", "Your name"], "qa_reviewer");
  if (!reviewerFilled) {
    const settingsButton = page.getByRole("button", { name: "Settings", exact: true }).first();
    if ((await settingsButton.count()) > 0) {
      await settingsButton.click();
      await fillFirstVisibleLabel(page, ["Reviewer"], "qa_reviewer");
      await page.keyboard.press("Escape");
    }
  }
  const onboardingHeader = page.getByText("Welcome to Synapse Wiki").first();
  if ((await onboardingHeader.count()) > 0) {
    const isOnboardingVisible = await onboardingHeader.isVisible().catch(() => false);
    if (isOnboardingVisible) {
      const skipButton = page.getByRole("button", { name: /Skip|Finish|Close/i }).first();
      if ((await skipButton.count()) > 0) {
        await skipButton.click();
      } else {
        await page.keyboard.press("Escape");
      }
    }
  }
  const refreshButton = page.getByRole("button", { name: /Refresh (Inbox|drafts)/i }).first();
  if ((await refreshButton.count()) > 0) {
    await refreshButton.click();
  } else {
    await page.getByRole("button", { name: /^Sync$/i }).first().click();
  }
  if (mode === "advanced") {
    if (!HAS_ADVANCED_UI) {
      test.skip(true, "advanced UI profile is disabled in this run");
      return;
    }
    await page.getByRole("button", { name: "Refresh Intelligence" }).click();
    await expect(page.getByText("Scheduler Run History (30d)")).toBeVisible();
    await expect(page.getByText("Top alert codes")).toBeVisible();
  } else {
    await expect(
      page.getByText(/(Company Wiki, Written by Agents\.|Synapse Wiki)/i),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Wiki", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Drafts", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Tasks", exact: true })).toBeVisible();
  }
}

test("intelligence run-history and calibration schedule CRUD", async ({ page }) => {
  test.setTimeout(180000);
  await openDashboard(page, "advanced");
  await expect(page.getByText("accuracy_drop_exceeded", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Calibration Operations")).toBeVisible();
  await page.getByRole("button", { name: "Preview due-state" }).click();
  await expect(page.getByText("Command preview", { exact: true })).toBeVisible();
  await expect(page.getByText("Schedule results")).toBeVisible();
  await expect(page.getByText("Schedule Observability")).toBeVisible();
  await expect(page.getByText("Cross-Project Observability")).toBeVisible();
  await page.getByRole("button", { name: "Open timelines" }).first().click();
  await expect(page.getByText("Compare Drill-down")).toBeVisible();
  await expect(page.getByText("Live run readiness")).toBeVisible();
  await expect(page.getByText("Async Operation Queue")).toBeVisible();
  await expect(page.getByText("Queue Throughput Controls")).toBeVisible();
  await expect(page.getByText("Queue Command Center")).toBeVisible();
  await page.getByLabel("Projects (csv)").first().fill("omega_demo,project_b");
  await page.getByRole("button", { name: "Refresh command center" }).click();
  await page.getByLabel("Project", { exact: true }).first().fill("omega_demo");
  await page.getByLabel("Owner name").fill("Ops On-call");
  await page.getByLabel("Owner contact").fill("ops@example.com");
  await page.getByLabel("On-call channel").fill("#ops-oncall");
  await page.getByLabel("Escalation channel").fill("#ops-escalation");
  await page.getByRole("button", { name: "Save ownership routing" }).click();
  await expect(page.getByText("Ownership routing saved", { exact: true })).toBeVisible();
  await expect(page.getByText("owner Ops On-call").first()).toBeVisible();
  await expect(page.getByText("Incident auto-ticket hooks")).toBeVisible();
  await page.getByLabel("Project", { exact: true }).nth(1).fill("omega_demo");
  await page.getByLabel("Open endpoint override", { exact: true }).fill("https://hooks.example.com/incidents/open");
  await page.getByLabel("Resolve endpoint override", { exact: true }).fill("https://hooks.example.com/incidents/resolve");
  await page.getByLabel("Open on health (csv)").fill("critical,healthy");
  await page.getByLabel("Incident hook enabled").check();
  await page.getByRole("button", { name: "Save incident hook" }).click();
  await expect(page.getByText("Incident hook saved", { exact: true })).toBeVisible();
  await page.getByLabel("Alert code", { exact: true }).fill("queue_depth_critical");
  await page.getByRole("textbox", { name: "Provider override" }).click();
  await page.getByRole("option", { name: "PagerDuty preset" }).click();
  await page.getByLabel("Severity map (csv)", { exact: true }).fill("critical=critical,watch=warning,healthy=warning");
  await page.getByLabel("Open on health override (csv)", { exact: true }).fill("critical");
  await page.getByRole("button", { name: "Save incident policy" }).click();
  await expect(page.getByText("Incident policy saved", { exact: true })).toBeVisible();
  await expect(page.getByText("omega_demo • queue_depth_critical • p100 • pagerduty • enabled").first()).toBeVisible();
  await page.getByRole("button", { name: "Simulate policy route" }).click();
  await expect(page.getByText("Simulation decision", { exact: true })).toBeVisible();
  await expect(page.getByText("would not open", { exact: true })).toBeVisible();
  await expect(page.getByText("Incident preflight presets", { exact: true })).toBeVisible();
  await page.getByLabel("Preflight name").fill("Queue depth critical preflight");
  await page.getByLabel("Preflight alert code").fill("queue_depth_critical");
  await page.getByRole("textbox", { name: "Preflight severity" }).click();
  await page.getByRole("option", { name: "critical", exact: true }).click();
  await page.getByRole("button", { name: "Save preflight preset" }).click();
  await expect(page.getByText("Preflight preset saved", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Run preflight checks" }).click();
  await expect(page.getByText(/Preflight checks (found issues|passed)/)).toBeVisible();
  await expect(page.getByText("Project rollups", { exact: true })).toBeVisible();
  await expect(page.getByText("Incident sync schedules", { exact: true })).toBeVisible();
  const incidentScheduleName = `incident-sync-e2e-${Date.now().toString(36)}`;
  await page.getByLabel("Incident sync schedule name").fill(incidentScheduleName);
  await page.getByRole("textbox", { name: "Schedule preset" }).click();
  await page.getByRole("option", { name: "Custom", exact: true }).click();
  await page.getByLabel("Custom interval (minutes)").fill("30");
  await page.getByLabel("Sync window (hours)").fill("12");
  await page.getByRole("button", { name: "Save incident sync schedule" }).click();
  await expect(page.getByText("Incident sync schedule saved", { exact: true })).toBeVisible();
  await expect(page.getByText("Fleet schedule table", { exact: true })).toBeVisible();
  await page.getByLabel("Fleet project filter").fill("omega_demo");
  await page.getByRole("textbox", { name: "Fleet sort by" }).click();
  await page.getByRole("option", { name: "status", exact: true }).click();
  await page.getByRole("textbox", { name: "Fleet sort direction" }).click();
  await page.getByRole("option", { name: "descending", exact: true }).click();
  await page.getByLabel("Fleet due only").check();
  await page.getByLabel("Fleet due only").uncheck();
  await page.getByRole("button", { name: "Refresh fleet" }).click();
  await expect(page.getByText(/page\s+1\/\d+/)).toBeVisible();
  const incidentScheduleRow = page.locator(".mantine-Paper-root").filter({ hasText: incidentScheduleName }).first();
  await expect(incidentScheduleRow).toBeVisible();
  await page.getByRole("button", { name: "Run incident sync schedules" }).click();
  await expect(page.getByText("Incident sync schedules executed", { exact: true })).toBeVisible();
  await expect(page.getByText("Incident sync run timeline", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Refresh run timeline" }).click();
  await expect(page.getByText("Failure class breakdown", { exact: true })).toBeVisible();
  await expect(page.getByText("Latest timeline runs", { exact: true })).toBeVisible();
  await incidentScheduleRow.getByRole("button", { name: "Delete" }).first().click();
  await expect(page.getByText("Incident sync schedule deleted", { exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "Live sync enforcement mode" }).click();
  await page.getByRole("option", { name: "block sync on critical fails" }).click();
  await page.getByLabel("Critical preflight threshold").fill("1");
  await page.getByRole("button", { name: "Save sync enforcement" }).click();
  await expect(page.getByText("Sync enforcement saved", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("preflight block 1", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/preflight block .*critical >= 1 .*pause 4h/).first()).toBeVisible();
  await page.getByRole("button", { name: "Sync incident hooks" }).click();
  await expect(page.getByText("Incident hooks synced", { exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "Live sync enforcement mode" }).click();
  await page.getByRole("option", { name: "off (observe only)" }).click();
  await page.getByRole("button", { name: "Save sync enforcement" }).click();
  await expect(page.getByText("Sync enforcement saved", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("preflight block 0", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("preflight off 2", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Sync incident hooks" }).click();
  await expect(page.getByText("Incident hooks synced", { exact: true })).toBeVisible();
  await expect(page.getByText("incident open").first()).toBeVisible();
  await page.getByRole("textbox", { name: "Provider adapter" }).click();
  await page.getByRole("option", { name: "PagerDuty preset" }).click();
  await page.getByLabel("PagerDuty routing key").fill("pd-routing-key-e2e");
  await page.getByLabel("Dedup key prefix").fill("synapse-e2e");
  await page.getByRole("button", { name: "Save incident hook" }).click();
  await expect(page.getByText("Incident hook saved", { exact: true })).toBeVisible();
  await expect(page.getByText("omega_demo • pagerduty • enabled").first()).toBeVisible();
  await expect(page.getByLabel("PagerDuty routing key")).toHaveValue("********");
  await page.getByRole("button", { name: "Bulk pause window" }).click();
  await expect(page.getByText("Bulk queue pause applied", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Bulk resume now" }).click();
  await expect(page.getByText("Bulk queue resume applied", { exact: true })).toBeVisible();
  await expect(page.getByText("Queue autoscaling recommendations")).toBeVisible();
  await page.getByRole("button", { name: "Refresh autoscaling" }).click();
  await expect(page.getByText("workers delta").first()).toBeVisible();
  await page.getByRole("button", { name: "Apply controls" }).first().click();
  await expect(page.getByText("Recommendation applied", { exact: true })).toBeVisible();
  await expect(page.getByText("Daily queue governance digest")).toBeVisible();
  await page.getByRole("button", { name: "Refresh digest" }).click();
  await expect(page.getByText("Top congestion", { exact: true })).toBeVisible();
  await expect(page.getByText("Incident escalation digest")).toBeVisible();
  await page.getByRole("button", { name: "Refresh escalation digest" }).click();
  await expect(page.getByText("Escalation queue", { exact: true })).toBeVisible();
  await expect(page.getByText("Owner queue performance rollups")).toBeVisible();
  await page.getByRole("button", { name: "Refresh owner rollups" }).click();
  await expect(page.getByText("SLA breaches", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Governance drift dashboard")).toBeVisible();
  await page.getByRole("button", { name: "Refresh governance drift" }).click();
  await expect(page.getByText("Pause age buckets", { exact: true })).toBeVisible();
  await expect(page.getByText("Cross-project incident SLO board")).toBeVisible();
  await page.getByRole("button", { name: "Refresh SLO board" }).click();
  await expect(page.getByText("MTTA/MTTR p90 trend", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Export CSV snapshot" }).click();
  await expect(page.getByText("Queue CSV exported", { exact: true })).toBeVisible();
  await page.getByLabel("Webhook snapshot URL").fill("https://hooks.example.com/synapse/queue");
  await page.getByRole("button", { name: "Send webhook snapshot" }).click();
  await expect(page.getByText("Queue snapshot delivered", { exact: true })).toBeVisible();
  await expect(page.getByText("Queue governance audit")).toBeVisible();
  await page.getByRole("button", { name: "Acknowledge" }).first().click();
  await expect(page.getByText("Audit event acknowledged", { exact: true })).toBeVisible();
  await expect(page.getByText("acknowledged by").first()).toBeVisible();
  await expect(page.getByText("incident_hook_updated").first()).toBeVisible();
  await expect(page.getByText("apply_recommendation").first()).toBeVisible();
  await expect(page.getByText("export_snapshot").first()).toBeVisible();
  await expect(page.getByText("bulk_resume").first()).toBeVisible();
  await page.getByLabel("Pause reason").fill("maintenance window");
  await page.getByRole("button", { name: "Pause queue" }).click();
  await expect(page.getByText("Queue paused", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Resume queue" }).click();
  await expect(page.getByText("Queue resumed", { exact: true })).toBeVisible();
  await page.getByLabel("Confirmation phrase").fill("RUN omega_demo");
  await page.getByLabel("I understand this launches production calibration").check();
  await page.getByRole("button", { name: "Run now", exact: true }).click();
  await expect(page.getByText("Manual run queued", { exact: true })).toBeVisible();
  await expect(page.getByText("Selected run")).toBeVisible();
});

test("calibration schedule CRUD quick flow", async ({ page }) => {
  test.setTimeout(90000);
  await openDashboard(page, "advanced");
  const scheduleName = `omega-nightly-e2e-${Date.now().toString(36)}`;
  await page.getByLabel("Schedule name", { exact: true }).fill(scheduleName);
  await page.getByRole("button", { name: "Create schedule" }).first().click();
  const scheduleCard = page
    .locator('[data-testid^="calibration-schedule-row-"]')
    .filter({ hasText: scheduleName })
    .first();
  await expect(scheduleCard).toBeVisible();
  await scheduleCard.getByRole("button", { name: "Edit" }).first().click();
  await page.getByLabel("Snapshot note").fill("updated by e2e");
  await page.getByRole("button", { name: "Update schedule" }).first().click();
  await expect(page.getByText("Schedule updated")).toBeVisible();

  await scheduleCard.getByRole("button", { name: "Delete" }).first().click();
  await expect(page.getByText("Schedule deleted", { exact: true })).toBeVisible();
});

test("alert routing management and rollback rejection workflow", async ({ page }) => {
  await openDashboard(page, "advanced");
  await expect(page.getByText("Rollback Governance Metrics")).toBeVisible();
  await expect(page.getByText("Rollback Attribution")).toBeVisible();

  const webhook = "https://hooks.slack.com/services/e2e/test/route";
  await page.getByLabel("Webhook URL", { exact: true }).fill(webhook);
  await page.getByLabel("Alert codes (optional)").fill("accuracy_drop_exceeded,guardrails_regressed");
  await page.getByRole("button", { name: "Save target" }).click();
  await expect(page.getByText(webhook)).toBeVisible();

  const targetValue = page.getByText(webhook, { exact: true });
  const targetRow = targetValue.locator("xpath=ancestor::*[contains(@class,'mantine-Paper-root')][1]");
  await targetRow.getByRole("button", { name: "Disable" }).first().click();
  await expect(targetRow.getByText("disabled")).toBeVisible();
  await targetRow.getByRole("button", { name: "Delete" }).first().click();
  await expect(page.getByText(webhook, { exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "Preview", exact: true }).first().click();
  await expect(page.getByText("risk medium")).toBeVisible();
  await page.getByRole("button", { name: "Request rollback" }).first().click();
  await expect(page.getByText("Rollback request created")).toBeVisible();

  await page.getByLabel("Reviewer").fill("qa_reviewer_approver");
  await page.getByLabel("Approve note").first().fill("Looks safe after traffic review");
  await page.getByRole("button", { name: "Approve" }).first().click();
  await expect(page.getByText("Approval recorded")).toBeVisible();
  await page.getByRole("button", { name: "Refresh Attribution" }).click();
  await page.getByRole("button", { name: "Open traces" }).first().click();
  await expect(page.getByText("Rollback Causal Traces")).toBeVisible();

  await page.getByLabel("Reviewer").fill("qa_reviewer_2");
  await page.getByLabel("Reject reason").first().fill("Risk unacceptable for peak hours");
  await page.getByRole("button", { name: "Reject" }).first().click();
  await expect(page.getByText("Request rejected")).toBeVisible();
  await expect(page.getByText("Risk unacceptable for peak hours").first()).toBeVisible();
});

test("task tracker lifecycle flow", async ({ page }) => {
  test.setTimeout(120000);
  await openDashboard(page, "core");
  await expect(page.getByRole("button", { name: /^Sync$/i }).first()).toBeVisible();
  await page.getByRole("button", { name: "Tasks", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Task Tracker" }).first()).toBeVisible();
  await page.getByRole("button", { name: "Refresh Tasks", exact: true }).click();
  await expect(page.getByText("Validate Omega gate access policy", { exact: true }).first()).toBeVisible();

  const taskTitle = `E2E Task ${Date.now().toString(36)}`;
  await page.getByLabel("Title").fill(taskTitle);
  await page.getByLabel("Description").fill("Task tracker flow coverage from Playwright e2e.");
  await page.getByLabel("Assignee").fill("qa_reviewer");
  await page.getByLabel("Entity Key").fill("bc_omega");
  await page.getByLabel("Category").fill("qa_checks");
  await page.getByLabel("Due at (ISO or browser-parseable)").fill("2026-04-10T18:00:00+03:00");
  await page.getByRole("button", { name: "Create Task", exact: true }).click();
  await expect(page.getByText("Task created", { exact: true })).toBeVisible();
  await expect(page.getByText(taskTitle, { exact: true }).first()).toBeVisible();

  await page.getByText(taskTitle, { exact: true }).first().click();
  await page.getByRole("button", { name: "in progress", exact: true }).click();
  await page.getByRole("button", { name: "blocked", exact: true }).click();
  await page.getByRole("button", { name: "done", exact: true }).click();

  await page.locator("textarea").nth(1).fill("E2E comment: task lifecycle validated.");
  await page.getByRole("button", { name: "Add Comment", exact: true }).click();
  await expect(page.getByText("comment", { exact: true }).first()).toBeVisible();

  await page.getByLabel("Reference").fill("draft:e2e-synapse-task");
  await page.getByLabel("Note").fill("Attached from e2e scenario");
  await page.getByRole("button", { name: "Add Link", exact: true }).click();
  await expect(page.getByText("draft:e2e-synapse-task", { exact: true })).toBeVisible();
  await expect(page.getByText("link_added", { exact: true }).first()).toBeVisible();
});

test("wiki lifecycle drill-down links and governance quick actions", async ({ page }) => {
  test.setTimeout(120000);
  await openDashboard(page, "core");
  await page.getByRole("button", { name: "Open operations", exact: true }).click();
  await expect.poll(() => new URL(page.url()).pathname.endsWith("/operations")).toBe(true);
  const lifecycleCard = page.locator("#core-left-lifecycle");
  await expect(lifecycleCard).toBeVisible();
  await expect(lifecycleCard.getByText("Lifecycle", { exact: true })).toBeVisible();
  await expect(lifecycleCard.getByText(/stale/i).first()).toBeVisible();
  await lifecycleCard.getByRole("button", { name: "Show details", exact: true }).click();
  await expect(lifecycleCard.getByTestId("core-lifecycle-action-mix")).toBeVisible();
  await expect(lifecycleCard.getByText(/Action mix \(/i).first()).toBeVisible();
  const actionButtons = lifecycleCard.locator('[data-testid^="core-lifecycle-action-open-"]');
  await expect(actionButtons.first()).toBeVisible();
  const firstActionTestId = (await actionButtons.first().getAttribute("data-testid")) || "";
  const expectedActionKey = firstActionTestId.replace("core-lifecycle-action-open-", "");
  await actionButtons.first().click();
  await expect.poll(() => new URL(page.url()).searchParams.get("wiki_lifecycle_action")).toBe(expectedActionKey);
  const actionDetail = page.getByTestId("wiki-lifecycle-action-detail").first();
  await expect(actionDetail).toBeVisible();
  await expect(actionDetail).toContainText(`Drill-down: ${expectedActionKey}`);
  await actionDetail.getByRole("button", { name: "Clear" }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("wiki_lifecycle_action")).toBeNull();
  await lifecycleCard.getByTestId("core-lifecycle-preset-critical_45").click();
  await expect.poll(() => new URL(page.url()).searchParams.get("wiki_lifecycle_preset")).toBe("critical_45");
  await expect.poll(() => new URL(page.url()).searchParams.get("wiki_lifecycle_stale_days")).toBe("45");
  await expect.poll(() => new URL(page.url()).searchParams.get("wiki_lifecycle_critical_days")).toBe("45");
  await lifecycleCard.getByTestId("core-lifecycle-preset-custom").click();
  await lifecycleCard.getByLabel("Stale days").fill("19");
  await lifecycleCard.getByLabel("Critical days").fill("52");
  await expect.poll(() => new URL(page.url()).searchParams.get("wiki_lifecycle_preset")).toBe("custom");
  await expect.poll(() => new URL(page.url()).searchParams.get("wiki_lifecycle_stale_days")).toBe("19");
  await expect.poll(() => new URL(page.url()).searchParams.get("wiki_lifecycle_critical_days")).toBe("52");
  await lifecycleCard.getByTestId("core-lifecycle-preset-stale_21").click();
  await expect.poll(() => new URL(page.url()).searchParams.get("wiki_lifecycle_preset")).toBe("stale_21");
  await expect.poll(() => new URL(page.url()).searchParams.get("wiki_lifecycle_stale_days")).toBe("21");
  await expect.poll(() => new URL(page.url()).searchParams.get("wiki_lifecycle_critical_days")).toBe("45");

  await page.goto("/operations?project=omega_demo&core_tab=wiki");
  await expect.poll(() => new URL(page.url()).pathname.endsWith("/operations")).toBe(true);
  await expect(page.getByRole("button", { name: "Drafts", exact: true })).toBeVisible();

  await page.goto(
    "/?project=omega_demo&wiki_page=operations%2Fbc-omega-access-policy&core_tab=drafts&wiki_focus=draft_inbox",
  );
  await expect(page.getByRole("heading", { name: "Draft Inbox" }).first()).toBeVisible();
});

test("wiki lifecycle empty-scope fixtures: no_published and all_open_drafts", async ({ page }) => {
  test.setTimeout(120000);
  await openDashboard(page, "core");
  await page.getByRole("button", { name: "Open operations", exact: true }).click();
  await expect.poll(() => new URL(page.url()).pathname.endsWith("/operations")).toBe(true);
  const lifecycleCard = page.locator("#core-left-lifecycle");
  await expect(lifecycleCard).toBeVisible();
  await lifecycleCard.getByRole("button", { name: "Show details", exact: true }).click();

  await page.getByLabel("Workspace").fill("fixture_no_published");
  await page.keyboard.press("Escape");
  await expect(lifecycleCard.getByTestId("core-lifecycle-empty-scope")).toBeVisible();
  await expect(lifecycleCard.getByTestId("core-lifecycle-empty-scope")).toContainText("no_published");
  await expect(lifecycleCard.getByTestId("core-lifecycle-empty-action-create_page")).toBeVisible();

  await page.getByLabel("Workspace").fill("fixture_all_open_drafts");
  await page.keyboard.press("Escape");
  await expect(lifecycleCard.getByTestId("core-lifecycle-empty-scope")).toBeVisible();
  await expect(lifecycleCard.getByTestId("core-lifecycle-empty-scope")).toContainText("all_open_drafts");
  await expect(lifecycleCard.getByTestId("core-lifecycle-empty-action-review_open_drafts")).toBeVisible();
});

test("core route split keeps drafts clean and operations tools isolated", async ({ page }) => {
  test.setTimeout(120000);
  await openDashboard(page, "core");

  await page.goto("/wiki?project=omega_demo&core_tab=drafts");
  await page.getByRole("button", { name: "Drafts", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Draft Inbox" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Open operations", exact: true })).toBeVisible();
  await expect(page.getByText("Migration Mode", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Bootstrap Migration", { exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "Open operations", exact: true }).click();
  await expect.poll(() => new URL(page.url()).pathname.endsWith("/operations")).toBe(true);
  await expect(page.getByText("Migration Mode", { exact: true })).toBeVisible();
  await expect(page.getByText("Bootstrap Migration", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Back to Drafts", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Back to Drafts", exact: true }).click();
  await expect.poll(() => new URL(page.url()).pathname.includes("/wiki")).toBe(true);
  await expect.poll(() => new URL(page.url()).pathname.includes("/operations")).toBe(false);
  await expect(page.getByRole("heading", { name: "Draft Inbox" }).first()).toBeVisible();
  await expect(page.getByText("Migration Mode", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Bootstrap Migration", { exact: true })).toHaveCount(0);

  await page.goto("/wiki?project=omega_demo&core_tab=wiki&wiki_page=operations%2Fbc-omega-access-policy");
  const rightRail = page.locator(".confluence-right-rail");
  await expect(rightRail.getByTestId("core-right-recent-versions")).toBeVisible();
  await expect(rightRail.getByText("Recent versions", { exact: true })).toBeVisible();
  await rightRail.getByTestId("core-right-version-open-2").click();
  const historyDrawer = page.getByTestId("core-history-drawer");
  await expect(historyDrawer).toBeVisible();
  await expect(historyDrawer.getByTestId("core-history-inline-diff")).toBeVisible();
  await expect(historyDrawer.getByText("Comparing v1 → v2.", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(rightRail.getByText("Review workflow", { exact: true })).toHaveCount(0);
  await expect(rightRail.getByText("Space governance", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "History", exact: true }).click();
  await expect(page.getByText("Rollback actions are restricted to Operations route.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Open operations", exact: true }).last().click();
  await expect.poll(() => new URL(page.url()).pathname.endsWith("/operations")).toBe(true);
  await expect(page.getByText("Rollback", { exact: true })).toBeVisible();
});

test("core draft detail shows gatekeeper reason code", async ({ page }) => {
  test.setTimeout(120000);
  await openDashboard(page, "core");

  await page.goto("/wiki?project=omega_demo&core_tab=drafts&wiki_space=operations");
  await page.getByRole("button", { name: "Drafts", exact: true }).click();
  const clearScope = page.getByTestId("core-clear-space-scope");
  if ((await clearScope.count()) > 0) {
    await clearScope.click();
  }
  await page.getByRole("button", { name: "Sync", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Draft Inbox" }).first()).toBeVisible();
  const firstDraft = page.locator('[data-testid^="core-draft-list-item-"]').first();
  await expect(firstDraft).toBeVisible();
  await firstDraft.click();

  const draftDetailPanel = page.getByTestId("core-draft-detail-panel");
  await expect(draftDetailPanel).toBeVisible();
  await expect(draftDetailPanel.getByRole("heading", { name: "Draft Detail" })).toBeVisible();
  await expect(draftDetailPanel.getByText("Gatekeeper Signal", { exact: true })).toBeVisible();
  await expect(draftDetailPanel.getByText(/reason\s+(override_skip_event|routing_policy_hard_block)/i)).toBeVisible();
});

test("retrieval diagnostics shows runtime graph config", async ({ page }) => {
  await openDashboard(page, "advanced");
  const diagnosticsCard = page.locator(".retrieval-diagnostics-card").first();
  await diagnosticsCard.scrollIntoViewIfNeeded();
  await expect(diagnosticsCard.getByText("MCP Retrieval Diagnostics", { exact: true })).toBeVisible();
  await diagnosticsCard.getByLabel("Query", { exact: true }).fill("omega gate access card");
  await diagnosticsCard.getByLabel("Related entity (optional graph hint)", { exact: true }).fill("bc_omega");
  await diagnosticsCard.getByRole("button", { name: "Explain retrieval", exact: true }).click();
  await expect(diagnosticsCard.getByText("Runtime graph config", { exact: true })).toBeVisible();
  await expect(diagnosticsCard.getByText("Context injection policy", { exact: true })).toBeVisible();
  await expect(diagnosticsCard.getByText("max hops 3", { exact: true })).toBeVisible();
  await expect(diagnosticsCard.getByText("hop1 +0.20", { exact: true })).toBeVisible();
  await expect(diagnosticsCard.getByText("filtered", { exact: false }).first()).toBeVisible();
  await expect(diagnosticsCard.getByText("Operational note for", { exact: false }).first()).toBeVisible();
});
