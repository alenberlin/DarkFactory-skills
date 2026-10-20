import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import path from "node:path";

const headers = {
  Authorization: "Bearer offline-browser-fixture-administrator-only",
};

test("keyboard, actual workflow, correction history, mobile layout and accessibility", async ({
  page,
  request,
}) => {
  const name = "Offline <img src=x onerror=alert(1)> العربية fixture";
  const response = await request.post("/v1/projects", {
    headers,
    data: {
      source: path.join(process.env.FACTORY_BROWSER_TEST_ROOT, "source"),
      policy: { required_check_kinds: ["test"] },
      blueprint: {
        name,
        architecture:
          "Explicit offline browser fixture with actual protected verification.",
        requirements: [
          {
            id: "FR-001",
            description: "Count correctly",
            acceptance: "Protected behavior passes",
          },
        ],
        tasks: [
          {
            id: "T01",
            description: "Implement the fixture counter",
            requirement_ids: ["FR-001"],
          },
        ],
        checks: [
          {
            id: "unit",
            kind: "test",
            argv: ["python", "-I", "{driver}"],
            driver:
              "from pathlib import Path\nassert Path('value.txt').read_text().startswith('correct')\nprint('criterion checked')\n",
            expected_output: "criterion checked",
          },
        ],
        image: "python:3.12-slim",
        permissions: { local_commits: true, local_integration: true },
        delivery: { required_files: [] },
      },
    },
  });
  expect(response.status(), await response.text()).toBe(201);
  const { id } = await response.json();
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to factory activity" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("article")).toBeFocused();
  await page
    .getByLabel("Administrator credential")
    .fill("incorrect-fixture-credential");
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("access was rejected");
  await expect(page.getByRole("alert")).toBeFocused();
  await page
    .getByLabel("Administrator credential")
    .fill("offline-browser-fixture-administrator-only");
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await page
    .getByRole("button", {
      name: name + " · AWAITING_BLUEPRINT_APPROVAL",
      exact: true,
    })
    .click();
  await expect(page.locator("#projects img")).toHaveCount(0);
  await page.getByRole("button", { name: "Approve this blueprint" }).focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("button", { name: "Start / resume" }),
  ).toBeVisible();
  let releaseStatus;
  const heldStatus = new Promise((resolve) => {
    releaseStatus = resolve;
  });
  let statusContinued;
  const continuedStatus = new Promise((resolve) => {
    statusContinued = resolve;
  });
  await page.route(
    "**/v1/projects",
    async (route) => {
      await heldStatus;
      await route.continue();
      statusContinued();
    },
    { times: 1 },
  );
  const refreshing = page.waitForRequest((request) =>
    request.url().endsWith("/v1/projects"),
  );
  await page.evaluate(() => {
    void run(refresh, false);
  });
  await refreshing;
  await page.getByRole("button", { name: "Start / resume" }).click();
  releaseStatus();
  await continuedStatus;
  await expect
    .poll(
      async () =>
        (await (await request.get(`/v1/projects/${id}`, { headers })).json())
          .project.state,
    )
    .toBe("READY_FOR_HUMAN_ACCEPTANCE");
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await page.getByRole("button", { name: "Request corrections" }).click();
  await expect(page.getByRole("alert")).toContainText("Describe the behavior");
  await page
    .getByLabel("Correction feedback")
    .fill(
      "Exercise the actual scoped correction and preserve original history.",
    );
  await page.getByRole("button", { name: "Request corrections" }).click();
  await expect(page.locator("#detail > .state")).toHaveText("PAUSED");
  const corrected = await (
    await request.get(`/v1/projects/${id}`, { headers })
  ).json();
  expect(corrected.corrections).toHaveLength(1);
  expect(corrected.tasks[0].state).toBe("INTEGRATED");
  expect(corrected.tasks[1].id).toMatch(/^COR/);
  await page.getByRole("button", { name: "Start / resume" }).click();
  await expect
    .poll(
      async () =>
        (await (await request.get(`/v1/projects/${id}`, { headers })).json())
          .project.state,
    )
    .toBe("READY_FOR_HUMAN_ACCEPTANCE");
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Accept this delivery" }),
  ).toBeVisible();
  const a11y = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(a11y.violations).toEqual([]);
  await page.screenshot({
    path: "docs/autopilot/evidence/dashboard-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  const mobile = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(mobile.violations).toEqual([]);
  await page.screenshot({
    path: "docs/autopilot/evidence/dashboard-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Accept this delivery" }).click();
  await expect(page.locator("#detail > .state")).toHaveText("ACCEPTED");
  const final = await (
    await request.get(`/v1/projects/${id}`, { headers })
  ).json();
  expect(final.project.state).toBe("ACCEPTED");
  expect(final.audit_intact).toBe(true);
  expect(final.tasks.every((task) => task.state === "INTEGRATED")).toBe(true);
  await page.route("**/v1/projects", (route) => route.abort());
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("could not be reached");
  await page.unroute("**/v1/projects");
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.locator("#connection")).toHaveText("Connected");
});
