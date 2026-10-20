"""Trusted driver results are tied to source and preserved through failure."""

from pathlib import Path

import pytest

from darkfactory.domain import CheckSpec, Permissions, Policy
from darkfactory.execution import SnapshotStore
from darkfactory.storage import Store
from darkfactory.verification import Verifier
from tests.test_contracts import blueprint


@pytest.mark.docker
def test_protected_driver_fails_then_passes_actual_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "value.txt").write_text("wrong")
    driver = (
        "from pathlib import Path\n"
        "assert Path('/workspace/value.txt').read_text() == 'correct'\n"
        "print('1 criterion passed')\n"
    )
    spec = CheckSpec(
        id="acceptance",
        argv=["python", "-I", "{driver}"],
        kind="test",
        driver=driver,
        expected_output="1 criterion passed",
    )
    proposal = blueprint().model_copy(
        update={
            "checks": [spec],
            "image": "python:3.12-slim",
            "permissions": Permissions(local_commits=True),
        }
    )
    store = Store(tmp_path / "state")
    project = store.create_project(proposal, Policy(required_check_kinds=["test"]))
    verifier = Verifier(store)
    failed_snapshot = SnapshotStore(store.root / "snapshots").capture(source)
    assert not verifier.run(project, failed_snapshot).allowed
    (source / "value.txt").write_text("correct")
    passed_snapshot = SnapshotStore(store.root / "snapshots").capture(source)
    assert verifier.run(project, passed_snapshot).allowed
    assert not verifier.gate(project, failed_snapshot.digest).allowed
    records = verifier.records(project)
    assert len(records) == 2
    assert records[0]["passed"] == 0 and records[1]["passed"] == 1


@pytest.mark.docker
def test_verification_rejects_source_mutation_and_noop_success(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "value.txt").write_text("correct")
    spec = CheckSpec(
        id="test",
        argv=["python", "-c", "open('value.txt','w').write('fake')"],
        kind="test",
        expected_output="1 criterion passed",
    )
    proposal = blueprint().model_copy(update={"checks": [spec], "image": "python:3.12-slim"})
    store = Store(tmp_path / "state")
    project = store.create_project(proposal, Policy(required_check_kinds=["test"]))
    snapshot = SnapshotStore(store.root / "snapshots").capture(source)
    assert not Verifier(store).run(project, snapshot).allowed
    assert SnapshotStore(store.root / "snapshots").verify(snapshot)


@pytest.mark.docker
def test_blackbox_driver_is_separate_from_generated_application(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text(
        "from http.server import HTTPServer,BaseHTTPRequestHandler\n"
        "class Handler(BaseHTTPRequestHandler):\n"
        " def do_GET(self):\n"
        "  self.send_response(200);self.end_headers();self.wfile.write(b'correct')\n"
        "HTTPServer(('0.0.0.0',8080),Handler).serve_forever()\n"
    )
    driver = (
        "import os,time,urllib.request,pathlib\n"
        "assert not pathlib.Path('/workspace/app.py').exists()\n"
        "for attempt in range(50):\n"
        " try:\n"
        "  response=urllib.request.urlopen(os.environ['FACTORY_TARGET'],timeout=1)\n"
        "  assert response.read()==b'correct'\n"
        "  break\n"
        " except OSError:\n  time.sleep(.1)\n"
        "else:\n raise AssertionError('target did not become ready')\n"
        "print('isolated criterion passed')\n"
    )
    spec = CheckSpec(
        id="blackbox",
        argv=["python", "-I", "{driver}"],
        kind="test",
        driver=driver,
        service_argv=["python", "-I", "app.py"],
        expected_output="isolated criterion passed",
        timeout_seconds=15,
    )
    proposal = blueprint().model_copy(update={"checks": [spec], "image": "python:3.12-slim"})
    store = Store(tmp_path / "state")
    project = store.create_project(proposal, Policy(required_check_kinds=["test"]))
    snapshot = SnapshotStore(store.root / "snapshots").capture(source)
    assert Verifier(store).run(project, snapshot).allowed
