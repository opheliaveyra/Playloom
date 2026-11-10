"""Opt-in OpenAI-compatible vision relay policy.

No network access occurs unless explicitly permitted. The policy never executes
model-supplied Python, shell commands, URLs, or tool calls. One valid action per
screenshot is accepted; invalid responses become a no-op.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import json
import queue
import threading
import time
from typing import Callable
from urllib import request
from urllib.parse import urlsplit

from .core import Action, MAX_DURATION


@dataclass(frozen=True)
class RelayConfig:
    base_url: str
    model: str
    api_key: str = field(repr=False)
    allow_remote: bool = False
    max_requests: int = 10
    max_output_tokens: int = 250
    timeout_seconds: float = 15.0
    max_image_bytes: int = 2_000_000

    def __post_init__(self) -> None:
        url = urlsplit(self.base_url.strip())
        if any(c.isspace() or ord(c) < 32 for c in self.base_url) or "\\" in self.base_url:
            raise ValueError("Invalid relay URL")
        try:
            url.port
        except ValueError:
            raise ValueError("Invalid relay port") from None
        if url.scheme not in ("http", "https") or not url.hostname:
            raise ValueError("Invalid relay URL")
        if url.username or url.password or url.query or url.fragment:
            raise ValueError("Relay URL must not include credentials, query, or fragment")
        if url.scheme == "http" and url.hostname.lower() not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("Remote relay must use HTTPS")
        if not self.model.strip() or not self.api_key.strip():
            raise ValueError("Model and API key must be supplied explicitly")
        if not 1 <= self.max_requests <= 100:
            raise ValueError("max_requests must be between 1 and 100")
        if not 1 <= self.max_output_tokens <= 1024:
            raise ValueError("max_output_tokens must be between 1 and 1024")
        if not 1 <= self.timeout_seconds <= 60:
            raise ValueError("timeout_seconds must be between 1 and 60")
        if not 1 <= self.max_image_bytes <= 10_000_000:
            raise ValueError("max_image_bytes out of range")

    @property
    def endpoint(self) -> str:
        url = self.base_url.strip().rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        if url.endswith("/v1"):
            return url + "/chat/completions"
        if urlsplit(url).path not in ("", "/"):
            return url + "/chat/completions"
        return url + "/v1/chat/completions"


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Relay redirects are forbidden")


def _default_transport(req: request.Request, timeout: float) -> bytes:
    with request.build_opener(NoRedirect()).open(req, timeout=timeout) as response:
        if response.geturl() != req.full_url:
            raise ValueError("Unexpected relay response URL")
        # Limit response size; model answers should be small.
        return response.read(128_001)


class RelayVisionPolicy:
    """Implements the Policy interface; safe to test without networking.

    Client/provider compatibility depends on the relay accepting OpenAI's
    /chat/completions image_url message shape. No price assumption is made.
    """

    def __init__(
        self,
        config: RelayConfig,
        *,
        transport: Callable[[request.Request, float], bytes] | None = None,
        stop_event=None,
    ):
        self.config = config
        self.transport = transport or _default_transport
        self.requests_used = 0
        self.stop_event = stop_event or threading.Event()
        self.cost = None  # Relay billing rates are unknown.
        self.tokens = None

    def _request(self, req):
        result = queue.Queue(maxsize=1)
        def run():
            try:
                if self.stop_event.is_set():
                    return
                result.put((True, self.transport(req, self.config.timeout_seconds)))
            except Exception:
                result.put((False, None))
        threading.Thread(target=run, daemon=True).start()
        deadline = time.monotonic() + self.config.timeout_seconds
        while not self.stop_event.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.stop_event.set()
                raise TimeoutError("Relay timed out")
            try:
                ok, raw = result.get(timeout=min(0.05, remaining))
                if not ok:
                    raise OSError("Relay request failed")
                return raw
            except queue.Empty:
                pass
        raise ValueError("Stopped")

    def decide(self, frame: bytes, history: list[dict]) -> tuple[str, list[Action]]:
        if self.stop_event.is_set():
            return "Stopped; no action", []
        if not self.config.allow_remote:
            return "Remote screenshot sharing is disabled; no action", []
        if self.requests_used >= self.config.max_requests:
            return "Request budget exhausted; no action", []
        if not isinstance(frame, bytes) or not frame.startswith(b"\x89PNG\r\n\x1a\n"):
            return "Invalid PNG observation; no action", []
        if len(frame) > self.config.max_image_bytes:
            return "Screenshot exceeds configured size cap; no action", []

        recent = [
            {"actions": row.get("actions", []), "reason": str(row.get("reason", ""))[:100]}
            for row in history[-3:] if isinstance(row, dict)
        ]
        payload = {
            "model": self.config.model,
            "stream": False,
            "max_tokens": self.config.max_output_tokens,
            "messages": [
                {"role": "system", "content": (
                    "You control a harmless test window or a permitted puzzle game. "
                    "Observe the screenshot. Return ONLY a JSON object: "
                    '{"reason":"brief text","key":"left|right|up|down|space|z|x|c|a|s|d|enter|esc|none",'
                    '"duration":0.08}. Use key none to abstain. '
                    f"Duration must be >0 and <= {MAX_DURATION} seconds. "
                    "Never return commands, URLs, or scripts."
                )},
                {"role": "user", "content": [
                    {"type": "text", "text": "Choose the next safe move. Recent actions: " +
                     json.dumps(recent, ensure_ascii=True)},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64," +
                     base64.b64encode(frame).decode("ascii")}},
                ]},
            ],
        }
        req = request.Request(
            self.config.endpoint,
            data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
            headers={"Authorization": "Bearer " + self.config.api_key,
                     "Content-Type": "application/json"},
            method="POST",
        )
        self.requests_used += 1
        try:
            raw = self._request(req)
            if self.stop_event.is_set():
                return "Stopped; no action", []
            if len(raw) > 128_000:
                raise ValueError("Oversized response")
            response = json.loads(raw)
            message = response["choices"][0]["message"]
            if message.get("tool_calls") or message.get("function_call"):
                raise ValueError("Tool calls are forbidden")
            msg = message["content"]
            if isinstance(msg, list):
                msg = "".join(part.get("text", "") for part in msg
                              if isinstance(part, dict) and part.get("type") == "text")
            result = json.loads(msg)
            if not isinstance(result, dict) or set(result) != {"reason", "key", "duration"}:
                raise ValueError("Unexpected decision shape")
            if not isinstance(result["reason"], str) or not isinstance(result["key"], str):
                raise ValueError("Invalid decision types")
            key = result["key"]
            reason = result["reason"][:200]
            duration = result["duration"]
            if isinstance(duration, bool) or not isinstance(duration, (int, float)):
                raise ValueError("Invalid duration")
            if not 0 < duration <= MAX_DURATION:
                raise ValueError("Invalid duration")
            if self.stop_event.is_set():
                return "Stopped; no action", []
            if key == "none":
                return reason or "Model abstained", []
            return reason, [Action(key, float(duration))]
        except (OSError, TimeoutError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
            # Never include model response, URL, authorization, or screenshots in trace.
            return "Relay request or decision invalid: " + type(exc).__name__, []
