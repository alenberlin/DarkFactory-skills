import { defineConfig } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import path from "node:path";

mkdirSync(".factory-dev", { recursive: true });
process.env.FACTORY_BROWSER_TEST_ROOT ||= path.resolve(
  ".factory-dev",
  "browser-" + randomUUID(),
);

/** Browser checks use a separate offline factory and an isolated browser profile. */
export default defineConfig({
  testDir: "./tests/browser",
  workers: 1,
  timeout: 120000,
  expect: { timeout: 30000 },
  outputDir: ".factory-dev/browser-results",
  reporter: [
    ["list"],
    ["json", { outputFile: "docs/autopilot/evidence/browser-tests.json" }],
  ],
  use: {
    baseURL: "http://127.0.0.1:31789",
    channel: process.env.FACTORY_BROWSER_CHANNEL || "chrome",
    headless: true,
    trace: "retain-on-failure",
  },
  webServer: {
    command: ".venv/bin/python tests/dashboard_fixture.py",
    url: "http://127.0.0.1:31789",
    reuseExistingServer: false,
    timeout: 60000,
  },
});
