"""Offline worker process used only by the actual kill/restart integration test."""

import sys
import time
from pathlib import Path

from darkfactory.adapters import AgentReply, FileEdit
from darkfactory.domain import Limits, Role
from darkfactory.engine import Engine
from darkfactory.execution import DockerExecutor
from darkfactory.resources import Resources
from darkfactory.storage import Store
from tests.test_engine import FixtureAdapter


def main() -> None:
    """Persist a real checkpoint before exposing an interruptible contained command."""
    state, project, phase = sys.argv[1:]
    store = Store(Path(state))

    class WorkerFixture(FixtureAdapter):
        def __init__(self, role: Role) -> None:
            super().__init__(role)
            self.first = True

        def propose(self, context: str, workspace: Path, limits: Limits) -> AgentReply:
            if self.role != Role.BACKEND:
                return super().propose(context, workspace, limits)
            if self.first and phase != "recover":
                self.first = False
                return AgentReply(
                    status="continue",
                    summary="Durable incomplete checkpoint",
                    files=[FileEdit(path="value.txt", content="incomplete")],
                )
            if phase == "interrupt":
                DockerExecutor("python:3.12-slim", Resources(store, project)).run(
                    workspace,
                    ["python", "-c", "import time; time.sleep(120)"],
                    Limits(command_seconds=120),
                    readonly=True,
                )
                raise AssertionError("test controller should have killed this process")
            assert (workspace / "value.txt").read_text() == "incomplete"
            if phase == "disconnect":
                deadline = time.monotonic() + 20
                while not (store.root / "continue.marker").exists():
                    if time.monotonic() >= deadline:
                        raise AssertionError("client did not release the worker fixture")
                    time.sleep(0.05)
            return super().propose(context, workspace, limits)

    Engine(store, lambda a, b, c, role: WorkerFixture(role), lease_seconds=3).run_one(
        project, phase
    )


if __name__ == "__main__":
    main()
