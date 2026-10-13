from __future__ import annotations

import json
import os
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen


BASE_URL = os.getenv("TAAS_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def request_json(path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"{BASE_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    with urlopen(request, timeout=5) as response:
        return json.load(response)


def main() -> int:
    try:
        health = request_json("/api/health")
        meta = request_json("/api/meta")
        series = request_json("/api/traffic/series?corridor=all")
        scenario = request_json("/api/scenarios/evaluate", meta["defaults"])
    except (URLError, TimeoutError, ValueError) as exc:
        print(f"SMOKE FAIL: {exc}", file=sys.stderr)
        return 1

    checks = {
        "health": health.get("status") == "ok",
        "stations": health.get("stations") == 56,
        "minutes": health.get("minutes") == 150,
        "15m_buckets": len(series.get("series", [])) == 10,
        "scenario_policies": len(scenario.get("policies", [])) == 6,
        "value_type": scenario.get("value_type") == "assumed",
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        print(f"SMOKE FAIL: {', '.join(failed)}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", "base_url": BASE_URL, "checks": checks}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
