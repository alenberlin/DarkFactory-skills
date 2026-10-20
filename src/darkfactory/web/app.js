"use strict";
let credential = "";
let selected = null;
let busy = false;
let idle = Promise.resolve();
let projectListFingerprint = "";
let detailFingerprint = "";
const element = (tag, text) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  return node;
};
async function request(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  /** @type {RequestInit} */
  const options = {
    headers: { Authorization: `Bearer ${credential}` },
    signal: controller.signal,
  };
  if (body !== undefined) {
    options.method = "POST";
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  let result;
  try {
    response = await fetch(path, options);
    result = await response.json();
  } catch {
    document.getElementById("connection").textContent =
      "Connection unavailable";
    throw new Error(
      "The factory could not be reached. Check its server, then select Refresh.",
    );
  } finally {
    clearTimeout(timeout);
  }
  if (response.status === 401) {
    credential = "";
    document.getElementById("connection").textContent = "Disconnected";
    throw new Error(
      "Administrator access was rejected. Enter the credential again and select Connect.",
    );
  }
  if (!response.ok)
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Request was rejected. Review the submitted data.",
    );
  return result;
}
async function run(action, interactive = true) {
  if (busy) {
    if (!interactive) return;
    await idle;
    return run(action, interactive);
  }
  busy = true;
  let releaseIdle = () => {};
  idle = new Promise((resolve) => {
    releaseIdle = () => resolve();
  });
  const previousFocus = document.activeElement;
  const focusWasInDetail = document
    .getElementById("detail")
    .contains(previousFocus);
  document.querySelector("main").setAttribute("aria-busy", "true");
  if (interactive) {
    document
      .querySelectorAll("button")
      .forEach((button) => (button.disabled = true));
    document.getElementById("error").textContent = "";
  }
  try {
    await action();
  } catch (error) {
    document.getElementById("error").textContent = error.message;
    if (interactive) document.getElementById("error").focus();
  } finally {
    busy = false;
    document.querySelector("main").setAttribute("aria-busy", "false");
    document
      .querySelectorAll("button")
      .forEach((button) => (button.disabled = false));
    if (
      interactive &&
      previousFocus instanceof HTMLElement &&
      document.activeElement !== document.getElementById("error")
    ) {
      const replacement = previousFocus.isConnected
        ? previousFocus
        : document.getElementById(previousFocus.id) ||
          (focusWasInDetail ? document.getElementById("detail") : null);
      replacement?.focus({ preventScroll: true });
    }
    releaseIdle();
  }
}
async function refresh() {
  const projects = await request("/v1/projects");
  document.getElementById("connection").textContent = "Connected";
  const list = document.getElementById("projects");
  if (projectListFingerprint !== JSON.stringify(projects)) {
    projectListFingerprint = JSON.stringify(projects);
    list.replaceChildren();
    if (!projects.length)
      list.append(
        element(
          "p",
          "No projects yet. Submit a blueprint through the operator CLI.",
        ),
      );
    projects.forEach((project) => {
      const button = element("button", `${project.name} · ${project.state}`);
      button.dataset.project = project.id;
      button.id = "project-" + project.id;
      button.setAttribute("aria-pressed", String(project.id === selected));
      button.onclick = () => run(() => show(project.id));
      list.append(button);
    });
  }
  if (selected) await show(selected);
}
function detailSection(parent, title, value) {
  const details = element("details");
  details.append(element("summary", title));
  details.append(
    element(
      "pre",
      typeof value === "string" ? value : JSON.stringify(value, null, 2),
    ),
  );
  parent.append(details);
}
async function show(id) {
  const report = await request(`/v1/projects/${id}`);
  const fingerprint = id + JSON.stringify(report);
  if (fingerprint === detailFingerprint) return;
  const root = document.getElementById("detail");
  const sameProject = selected === id;
  const focusedId = root.contains(document.activeElement)
    ? document.activeElement.id
    : "";
  /** @type {HTMLTextAreaElement | null} */
  const previousFeedback = document.querySelector("textarea#feedback");
  const feedbackValue =
    sameProject && previousFeedback ? previousFeedback.value : "";
  const expanded = sameProject
    ? [...root.querySelectorAll("details[open] summary")].map(
        (node) => node.textContent,
      )
    : [];
  selected = id;
  document.querySelectorAll("#projects button").forEach((button) => {
    button.setAttribute(
      "aria-pressed",
      String(button.getAttribute("data-project") === id),
    );
  });
  detailFingerprint = fingerprint;
  root.replaceChildren();
  root.append(element("h2", report.project.name));
  const state = element("p", report.project.state);
  state.className = "state";
  state.setAttribute("role", "status");
  root.append(state);
  if (report.blueprint.mode !== "strict")
    root.append(
      element(
        "p",
        "This project uses foreground execution. Start it with factory run from your operator terminal.",
      ),
    );
  if (report.project.error) root.append(element("p", report.project.error));
  const controls = element("div");
  controls.className = "controls";
  function control(label, path, body) {
    const button = element("button", label);
    button.id = "action-" + label.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-");
    button.onclick = () =>
      run(async () => {
        await request(path, body);
        await refresh();
      });
    controls.append(button);
  }
  const base = `/v1/projects/${id}`;
  if (report.project.state === "AWAITING_BLUEPRINT_APPROVAL")
    control("Approve this blueprint", `${base}/approve`, {
      digest: report.project.blueprint_hash,
    });
  if (
    ["READY", "PAUSED", "BLOCKED"].includes(report.project.state) &&
    report.blueprint.mode === "strict"
  )
    control("Start / resume", `${base}/start`, {});
  if (report.project.state === "RUNNING")
    control("Pause safely", `${base}/pause`, {});
  if (!["ACCEPTED", "CANCELLED"].includes(report.project.state))
    control("Cancel project", `${base}/cancel`, {});
  if (report.project.state === "READY_FOR_HUMAN_ACCEPTANCE") {
    control("Accept this delivery", `/v1/deliveries/${id}/accept`, {
      revision: report.project.delivery_digest,
    });
    const label = element("label", "Correction feedback");
    label.htmlFor = "feedback";
    root.append(label);
    const feedback = document.createElement("textarea");
    feedback.id = "feedback";
    feedback.value = feedbackValue;
    feedback.maxLength = 16000;
    feedback.setAttribute("aria-required", "true");
    feedback.setAttribute("aria-describedby", "error");
    root.append(feedback);
    const reject = element("button", "Request corrections");
    reject.id = "action-request-corrections";
    reject.onclick = () =>
      run(async () => {
        if (!feedback.value.trim()) {
          feedback.setAttribute("aria-invalid", "true");
          throw new Error(
            "Describe the behavior that needs correction before submitting feedback.",
          );
        }
        await request(`/v1/deliveries/${id}/reject`, {
          revision: report.project.delivery_digest,
          reason: feedback.value,
        });
        await refresh();
      });
    controls.append(reject);
  }
  root.append(controls);
  const metrics = element("div");
  metrics.className = "metric";
  metrics.append(
    element(
      "p",
      `Measured tokens: ${report.usage.reduce((sum, row) => sum + row.tokens, 0)}`,
    ),
  );
  metrics.append(
    element(
      "p",
      `Reserved tokens: ${report.usage.reduce((sum, row) => sum + row.reserved, 0)}`,
    ),
  );
  metrics.append(
    element("p", `Audit: ${report.audit_intact ? "intact" : "FAILED"}`),
  );
  root.append(metrics);
  root.append(element("h3", "Blueprint"));
  root.append(element("p", report.blueprint.architecture));
  report.blueprint.requirements.forEach((item) =>
    root.append(
      element("p", `${item.id} · ${item.description} — ${item.acceptance}`),
    ),
  );
  root.append(
    element(
      "p",
      `Permissions: local commits ${report.blueprint.permissions.local_commits ? "allowed" : "denied"}; local integration ${report.blueprint.permissions.local_integration ? "allowed" : "denied"}. Token limit: ${report.blueprint.limits.max_tokens}.`,
    ),
  );
  root.append(element("h3", "Dependency plan"));
  const table = element("table");
  table.append(
    element(
      "caption",
      "Task dependencies, attempts and current execution state",
    ),
  );
  const head = element("tr");
  ["Task", "Dependencies", "State", "Attempts", "Diagnostic"].forEach(
    (text) => {
      const cell = element("th", text);
      cell.setAttribute("scope", "col");
      head.append(cell);
    },
  );
  const thead = element("thead");
  thead.append(head);
  table.append(thead);
  const tbody = element("tbody");
  report.tasks.forEach((task) => {
    const row = element("tr");
    [
      task.id,
      JSON.parse(task.spec).dependencies.join(", ") || "None",
      task.state,
      task.attempts,
      task.error || "—",
    ].forEach((value) => row.append(element("td", String(value))));
    tbody.append(row);
  });
  table.append(tbody);
  const tableRegion = element("div");
  tableRegion.className = "task-table";
  tableRegion.setAttribute("role", "region");
  tableRegion.setAttribute(
    "aria-label",
    "Task plan, scroll horizontally for all columns",
  );
  tableRegion.tabIndex = 0;
  tableRegion.append(table);
  root.append(tableRegion);
  detailSection(root, "Blueprint configuration and identity", report.blueprint);
  detailSection(
    root,
    "Task dependencies and assignments",
    report.tasks.map((task) => JSON.parse(task.spec)),
  );
  detailSection(
    root,
    "Requirement acceptance matrix",
    report.acceptance_matrix,
  );
  detailSection(root, "Verification evidence and failures", report.checks);
  detailSection(root, "Independent reviews and findings", {
    reviews: report.reviews,
    findings: report.findings,
    exceptions: report.finding_exceptions,
  });
  detailSection(
    root,
    "Correction requests and task history",
    report.corrections,
  );
  detailSection(root, "Adapter diagnostics", report.adapter_runs);
  detailSection(root, "Persisted event history", report.events);
  root.append(element("p", report.release));
  root.querySelectorAll("details").forEach((node) => {
    if (expanded.includes(node.querySelector("summary").textContent))
      node.open = true;
  });
  if (focusedId)
    (document.getElementById(focusedId) || root).focus({ preventScroll: true });
}
document.getElementById("login").onsubmit = (event) => {
  event.preventDefault();
  const field = document.querySelector("input");
  credential = field.value;
  field.value = "";
  run(refresh);
};
document.getElementById("refresh").onclick = () => run(refresh);
setInterval(() => {
  if (credential && !busy && !document.hidden) run(refresh, false);
}, 10000);
