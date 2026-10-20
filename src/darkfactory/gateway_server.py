"""Minimal isolated model-only gateway; executed in its own trusted container.

No controller database, administrative channel or target workspace is mounted.
Credential bytes stay in this process and are never included in diagnostics.
"""

from __future__ import annotations

import hmac
import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def serve(config_path: Path, credential_path: Path, ledger_path: Path) -> None:
    """Serve approved inference routes with atomic conservative token reservations.

    Args:
        config_path: Read-only operator-approved gateway configuration.
        credential_path: Read-only provider credential, inaccessible to task containers.
        ledger_path: Gateway-private measured usage and unreconciled reservations.

    Returns:
        Only after the trusted gateway is stopped.
    """
    config = json.loads(config_path.read_text())
    credential = credential_path.read_text().strip()
    lock = threading.Lock()
    ledger: dict[str, Any] = {
        "tokens": 0,
        "reserved": 0,
        "requests": 0,
        "cost_microusd": 0,
        "unknown": False,
    }

    def persist() -> None:
        temporary = ledger_path.with_suffix(".pending")
        temporary.write_text(json.dumps(ledger))
        with temporary.open("rb") as file:
            os.fsync(file.fileno())
        temporary.replace(ledger_path)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            # Requests can contain credentials or task content; structured ledger is sufficient.
            return

        def do_POST(self) -> None:
            provider = config["provider"]
            route = "/v1/messages" if provider == "anthropic" else "/v1/responses"
            requested = urllib.parse.urlsplit(self.path)
            permitted_query = not requested.query or (
                provider == "anthropic" and requested.query == "beta=true"
            )
            authorized = hmac.compare_digest(
                self.headers.get("Authorization", ""), "Bearer " + config["capability"]
            )
            authorized = authorized or hmac.compare_digest(
                self.headers.get("x-api-key", ""), config["capability"]
            )
            if requested.path != route or not permitted_query or not authorized:
                self.send_error(403, "inference capability or route denied")
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 2 * 1024 * 1024:
                    raise ValueError("request size")
                body = self.rfile.read(size)
                request = json.loads(body)
                if request.get("model") != config["model"]:
                    raise ValueError("unapproved model")
                for tool in request.get("tools", []):
                    if tool.get("type", "function") not in ("function", "custom"):
                        raise ValueError("provider-executed tool denied")
                output_limit = min(
                    int(
                        request.get(
                            "max_tokens",
                            request.get("max_output_tokens", config["max_output_tokens"]),
                        )
                    ),
                    config["max_output_tokens"],
                )
                request["max_tokens" if provider == "anthropic" else "max_output_tokens"] = (
                    output_limit
                )
                if output_limit <= 0:
                    raise ValueError("invalid output token bound")
                # Unknown usage stays reserved; UTF-8 bytes conservatively bound input tokens.
                reservation = len(body) + output_limit
                with lock:
                    if (
                        ledger["unknown"]
                        or ledger["tokens"] + ledger["reserved"] + reservation
                        > config["attempt_tokens"]
                    ):
                        self.send_error(429, "inference token reservation exhausted")
                        return
                    ledger["reserved"] += reservation
                    ledger["requests"] += 1
                    persist()
                headers = {"Content-Type": "application/json"}
                if provider == "anthropic":
                    headers.update({"x-api-key": credential, "anthropic-version": "2023-06-01"})
                    upstream = "https://api.anthropic.com/v1/messages"
                    if requested.query:
                        upstream += "?beta=true"
                    beta = self.headers.get("anthropic-beta", "")
                    if (
                        beta
                        and len(beta) < 1024
                        and all(character.isalnum() or character in "-," for character in beta)
                    ):
                        headers["anthropic-beta"] = beta
                else:
                    headers["Authorization"] = "Bearer " + credential
                    upstream = "https://api.openai.com/v1/responses"
                call = urllib.request.Request(  # noqa: S310 -- fixed HTTPS vendor endpoint
                    upstream, data=json.dumps(request).encode(), headers=headers, method="POST"
                )
                opener = urllib.request.build_opener(NoRedirect())
                with opener.open(call, timeout=config["timeout_seconds"]) as response:
                    payload = response.read(8 * 1024 * 1024 + 1)
                    content_type = response.headers.get("Content-Type", "application/json")
                    if len(payload) > 8 * 1024 * 1024:
                        raise ValueError("provider output exceeded gateway limit")
                usage: dict[str, int] = {}
                if "event-stream" in content_type:
                    for line in payload.splitlines():
                        if not line.startswith(b"data: ") or line == b"data: [DONE]":
                            continue
                        event = json.loads(line[6:])
                        for record in (event, event.get("message", {}), event.get("response", {})):
                            usage.update(record.get("usage", {}))
                else:
                    usage = json.loads(payload).get("usage", {})
                with lock:
                    if "input_tokens" not in usage or "output_tokens" not in usage:
                        ledger["unknown"] = True
                    else:
                        input_tokens = (
                            usage["input_tokens"]
                            + usage.get("cache_creation_input_tokens", 0)
                            + usage.get("cache_read_input_tokens", 0)
                        )
                        output_tokens = usage["output_tokens"]
                        ledger["tokens"] += input_tokens + output_tokens
                        ledger["reserved"] -= reservation
                        if config.get("input_microusd_per_token") is not None:
                            ledger["cost_microusd"] += (
                                input_tokens * config["input_microusd_per_token"]
                                + output_tokens * config["output_microusd_per_token"]
                            )
                    persist()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except (ValueError, TypeError, KeyError, OSError, urllib.error.URLError):
                with lock:
                    ledger["unknown"] = True
                    persist()
                self.send_error(502, "provider request failed; reservation retained")

    persist()
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()  # noqa: S104 -- private Docker network only, no host port


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Prevent provider responses from forwarding credentials to another destination."""

    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        """Deny all redirected inference requests.

        Args:
            req: Original provider request whose redirect is refused.
            fp: Redirect response stream supplied by urllib.
            code: Actual HTTP redirect status.
            msg: HTTP response message supplied by urllib.
            headers: HTTP redirect response headers.
            newurl: Redirect destination that must not be followed.
        """
        return None


if __name__ == "__main__":
    serve(Path("/trusted/config"), Path("/trusted/credential"), Path("/ledger/usage.json"))
