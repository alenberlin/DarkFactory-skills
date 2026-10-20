"""Offline browser fixture: canned proposals, real Docker/Git/checks, no live model access."""

import faulthandler
import json
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn  # noqa: E402 -- this standalone fixture selects only its trusted repository

from darkfactory.adapters import AgentReply, FileEdit  # noqa: E402
from darkfactory.api import create_app  # noqa: E402
from darkfactory.domain import Limits, Role  # noqa: E402
from darkfactory.engine import Engine  # noqa: E402
from darkfactory.services import Factory  # noqa: E402
from darkfactory.storage import Store  # noqa: E402
from tests.test_engine import FixtureAdapter  # noqa: E402


class BrowserFixture(FixtureAdapter):
    """A labeled fixture changes real source when exercising human correction history."""

    def propose(self, context: str, workspace: Path, limits: Limits) -> AgentReply:
        """Return a canned proposal; this fixture provides no evidence of live AI quality."""
        if self.role == Role.BACKEND and json.loads(context)["assignment"]["id"].startswith("COR"):
            return AgentReply(
                status="complete",
                summary="Offline correction fixture",
                files=[FileEdit(path="value.txt", content="correct-repaired")],
            )
        return super().propose(context, workspace, limits)


if __name__ == "__main__":
    if os.environ.get("FACTORY_BROWSER_TRACEBACK"):
        faulthandler.dump_traceback_later(int(os.environ["FACTORY_BROWSER_TRACEBACK"]), repeat=True)
    root = Path(os.environ["FACTORY_BROWSER_TEST_ROOT"])
    if root.resolve().parent != Path(__file__).resolve().parents[1] / ".factory-dev":
        raise ValueError("browser fixture state must remain inside .factory-dev")
    root.mkdir(parents=True, exist_ok=False)
    (root / "source").mkdir()
    store = Store(root / "state")
    factory = Factory(store, Engine(store, lambda a, b, c, role: BrowserFixture(role)))
    stop = threading.Event()

    def dispatch() -> None:
        while not stop.wait(0.1):
            for project in store.projects():
                if project["state"] in ("RUNNING", "FINAL_QA", "PAUSING"):
                    factory.engine.run_one(project["id"], "offline-browser-fixture")

    thread = threading.Thread(target=dispatch, daemon=True)
    thread.start()
    try:
        uvicorn.run(
            create_app(store, "offline-browser-fixture-administrator-only", factory),
            host="127.0.0.1",
            port=31789,
            log_level="warning",
        )
    finally:
        stop.set()
        thread.join(timeout=30)
