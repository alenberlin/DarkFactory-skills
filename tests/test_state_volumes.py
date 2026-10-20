"""Exercise actual bounded state filesystems and fail-closed missing-volume recovery."""

import errno
import os
import platform
from pathlib import Path

import pytest

from darkfactory.domain import Policy
from darkfactory.storage import StateError, Store
from darkfactory.volumes import create_volume, detach_volume, inspect_volume
from tests.test_contracts import blueprint


def test_unbounded_host_filesystem_does_not_satisfy_small_kernel_quota(tmp_path: Path) -> None:
    with pytest.raises(StateError, match="bounded filesystem"):
        inspect_volume(tmp_path, 1024)


@pytest.mark.skipif(platform.system() != "Darwin", reason="actual macOS APFS provisioning case")
def test_kernel_disk_exhaustion_preserves_state_and_missing_mount_fails_closed(
    tmp_path: Path,
) -> None:
    image, mount = tmp_path / "state.asif", tmp_path / "bounded-state"
    observed = create_volume(image, mount, 128)
    assert observed["enforcement"] == "kernel-filesystem-capacity"
    assert 0 < observed["capacity_bytes"] <= 128 * 1024 * 1024
    try:
        store = Store(mount)
        project = store.create_project(blueprint(), Policy(required_check_kinds=["test"]))
        store.approve(project, store.project(project)["blueprint_hash"], "human:fixture")
        before = store.project(project)
        probe = mount / "capacity-probe"
        exhausted = False
        with probe.open("xb", buffering=0) as file:
            for _ in range(256):
                try:
                    file.write(b"x" * 1024 * 1024)
                except OSError as error:
                    assert error.errno in (errno.ENOSPC, errno.EDQUOT)
                    exhausted = True
                    break
        assert exhausted, "the actual kernel must refuse writes beyond the bounded filesystem"
        probe.unlink()
        assert Store(mount).project(project) == before
        assert Store(mount).verify_audit()
    finally:
        if "store" in locals():
            store.close()
        if os.path.ismount(mount):
            detach_volume(mount)
    assert image.exists()
    with pytest.raises(StateError, match="not mounted"):
        Store(mount)
    assert not (mount / "factory.sqlite3").exists()


def test_volume_creation_refuses_existing_paths_without_overwriting(tmp_path: Path) -> None:
    if platform.system() != "Darwin":
        with pytest.raises(StateError, match="macOS"):
            create_volume(tmp_path / "state.asif", tmp_path / "mount", 128)
        return
    image = tmp_path / "existing.asif"
    image.write_text("preserve")
    with pytest.raises(StateError, match="new"):
        create_volume(image, tmp_path / "mount", 128)
    assert image.read_text() == "preserve"
