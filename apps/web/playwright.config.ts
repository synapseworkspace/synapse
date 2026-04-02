import { defineConfig } from "@playwright/test";

const webPort = Number(process.env.SYNAPSE_E2E_WEB_PORT || 4173);
const apiPort = Number(process.env.SYNAPSE_E2E_API_PORT || 18180);

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    headless: true,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: "node ./e2e/mock-api-server.mjs",
      url: `http://127.0.0.1:${apiPort}/health`,
      reuseExistingServer: !process.env.CI,
      env: {
        ...process.env,
        SYNAPSE_E2E_API_PORT: String(apiPort),
      },
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${webPort} --strictPort`,
      url: `http://127.0.0.1:${webPort}`,
      reuseExistingServer: !process.env.CI,
    },
  ],
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
});
