"""Offline relay policy tests; every request uses a fake transport."""
from __future__ import annotations

import json
import unittest

from playloom.relay import RelayConfig, RelayVisionPolicy

PNG = b"\x89PNG\r\n\x1a\n" + b"dummy-pixels"
URL = "https://relay.example.invalid/v1"
KEY = "unit-test-only"


def response(data):
    return json.dumps({"choices": [{"message": {"content": json.dumps(data)}}]}).encode()


def config(**kwargs):
    return RelayConfig(URL, "vision-test", KEY, **kwargs)


class RelayTests(unittest.TestCase):
    def test_no_network_without_explicit_consent(self):
        calls = []
        policy = RelayVisionPolicy(config(), transport=lambda req, timeout: calls.append(req))
        self.assertEqual(policy.decide(PNG, [] )[1], [])
        self.assertEqual(calls, [])

    def test_compatible_image_request(self):
        calls = []
        def fake(req, timeout):
            calls.append(req)
            return response({"reason": "step right", "key": "right", "duration": 0.08})
        policy = RelayVisionPolicy(config(allow_remote=True), transport=fake)
        reason, actions = policy.decide(PNG, [])
        self.assertEqual(reason, "step right")
        self.assertEqual(actions[0].key, "right")
        self.assertEqual(actions[0].duration, 0.08)
        sent = json.loads(calls[0].data)
        self.assertTrue(sent["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,"))
        self.assertEqual(calls[0].full_url, URL + "/chat/completions")

    def test_budget_stops_second_request(self):
        calls = []
        def fake(req, timeout):
            calls.append(1)
            return response({"reason": "fine", "key": "none", "duration": 0.08})
        policy = RelayVisionPolicy(config(allow_remote=True, max_requests=1), transport=fake)
        policy.decide(PNG, [])
        self.assertEqual(policy.decide(PNG, [])[1], [])
        self.assertEqual(len(calls), 1)

    def test_invalid_model_key_fails_closed(self):
        policy = RelayVisionPolicy(config(allow_remote=True),
               transport=lambda req, timeout: response({"reason":"bad","key":"delete","duration":0.08}))
        self.assertEqual(policy.decide(PNG, [])[1], [])

    def test_invalid_model_duration_fails_closed(self):
        policy = RelayVisionPolicy(config(allow_remote=True),
               transport=lambda req, timeout: response({"reason":"bad","key":"right","duration":3.0}))
        self.assertEqual(policy.decide(PNG, [])[1], [])

    def test_bad_json_and_timeout_fail_closed(self):
        bad = RelayVisionPolicy(config(allow_remote=True), transport=lambda req, t: b"not json")
        self.assertEqual(bad.decide(PNG, [])[1], [])
        def timed_out(req, t):
            raise TimeoutError("network timeout")
        slow = RelayVisionPolicy(config(allow_remote=True), transport=timed_out)
        self.assertEqual(slow.decide(PNG, [])[1], [])

    def test_bad_frame_never_uses_network(self):
        calls = []
        p = RelayVisionPolicy(config(allow_remote=True), transport=lambda req,t: calls.append(1))
        self.assertEqual(p.decide(b"not a PNG", [])[1], [])
        self.assertEqual(calls, [])

    def test_http_remote_rejected(self):
        with self.assertRaises(ValueError):
            RelayConfig("http://relay.example.com/v1", "test", KEY, allow_remote=True)
        self.assertEqual(RelayConfig("http://127.0.0.1:1234/v1", "test", KEY).endpoint,
                         "http://127.0.0.1:1234/v1/chat/completions")

    def test_model_abstention(self):
        p = RelayVisionPolicy(config(allow_remote=True),
                transport=lambda req,t: response({"reason":"wait","key":"none","duration":0.08}))
        self.assertEqual(p.decide(PNG, []), ("wait", []))


if __name__ == "__main__":
    unittest.main()
