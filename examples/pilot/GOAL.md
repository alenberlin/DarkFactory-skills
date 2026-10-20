# Pending live project-board pilot

This is an intake specification for the approved pilot, not a built application
or a successful factory run. The operator requested local validation first and
explicitly left live inference pending. No provider access or spending is
authorized by this file. Resolve provider/model/limits and enroll a dedicated
credential administratively before using `factory discover`.

Build a local project board with persistent accounts, protected sessions,
owned projects and tasks, task updates, activity records and a browser UI.
Produce a complete reviewable PRD, architecture, design and executable plan.
The final proposal must map these eight criteria to real protected checks and
scoped tasks:

| Criterion | Required observable behavior |
| --- | --- |
| PB-001 | Register/login/logout; unauthenticated access is denied; sessions have secure cookie handling and passwords are stored safely |
| PB-002 | Projects persist in a real local database and remain owned by their account |
| PB-003 | Create/read/update tasks in an owned project; validate inputs and record activity |
| PB-004 | Browser workflows cover login, project creation, task creation and state changes with usable error/empty/loading states |
| PB-005 | A second account cannot enumerate, read or modify another account's projects/tasks; use real HTTP/database tests |
| PB-006 | Actual test, typecheck, lint, build, protected behavioral checks and independent security review pass on the delivered source |
| PB-007 | Backend and frontend work proceed independently after their shared contract; verify merged source, demonstrate a failed check and repair, and kill/restart a real worker safely |
| PB-008 | A fresh installation runs the app from its README/runbook; every criterion links actual evidence and final human acceptance remains separate |

Use the same runtime contracts for the chosen language. Dependencies must be
provisioned in the target image before execution. Include protected separate
driver checks for account access, persistence, task updates and ownership.
Approve the complete generated product blueprint through the operator channel;
approval of the factory upgrade does not approve an unidentified pilot revision.

Do not hand-build a fixture app and present it as live agent work. Preserve real
provider usage, source snapshots, task attempts, independent reviews, browser
proof, repair/restart events and the final acceptance matrix. Public hosting,
billing, production email, external notifications and purchases are outside
pilot scope. The pilot is complete only after the real run and human acceptance.
