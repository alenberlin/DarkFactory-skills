"""Operator CLI and separately supervised worker process entry points."""

from __future__ import annotations

import argparse
import json
import os
import signal
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import uvicorn
from pydantic import ValidationError

from darkfactory.adapters import NativeAdapter
from darkfactory.api import create_app
from darkfactory.discovery import Discovery
from darkfactory.domain import Blueprint, InferenceSpec, Limits, Mode, Policy, ProjectState
from darkfactory.engine import Engine
from darkfactory.execution import BoundaryError
from darkfactory.profiles import Profile
from darkfactory.resources import Resources
from darkfactory.services import Factory
from darkfactory.storage import StateError, Store


def worker(
    store: Store,
    project: str | None = None,
    *,
    once: bool = False,
    foreground: bool = False,
) -> None:
    """Run durable background scheduling independently of any interactive chat.

    Args:
        store: Protected runtime state location.
        project: Optional project restriction.
        once: Perform one dispatch round for diagnostics or service integration tests.
        foreground: Explicit operator-attached execution, allowing non-Strict projects.

    Returns:
        After cooperative shutdown or one dispatch round.
    """
    stop = threading.Event()
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda number, frame: stop.set())
    if foreground and project is None:
        raise StateError("foreground execution requires an explicit project")
    if project and not foreground and store.blueprint(project).mode != Mode.STRICT:
        raise StateError("unattended worker requires Strict; use factory run for foreground modes")
    engine = Engine(store, foreground=foreground)
    owner = "worker-" + uuid.uuid4().hex
    while not stop.is_set():
        for record in store.projects():
            if project and record["id"] != project:
                continue
            if not foreground and store.blueprint(record["id"]).mode != Mode.STRICT:
                continue
            if record["state"] not in ("RUNNING", "PAUSING", "FINAL_QA"):
                continue
            identifier = record["id"]
            try:
                Resources(store, identifier).reap()
                engine.verifier.reconcile(identifier)
                NativeAdapter.reconcile(store, identifier)
                engine.reconcile_usage(identifier)
                if store.project(identifier)["state"] == "BLOCKED":
                    continue
                engine.admit(identifier)
                with ThreadPoolExecutor(
                    max_workers=store.blueprint(identifier).limits.concurrency
                ) as pool:
                    futures = [
                        pool.submit(engine.run_one, identifier, owner + "-" + str(index))
                        for index in range(store.blueprint(identifier).limits.concurrency)
                    ]
                    for future in futures:
                        future.result()
            except (StateError, BoundaryError, ValueError, OSError) as error:
                store.block(identifier, str(error))
        if once:
            return
        if (
            foreground
            and project
            and store.project(project)["state"]
            not in (
                ProjectState.RUNNING,
                ProjectState.PAUSING,
                ProjectState.FINAL_QA,
            )
        ):
            return
        stop.wait(1)
    if (
        foreground
        and project
        and store.project(project)["state"]
        in (
            ProjectState.RUNNING,
            ProjectState.FINAL_QA,
        )
    ):
        store.control(project, "pause", "human:foreground-operator")


def main() -> None:
    """Parse explicit operator commands without granting implicit execution permissions."""
    parser = argparse.ArgumentParser(
        prog="factory", description="DarkFactory Autopilot operator CLI"
    )
    parser.add_argument("--state", type=Path, default=Path(".factory/state"))
    sub = parser.add_subparsers(dest="command", required=True)
    discover = sub.add_parser("discover")
    discover.add_argument("goal")
    discover.add_argument("--inference", type=Path, required=True)
    discover.add_argument("--limits", type=Path, required=True)
    discover.add_argument("--source", type=Path, required=True)
    discover.add_argument("--adapter", choices=["claude", "codex"], required=True)
    discover.add_argument("--profile", type=Path)
    answer = sub.add_parser("answer")
    answer.add_argument("project")
    answer.add_argument("--answers", type=Path, required=True)
    sub.add_parser("status").add_argument("project", nargs="?")
    proposal = sub.add_parser("propose")
    proposal.add_argument("blueprint", type=Path)
    proposal.add_argument("--policy", type=Path)
    proposal.add_argument("--source", type=Path, required=True)
    revision = sub.add_parser("revise")
    revision.add_argument("project")
    revision.add_argument("--blueprint", type=Path, required=True)
    revision.add_argument("--policy", type=Path, required=True)
    approve = sub.add_parser("approve")
    approve.add_argument("project")
    approve.add_argument("--digest", required=True)
    for action in ("start", "pause", "resume", "cancel", "report", "preflight", "retry", "review"):
        action_parser = sub.add_parser(action)
        action_parser.add_argument("project")
        if action == "preflight":
            action_parser.add_argument("--foreground", action="store_true")
    runner = sub.add_parser("worker")
    runner.add_argument("--project")
    runner.add_argument("--once", action="store_true")
    foreground = sub.add_parser("run")
    foreground.add_argument("project")
    foreground.add_argument("--once", action="store_true")
    for action in ("accept", "reject"):
        action_parser = sub.add_parser(action)
        action_parser.add_argument("project")
        action_parser.add_argument("--revision", required=True)
        if action == "reject":
            action_parser.add_argument("--reason", required=True)
            action_parser.add_argument("--criteria", nargs="+")
    export = sub.add_parser("export")
    export.add_argument("project")
    export.add_argument("destination", type=Path)
    backup = sub.add_parser("backup")
    backup.add_argument("destination", type=Path)
    reconcile = sub.add_parser("reconcile-usage")
    reconcile.add_argument("project")
    reconcile.add_argument("usage")
    reconcile.add_argument("--tokens", type=int, required=True)
    reconcile.add_argument("--cost-microusd", type=int)
    reconcile.add_argument("--reference", required=True)
    server = sub.add_parser("serve")
    server.add_argument("--port", type=int, default=8787)
    server.add_argument("--token-file", type=Path, required=True)
    allow = sub.add_parser("allow-finding")
    allow.add_argument("project")
    allow.add_argument("finding")
    allow.add_argument("--revision", required=True)
    allow.add_argument("--reason", required=True)
    revoke = sub.add_parser("revoke-exception")
    revoke.add_argument("project")
    revoke.add_argument("exception")
    volume = sub.add_parser("create-state-volume")
    volume.add_argument("--image", type=Path, required=True)
    volume.add_argument("--mount", type=Path, required=True)
    volume.add_argument("--size-mb", type=int, required=True)
    init_parser = sub.add_parser("init")
    init_parser.add_argument("destination", type=Path)
    init_parser.add_argument("--provider", choices=["openai", "anthropic"], required=True)
    init_parser.add_argument("--model", required=True)
    init_parser.add_argument("--max-tokens", type=int, required=True)
    init_parser.add_argument(
        "--profile", choices=["python", "node", "rust", "node-rust"], required=True
    )
    init_parser.add_argument("--image")
    init_parser.add_argument("--max-cost-microusd", type=int)
    init_parser.add_argument("--input-rate", type=int)
    init_parser.add_argument("--output-rate", type=int)
    init_parser.add_argument("--require-filesystem-quota", action="store_true")
    args = parser.parse_args()
    if args.command == "init":
        from darkfactory.setup import initialize

        try:
            configuration = initialize(
                args.destination,
                args.provider,
                args.model,
                args.max_tokens,
                args.profile,
                image=args.image,
                max_cost_microusd=args.max_cost_microusd,
                input_rate=args.input_rate,
                output_rate=args.output_rate,
                require_filesystem_quota=args.require_filesystem_quota,
            )
            print(json.dumps(configuration, indent=2))
        except (StateError, ValueError, OSError) as error:
            parser.exit(1, "factory: " + str(error) + "\n")
        return
    if args.command == "create-state-volume":
        from darkfactory.volumes import create_volume

        try:
            print(json.dumps(create_volume(args.image, args.mount, args.size_mb), indent=2))
        except (StateError, BoundaryError, OSError) as error:
            parser.exit(1, "factory: " + str(error) + "\n")
        return
    store = Store(args.state)
    factory = Factory(store)
    actor = "human:local-owner"
    output: object = None
    try:
        if args.command == "discover":
            discovery = Discovery(store)
            project = discovery.begin(
                args.goal,
                InferenceSpec.model_validate_json(args.inference.read_text()),
                Limits.model_validate_json(args.limits.read_text()),
                args.source,
                args.adapter,
                profile=Profile.model_validate_json(args.profile.read_text())
                if args.profile
                else None,
            )
            output = {"discovery": project, **discovery.advance(project)}
        elif args.command == "answer":
            output = Discovery(store).advance(args.project, json.loads(args.answers.read_text()))
        elif args.command == "propose":
            blueprint = Blueprint.model_validate_json(args.blueprint.read_text())
            policy = (
                Policy.model_validate_json(args.policy.read_text()) if args.policy else Policy()
            )
            output = factory.propose(blueprint, policy, args.source)
        elif args.command == "approve":
            store.approve(args.project, args.digest, actor)
        elif args.command == "allow-finding":
            output = {
                "id": factory.grant_exception(
                    args.project, args.finding, args.revision, args.reason, actor
                )
            }
        elif args.command == "revoke-exception":
            factory.revoke_exception(args.project, args.exception, actor)
        elif args.command == "revise":
            output = factory.revise(
                args.project,
                Blueprint.model_validate_json(args.blueprint.read_text()),
                Policy.model_validate_json(args.policy.read_text()),
            )
        elif args.command in ("start", "resume"):
            output = factory.start(args.project)
        elif args.command in ("pause", "cancel"):
            factory.control(args.project, args.command, actor)
        elif args.command == "retry":
            factory.retry(args.project, actor)
        elif args.command == "review":
            output = {"reviewed": factory.review(args.project)}
        elif args.command == "status":
            output = store.project(args.project) if args.project else store.projects()
        elif args.command == "preflight":
            output = Engine(store, foreground=args.foreground).admit(args.project)
        elif args.command == "worker":
            worker(store, args.project, once=args.once)
        elif args.command == "run":
            foreground_factory = Factory(store, Engine(store, foreground=True))
            foreground_factory.start(args.project)
            worker(store, args.project, once=args.once, foreground=True)
        elif args.command == "report":
            output = factory.report(args.project)
        elif args.command == "export":
            factory.export(args.project, args.destination)
        elif args.command == "backup":
            store.backup(args.destination)
        elif args.command == "reconcile-usage":
            factory.reconcile_usage(
                args.project, args.usage, args.tokens, args.cost_microusd, args.reference, actor
            )
        elif args.command == "accept":
            factory.accept(args.project, args.revision, actor)
        elif args.command == "reject":
            factory.reject(args.project, args.revision, args.reason, actor, args.criteria)
        elif args.command == "serve":
            token_path: Path = args.token_file
            if token_path.is_symlink() or token_path.stat().st_mode & 0o077:
                raise StateError("admin credential must be an owner-only regular file")
            if token_path.stat().st_uid != os.getuid():
                raise StateError("admin credential must be owned by the operator")
            uvicorn.run(
                create_app(store, token_path.read_text().strip()), host="127.0.0.1", port=args.port
            )
        if output is not None:
            print(json.dumps(output, indent=2))
    except (StateError, BoundaryError, ValueError, OSError) as error:
        message = (
            json.dumps(error.errors(include_input=False, include_context=False))
            if isinstance(error, ValidationError)
            else str(error)
        )
        parser.exit(1, "factory: " + message + "\n")


if __name__ == "__main__":
    main()
