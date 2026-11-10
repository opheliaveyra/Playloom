"""Network-free integration tests for relay gates and cancellation."""
import json
import threading
import unittest
from unittest.mock import patch, MagicMock
from playloom.core import AgentLoop
from playloom.live import main
from playloom.relay import RelayConfig, RelayVisionPolicy, NoRedirect
from test_relay import config, response, PNG

class RelaySafetyTests(unittest.TestCase):
    def test_secret_not_in_config_repr(self):
        self.assertNotIn("unit-test-only", repr(config()))

    def test_invalid_urls(self):
        for url in ("file:///a", "https://a@b/v1", "https://a/?key=x", "https://a/#x",
                    "https://a:bad", "https://a/\nheader"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                RelayConfig(url, "model", "fake")

    def test_redirects_refused(self):
        with self.assertRaises(ValueError):
            NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid")

    def test_missing_key_and_cap_rejected_before_windows(self):
        with patch.dict("os.environ", {}, clear=True), patch("playloom.live.require_windows") as windows:
            with self.assertRaises(SystemExit):
                main(["--live", "--target-title", "Test", "--policy", "relay",
                      "--relay-base-url", "https://relay.invalid", "--relay-model", "model",
                      "--relay-max-requests", "1"])
            windows.assert_not_called()

    def test_upload_declined_before_input_or_transport(self):
        with patch.dict("os.environ", {"PLAYLOOM_RELAY_API_KEY": "fake"}), \
             patch("playloom.live.require_windows"), patch("playloom.live.TargetWindow"), \
             patch("playloom.live.WindowsCapture"), patch("playloom.live.wait_for_focus"), \
             patch("playloom.live.preview"), patch("builtins.input", side_effect=["LIVE", "NO"]), \
             patch("playloom.live.WindowsInput") as inputs, patch("playloom.live.RelayVisionPolicy") as policy:
            self.assertEqual(main(["--live", "--target-title", "Test", "--policy", "relay",
                             "--relay-base-url", "https://relay.invalid", "--relay-model", "model",
                             "--relay-max-requests", "1"]), 0)
            inputs.assert_not_called()
            policy.assert_not_called()

    def test_late_response_after_stop_never_executes(self):
        entered, finish, stop = threading.Event(), threading.Event(), threading.Event()
        def transport(req, timeout):
            entered.set()
            finish.wait(2)
            return response({"reason": "late", "key": "right", "duration": 0.08})
        policy = RelayVisionPolicy(config(allow_remote=True), transport=transport, stop_event=stop)
        inputs, capture, recorder = MagicMock(), MagicMock(), MagicMock()
        capture.screenshot.return_value = PNG
        loop = AgentLoop(capture, policy, inputs, recorder)
        loop.stop_event = stop
        thread = threading.Thread(target=loop.run)
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            stop.set()
            thread.join(1)
            self.assertFalse(thread.is_alive())
            inputs.execute.assert_not_called()
            inputs.release_all.assert_called_once()
        finally:
            finish.set()
            thread.join(2)

    def test_bad_responses_never_execute(self):
        cases = [b"x" * 128001, b"{}", b"null", b'{"choices":[{"message":null}]}',
                 response({"reason":"bad","key":"right","duration":True}),
                 response({"reason":"bad","key":"none","duration":5}),
                 response({"reason":"bad","key":"right","duration":float("nan")})]
        for raw in cases:
            with self.subTest(raw=raw[:40]):
                policy = RelayVisionPolicy(config(allow_remote=True), transport=lambda req,t: raw)
                inputs, capture = MagicMock(), MagicMock()
                capture.screenshot.return_value = PNG
                AgentLoop(capture, policy, inputs, MagicMock(), max_steps=1).run()
                inputs.execute.assert_not_called()
                inputs.release_all.assert_called_once()

    def test_network_error_counted_and_redacted(self):
        def broken(req, timeout):
            raise OSError("unit-test-only")
        policy = RelayVisionPolicy(config(allow_remote=True, max_requests=1), transport=broken)
        reason, actions = policy.decide(PNG, [])
        self.assertEqual(actions, [])
        self.assertNotIn("unit-test-only", reason)
        self.assertEqual(policy.requests_used, 1)
        self.assertEqual(policy.decide(PNG, [])[1], [])

    def test_oversize_image_no_request(self):
        transport = MagicMock()
        policy = RelayVisionPolicy(config(allow_remote=True, max_image_bytes=8), transport=transport)
        self.assertEqual(policy.decide(PNG, [])[1], [])
        transport.assert_not_called()
