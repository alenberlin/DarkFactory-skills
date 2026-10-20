"""Actual skip/no-op output cannot silently pass required protected verification."""

from pathlib import Path

import pytest

from darkfactory.domain import CheckSpec, Policy
from darkfactory.execution import SnapshotStore
from darkfactory.storage import Store
from darkfactory.verification import Verifier
from tests.test_contracts import blueprint


@pytest.mark.docker
@pytest.mark.parametrize(
    "output",
    [
        "1 passed, 1 skipped",
        "1 passed, 1 deselected",
        "# pass 1\\n# skip 1",
        "0 passed; no tests ran",
    ],
)
def test_success_exit_with_skipped_or_empty_required_tests_is_denied(
    tmp_path: Path, output: str
) -> None:
    store = Store(tmp_path / "state")
    source = tmp_path / "source"
    source.mkdir()
    snapshot = SnapshotStore(store.root / "snapshots").capture(source)
    spec = CheckSpec(
        id="unit",
        kind="test",
        argv=["python", "-I", "{driver}"],
        driver=f"print({output!r})\nprint('positive marker')\n",
        expected_output="positive marker",
    )
    project = store.create_project(
        blueprint().model_copy(
            update={
                "checks": [spec],
                "image": "python:3.12-slim",
            }
        ),
        Policy(required_check_kinds=["test"]),
    )
    assert not Verifier(store).run(project, snapshot).allowed
    assert not Verifier(store).records(project)[0]["passed"]
