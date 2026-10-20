"""Run one actual contained verification for parent-owned interruption tests."""

import sys
from pathlib import Path

from darkfactory.execution import Snapshot
from darkfactory.storage import Store
from darkfactory.verification import Verifier

if __name__ == "__main__":
    state, project, source = sys.argv[1:]
    store = Store(Path(state))
    Verifier(store).run(project, Snapshot(source, store.root / "snapshots" / source / "source"))
