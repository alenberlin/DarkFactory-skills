# Dark Factory — agent entry point

This is the canonical entry file for the Dark Factory workflow, and a template. To use it elsewhere, copy this file (with `CLAUDE.md`) into your global agent config or a project root, and replace `<path-to-darkfactory>` below with the path to this pack.

## Dark Factory workflow  (lives at `<path-to-darkfactory>`)

Before engaging, check the current project for a file named `.darkfactory`:

- **`engage`** → read `<path-to-darkfactory>/ORCHESTRATOR.md` and follow it.
- **`ignore`** → proceed normally; do not mention the workflow again.
- **missing** → ask once: *"Engage the Dark Factory workflow for this project? (engage / ignore)"*, then write the answer to `.darkfactory` in the project root so you don't ask again.

Do not load the orchestrator unless engaged. Full setup and behavior: [`docs/WORKFLOW.md`](docs/WORKFLOW.md).
