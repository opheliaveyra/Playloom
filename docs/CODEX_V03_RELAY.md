# Codex handoff — Playloom v0.3 relay vision

Work in branch `feat/v0.3-relay-vision`, based on v0.2's development branch.
Related: issue #3 and PR #2. Do not merge PR #2 until a human Windows
disposable-window input test has passed.

## Existing seed code

- `playloom/relay.py`: `RelayConfig`, `RelayVisionPolicy`. Default denies
  remote screenshots. Uses Python stdlib, `chat/completions`, image_url PNG,
  strict one-action schema and bounded request count.
- `tests/test_relay.py`: offline fake-transport tests, no real API calls.
- `playloom/disposable_window.py`: isolated Tk input test window.
- `playloom/live.py`: currently a fixed MockPolicy, not yet connected to relay.

**Do not assume** the seed's generic OpenAI-compatible schema works for all
relay sites. Providers may return unsupported formats; fail closed.

## Codex's next implementation tasks

1. **CLI support and credentials**
   - Add a distinct remote opt-in mode to `playloom.live`, e.g.
     `--policy relay --relay-base-url <url> --relay-model <name>`.
   - Read the API key only from a process environment variable such as
     `PLAYLOOM_RELAY_API_KEY`. Never require the user to paste a real key into
     GitHub, code, tests, console output, logs, issue comments or chat.
   - Keep `--policy mock` as default. Require `--live`, exact title, LIVE
     confirmation, **additional clear opt-in that screenshots leave the PC**,
     and successful F12 emergency registration.
   - The program must refuse remote policy use if the key is missing or
     `--relay-max-requests` is not positive. Never run without hard limits.
   - A URL provided by the user should be treated as a config value, never
     interpreted as shell commands; avoid leaking key in HTTP errors.

2. **Request/decision behavior**
   - Build compatible PNG `image_url` requests with bounded size and output
     tokens, strict JSON single action; malformed, timed-out, denied or
     budget-exhausted responses must generate **zero physical key events**.
   - Explicitly support a `none`/wait decision.
   - Add robust stop behavior if F12 is pressed during a slow model request.
     The loop must never execute a decision that arrives after stop.
   - Limit total attempts and optionally per-session time; separate *request
     count* from unknown monetary cost. Do not promise a precise currency cap
     when a relay's billing rates cannot be verified. Display request count.
   - Guard against oversized HTTP responses and redirects that could forward
     auth headers away from the configured relay.

3. **Real demo**
   - Demonstrate an offline fake-transport decision that visibly moves a
     square in the disposable Tk window **only after** the user authorizes it.
   - Propose a local replay or deterministic fake model before spending any
     relay balance.
   - Only after the user supplies their own model/Base URL/Key locally, add an
     opt-in single-request smoke-test command. No free-form background sends.
   - Do not access the user's Silksong installation, personal game saves,
     clipboard, browser credentials or unrelated windows.

4. **Quality gates**
   - Unit tests for no-consent, key missing, invalid URL, invalid PNG,
     invalid response/key/duration, network errors, exhausted limit, remote
     confirmation, F12 stop while waiting, and key never pressed on failures.
   - Keep Windows/Linux Python 3.11 and 3.12 CI green.
   - Update README with precise Windows PowerShell run example, no secrets,
     support disclaimers and request-cost guidance.
   - Open a **draft PR targeting `feat/v0.2-windows-live`** (not main) and
     write what was actually tested. Do not auto-merge.

## Success criterion

The v0.3 policy can consume a screenshot and choose a safe, strictly
validated action. A user can explicitly select an OpenAI-compatible relay
endpoint and its vision model, with secret supplied by environment only.
Remote screenshot sharing remains off unless separately consented.
