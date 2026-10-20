"""Generate published contracts from the executable domain models; never edit output by hand."""

import json
import tempfile
from pathlib import Path

from darkfactory.adapters import AgentReply
from darkfactory.api import create_app
from darkfactory.domain import Blueprint, Policy
from darkfactory.storage import Store


def main() -> None:
    """Export the exact current blueprint, policy and agent proposal schemas."""
    root = Path(__file__).resolve().parents[1] / "schemas"
    root.mkdir(exist_ok=True)
    for name, model in (("blueprint", Blueprint), ("policy", Policy), ("agent-reply", AgentReply)):
        (root / (name + ".schema.json")).write_text(
            json.dumps(model.model_json_schema(), indent=2) + "\n"
        )
    private = root.parent / ".factory-dev"
    private.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="schema-export-", dir=private) as directory:
        app = create_app(Store(Path(directory)), "schema-generation-fixture-no-real-access")
        (root / "openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n")


if __name__ == "__main__":
    main()
