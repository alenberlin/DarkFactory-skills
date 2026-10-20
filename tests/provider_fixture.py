"""Offline canned provider protocol, never a real model or live pilot substitute."""

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    """Emit minimal native SDK streaming envelopes for a fixed AgentReply fixture."""

    count = 0

    def log_message(self, format: str, *args: object) -> None:
        """Keep capability-bearing requests out of fixture logs."""
        return

    def do_POST(self) -> None:
        """Return canned Anthropic or OpenAI streaming content with no outside network."""
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        delay = Path("/workspace/delay-seconds")
        if delay.exists():
            print("offline-fixture-request-received", flush=True)
            time.sleep(float(delay.read_text()))
        reply = json.loads(Path("/workspace/reply.json").read_text())
        events: list[dict[str, object]] = []
        text = json.dumps(reply)
        if self.path.startswith("/v1/messages"):
            message = {
                "id": "msg_fixture",
                "type": "message",
                "role": "assistant",
                "model": body["model"],
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 0},
            }
            tool = Handler.count == 0
            content = (
                {"type": "tool_use", "id": "tool_fixture", "name": "StructuredOutput", "input": {}}
                if tool
                else {"type": "text", "text": ""}
            )
            delta = (
                {"type": "input_json_delta", "partial_json": text}
                if tool
                else {"type": "text_delta", "text": "Fixture proposal"}
            )
            events = [
                {"type": "message_start", "message": message},
                {"type": "content_block_start", "index": 0, "content_block": content},
                {"type": "content_block_delta", "index": 0, "delta": delta},
                {"type": "content_block_stop", "index": 0},
                {
                    "type": "message_delta",
                    "delta": {
                        "stop_reason": "tool_use" if tool else "end_turn",
                        "stop_sequence": None,
                    },
                    "usage": {"output_tokens": 20},
                },
                {"type": "message_stop"},
            ]
        elif self.path == "/v1/responses":
            message = {
                "id": "msg_fixture",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "phase": "final_answer",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
            response = {
                "id": "resp_fixture",
                "object": "response",
                "created_at": 1,
                "status": "completed",
                "output": [message],
                "model": body["model"],
                "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            }
            events = [
                {
                    "type": "response.created",
                    "response": {**response, "status": "in_progress", "output": []},
                },
                {"type": "response.output_item.added", "output_index": 0, "item": message},
                {
                    "type": "response.output_text.delta",
                    "output_index": 0,
                    "content_index": 0,
                    "item_id": "msg_fixture",
                    "delta": text,
                },
                {"type": "response.output_item.done", "output_index": 0, "item": message},
                {"type": "response.completed", "response": response},
            ]
        else:
            self.send_error(403)
            return
        Handler.count += 1
        payload = "".join(
            "event: " + str(event["type"]) + "\ndata: " + json.dumps(event) + "\n\n"
            for event in events
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()  # noqa: S104 -- isolated fixture network
