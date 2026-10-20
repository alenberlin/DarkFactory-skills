"""Operator-created bounded state volumes and observable kernel filesystem limits."""

from __future__ import annotations

import json
import os
import platform
import shutil
from pathlib import Path

from darkfactory.execution import bounded_process
from darkfactory.storage import Record, StateError


def inspect_volume(state: Path, maximum_bytes: int) -> Record:
    """Require state to reside on a filesystem whose total size fits the approved limit.

    Args:
        state: Existing protected state directory on a dedicated bounded volume.
        maximum_bytes: Maximum whole-filesystem capacity authorized in the blueprint.

    Returns:
        Observed mount point, device, total capacity and available bytes. This
        supports operator-provisioned bounded filesystems on macOS and Linux.

    Raises:
        StateError: The path is unsafe or its filesystem is larger than the allowance.
    """
    if state.is_symlink() or not state.is_dir():
        raise StateError("filesystem quota requires an existing real state directory")
    mount = state.resolve()
    while not os.path.ismount(mount) and mount != mount.parent:
        mount = mount.parent
    info = os.statvfs(state)
    capacity = info.f_blocks * info.f_frsize
    if capacity <= 0 or capacity > maximum_bytes:
        raise StateError("state requires a bounded filesystem within its approved storage limit")
    return {
        "mount": str(mount),
        "device": state.stat().st_dev,
        "capacity_bytes": capacity,
        "available_bytes": info.f_bavail * info.f_frsize,
        "enforcement": "kernel-filesystem-capacity",
    }


def create_volume(image: Path, mount: Path, size_mb: int) -> Record:
    """Create and mount a new macOS APFS state image at explicitly supplied local paths.

    Args:
        image: New .asif disk-image path, outside the mount directory.
        mount: New mount directory with an existing parent.
        size_mb: Maximum virtual device size in MiB, including filesystem overhead.

    Returns:
        Observed bounded filesystem metadata after successful attachment.

    Raises:
        StateError: Host, paths, creation, attachment or observed capacity is unsupported.
    """
    if platform.system() != "Darwin":
        raise StateError(
            "automatic volume creation is macOS-only; provision a bounded Linux filesystem"
        )
    if not 128 <= size_mb <= 1048576:
        raise StateError("state volume size must be between 128 and 1048576 MiB")
    image, mount = image.absolute(), mount.absolute()
    for path in (image, mount):
        if path.exists() or path.is_symlink() or not path.parent.is_dir():
            raise StateError("state volume paths must be new with existing parent directories")
        if any(parent.is_symlink() for parent in path.parents):
            raise StateError("state volume paths cannot contain symlinks")
    if image.suffix != ".asif" or image.is_relative_to(mount) or mount.is_relative_to(image):
        raise StateError("use a new .asif image outside its new mount directory")
    binary = shutil.which("diskutil")
    if not binary:
        raise StateError("diskutil image support is required for APFS volume provisioning")
    marker = mount.parent / ("." + mount.name + ".darkfactory-volume.json")
    descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as file:
        json.dump({"mount": str(mount), "image": str(image), "size_mb": size_mb}, file)
    created = bounded_process(
        [
            binary,
            "image",
            "create",
            "blank",
            "--format",
            "ASIF",
            "--size",
            str(size_mb * 1024 * 1024),
            "--volumeName",
            "DarkFactoryState",
            str(image),
        ],
        timeout=120,
        output_bytes=16384,
    )
    if created.exit_code or created.timed_out or created.output_truncated:
        raise StateError("bounded state image creation failed; preserve any partial image")
    image.chmod(0o600)
    attached = bounded_process(
        [binary, "image", "attach", "--nobrowse", "--mountPoint", str(mount), str(image)],
        timeout=60,
        output_bytes=16384,
    )
    if attached.exit_code or attached.timed_out or attached.output_truncated:
        raise StateError("state image attachment failed; preserve the created image")
    mount.chmod(0o700)
    return {"image": str(image), **inspect_volume(mount, size_mb * 1024 * 1024)}


def detach_volume(mount: Path) -> None:
    """Unmount an operator-selected mounted image without deleting its preserved data.

    Args:
        mount: Exact mounted state volume after all its workers and servers have stopped.

    Raises:
        StateError: The host or mount is unsupported, or normal detachment fails.
    """
    if platform.system() != "Darwin" or not os.path.ismount(mount) or mount.is_symlink():
        raise StateError("detach requires an existing macOS state-volume mount")
    binary = shutil.which("diskutil")
    if binary is None:
        raise StateError("disk-image detachment tool unavailable")
    result = bounded_process([binary, "eject", str(mount.resolve())], timeout=30, output_bytes=4096)
    if result.exit_code or result.timed_out:
        raise StateError("state volume remains mounted; stop its processes and retry without force")


def require_registered_mount(state: Path) -> None:
    """Refuse empty replacement state when a registered enclosing volume is detached.

    Args:
        state: Requested controller directory, possibly below a registered mount.

    Raises:
        StateError: A registered enclosing volume is absent or exceeds its bound.
    """
    for candidate in (state.resolve(), *state.resolve().parents):
        marker = candidate.parent / ("." + candidate.name + ".darkfactory-volume.json")
        if marker.is_symlink():
            raise StateError("registered state-volume marker cannot be a symlink")
        if marker.is_file():
            record = json.loads(marker.read_text())
            if record["mount"] != str(candidate) or not os.path.ismount(candidate):
                raise StateError(
                    "registered state volume is not mounted; attach its preserved image"
                )
            inspect_volume(candidate, record["size_mb"] * 1024 * 1024)
            return
