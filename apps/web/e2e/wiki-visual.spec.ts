import { expect, test, type Page, type TestInfo } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

async function saveVisualSnapshot(page: Page, testInfo: TestInfo, name: string): Promise<void> {
  const outputDir = path.join(testInfo.config.rootDir, ".artifacts", "visual-snapshots");
  await fs.mkdir(outputDir, { recursive: true });
  const normalizedProject = String(testInfo.project.name || "chromium").replace(/[^a-z0-9_-]+/gi, "_");
  const targetPath = path.join(outputDir, `${name}-${normalizedProject}.png`);
  await page.screenshot({ path: targetPath, fullPage: true });
}

async function prepareVisualSnapshotPage(page: Page, path: string): Promise<void> {
  await page.setViewportSize({ width: 1720, height: 1100 });
  await page.goto(path);

  // Keep screenshots deterministic across CI retries by disabling runtime animation.
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation: none !important;
        transition: none !important;
        caret-color: transparent !important;
      }
    `,
  });

  const onboardingHeader = page.getByText("Welcome to Synapse Wiki").first();
  if ((await onboardingHeader.count()) > 0) {
    const visible = await onboardingHeader.isVisible().catch(() => false);
    if (visible) {
      const skipButton = page.getByRole("button", { name: /Skip|Finish|Close/i }).first();
      if ((await skipButton.count()) > 0) {
        await skipButton.click();
      } else {
        await page.keyboard.press("Escape");
      }
    }
  }
}

test("visual snapshot: wiki route", async ({ page }, testInfo) => {
  await prepareVisualSnapshotPage(page, "/wiki?project=omega_demo");
  await expect(page.getByRole("button", { name: "Wiki", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Dispatch Escalation Policy" }).first()).toBeVisible();
  await saveVisualSnapshot(page, testInfo, "wiki-route");
});

test("visual snapshot: operations route", async ({ page }, testInfo) => {
  await prepareVisualSnapshotPage(page, "/operations?project=omega_demo&core_tab=drafts");
  await expect(page.getByRole("button", { name: "Operations", exact: true })).toBeVisible();
  await expect(page.getByText("Migration Mode", { exact: true })).toBeVisible();
  await saveVisualSnapshot(page, testInfo, "operations-route");
});
