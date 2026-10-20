"""Keep temporary integration resources within the approved workspace."""

import uuid
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Create the parent of pytest's explicitly configured temporary directory."""
    (Path(config.rootpath) / ".factory-dev").mkdir(exist_ok=True)
    if config.option.basetemp is None:
        # Reusing a deleted bind parent can retain stale file-share inodes in Docker Desktop.
        config.option.basetemp = str(
            Path(config.rootpath) / ".factory-dev" / ("pytest-" + uuid.uuid4().hex)
        )
