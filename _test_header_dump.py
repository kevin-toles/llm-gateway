#!/usr/bin/env python3
"""
P0 Header Comparison Test.

Compares what headers the Anthropic SDK sends to api.anthropic.com vs
what the LLM Gateway forwards.

Strategy:
  1. Patch httpx.Client.send() to capture the request headers before sending.
  2. Create an AsyncAnthropic(auth_token="sk-ant-oat01-...") client.
  3. Call messages.create() with max_tokens=1 so we don't burn many credits.
  4. Print the captured headers.
  5. Then create an AsyncAnthropic(api_key="sk-ant-...") client and repeat.
  6. Finally, show a diff table.

Usage:  source .venv/bin/activate && python3 _test_header_dump.py
"""

import os
import json
import textwrap
from difflib import unified_diff

# ── Config ──────────────────────────────────────────────────────────────────
# Use a throwaway test message.  We set max_tokens=1 so the cost is trivial.
AUTH_TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
API_KEY    = os.environ.get("ANTHROPIC_API_KEY", "")

TEST_MESSAGES = [{"role": "user", "content": "Say exactly 'hello'"}]
# ────────────────────────────────────────────────────────────────────────────


def capture_anthropic_headers(client_kwargs: dict, label: str) -> dict[str, str]:
    """Create an AsyncAnthropic client, intercept the first httpx request,
    and return the request headers dict (no real network call).

    Strategy: monkey-patch httpx.AsyncClient.send on the *instance* after
    construction but before the first API call.
    """

    import httpx
    import anthropic

    captured_headers: dict[str, str] = {}

    # Build the client
    client_kwargs_clean = {k: v for k, v in client_kwargs.items() if v}
    client = anthropic.AsyncAnthropic(**client_kwargs_clean)

    # ── Patch the underlying httpx client instance ──────────────────────
    original_send = client._client.send  # AsyncClient.send

    async def patched_send(request: httpx.Request, **kwargs):
        nonlocal captured_headers
        captured_headers = dict(request.headers)
        # Restore original immediately
        client._client.send = original_send
        # Build a mock response that won't blow up in raise_for_status
        mock_resp = httpx.Response(
            status_code=200,
            json={"type": "message", "content": [{"type": "text", "text": "mock"}], "role": "assistant", "id": "mock", "model": "mock", "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}},
        )
        mock_resp._request = request  # httpx 0.28+ requires this for raise_for_status
        return mock_resp

    client._client.send = patched_send  # type: ignore[method-assign]

    import asyncio
    asyncio.run(
        client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1,
            messages=TEST_MESSAGES,
        )
    )

    return captured_headers


def sort_headers(h: dict[str, str]) -> dict[str, str]:
    """Return headers sorted by key, case-insensitive."""
    return dict(sorted(h.items(), key=lambda kv: kv[0].lower()))


def diff_headers(a_label: str, a: dict[str, str], b_label: str, b: dict[str, str]) -> str:
    """Return a unified diff string showing header differences."""
    a_sorted = sort_headers(a)
    b_sorted = sort_headers(b)

    a_lines = [f"{k}: {v}" for k, v in a_sorted.items()]
    b_lines = [f"{k}: {v}" for k, v in b_sorted.items()]

    diff = list(
        unified_diff(
            a_lines,
            b_lines,
            fromfile=a_label,
            tofile=b_label,
            lineterm="",
        )
    )
    return "\n".join(diff)


def header_values_diff(
        a: dict[str, str], b: dict[str, str],
) -> list[tuple[str, str | None, str | None]]:
    """Return a list of (key, a_value, b_value) for entries that differ."""
    all_keys = set(a.keys()) | set(b.keys())
    diffs: list[tuple[str, str | None, str | None]] = []
    for key in sorted(all_keys, key=str.lower):
        va = a.get(key)
        vb = b.get(key)
        if va != vb:
            diffs.append((key, va, vb))
    return diffs


def main():
    if not AUTH_TOKEN and not API_KEY:
        print("ERROR: Set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY env var.")
        print("  export ANTHROPIC_AUTH_TOKEN=sk-ant-oat01-...")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        raise SystemExit(1)

    print("=" * 72)
    print("P0 HEADER COMPARISON TEST")
    print("=" * 72)

    captured: list[tuple[str, dict[str, str]]] = []

    # ── Test 1: auth_token only ──────────────────────────────────────────
    if AUTH_TOKEN:
        print(f"\n{'─' * 72}")
        print(f"Test 1: AsyncAnthropic(auth_token='sk-ant-oat01-...')")
        print(f"{'─' * 72}")
        h1 = capture_anthropic_headers({"auth_token": AUTH_TOKEN}, "auth_token")
        captured.append(("auth_token_only", h1))
        for k, v in sort_headers(h1).items():
            # Mask values for safe display
            masked = v[:20] + "..." if len(v) > 24 else v
            print(f"  {k}: {masked}")
    else:
        print("\n  [SKIP] No ANTHROPIC_AUTH_TOKEN set")

    # ── Test 2: api_key only ─────────────────────────────────────────────
    if API_KEY:
        print(f"\n{'─' * 72}")
        print(f"Test 2: AsyncAnthropic(api_key='sk-ant-...')")
        print(f"{'─' * 72}")
        h2 = capture_anthropic_headers({"api_key": API_KEY}, "api_key")
        captured.append(("api_key_only", h2))
        for k, v in sort_headers(h2).items():
            masked = v[:20] + "..." if len(v) > 24 else v
            print(f"  {k}: {v}")
    else:
        print("\n  [SKIP] No ANTHROPIC_API_KEY set")

    # ── Test 3: both (auth_token + api_key) ──────────────────────────────
    if AUTH_TOKEN and API_KEY:
        print(f"\n{'─' * 72}")
        print(f"Test 3: AsyncAnthropic(auth_token='...', api_key='...') — BOTH")
        print(f"{'─' * 72}")
        h3 = capture_anthropic_headers(
            {"auth_token": AUTH_TOKEN, "api_key": API_KEY}, "both"
        )
        captured.append(("both", h3))
        for k, v in sort_headers(h3).items():
            masked = v[:20] + "..." if len(v) > 24 else v
            print(f"  {k}: {masked}")

    # ── Comparison Table ─────────────────────────────────────────────────
    if len(captured) >= 2:
        print(f"\n{'=' * 72}")
        print("HEADER DIFF TABLE")
        print("=" * 72)

        # Compare first two captures
        label_a, ha = captured[0]
        label_b, hb = captured[1]
        diffs = header_values_diff(ha, hb)

        if not diffs:
            print("\n  [IDENTICAL] No differences found.")
        else:
            print(f"\n  {'Header':<40} {'auth_token':<40} {'api_key':<40}")
            print(f"  {'─'*40} {'─'*40} {'─'*40}")
            for key, va, vb in diffs:
                va_str = (va[:37] + "...") if va and len(va) > 40 else (va or "(absent)")
                vb_str = (vb[:37] + "...") if vb and len(vb) > 40 else (vb or "(absent)")
                print(f"  {key:<40} {va_str:<40} {vb_str:<40}")

    # ── Analysis ─────────────────────────────────────────────────────────
    print(f"\n{'=' * 72}")
    print("ANALYSIS")
    print("=" * 72)

    for label, h in captured:
        api_key_header = h.get("x-api-key")
        auth_header = h.get("authorization")
        print(f"\n  {label}:")
        print(f"    x-api-key present:       {'YES' if api_key_header else 'no'}")
        print(f"    Authorization present:    {'YES' if auth_header else 'no'}")
        if api_key_header:
            print(f"    x-api-key prefix:        {api_key_header[:20]}...")
        if auth_header:
            print(f"    Authorization prefix:    {auth_header[:30]}...")

    print(f"\n{'=' * 72}")
    print("DONE — No real Anthropic API calls were made.")
    print("=" * 72)


if __name__ == "__main__":
    main()
