"""Run one actual native CLI against a parent-owned offline provider for interruption tests."""

import sys
from pathlib import Path

from darkfactory.adapters import InferenceSession, NativeAdapter
from darkfactory.domain import InferenceSpec, Limits
from darkfactory.storage import Store

if __name__ == "__main__":
    state, project, network, workspace = sys.argv[1:]
    store = Store(Path(state))
    spec = InferenceSpec(
        provider="anthropic", model="fixture-model", agent_image="darkfactory-native-adapters:0.3.0"
    )
    session = InferenceSession(store, project, "interrupted-native", spec)
    session.network = network
    NativeAdapter(store.blueprint(project).model_copy(update={"inference": spec}), session).propose(
        "Return the offline fixture proposal.", Path(workspace), Limits(command_seconds=60)
    )
