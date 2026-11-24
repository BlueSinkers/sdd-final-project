"""Send POST /swaps requests one after another and report how fast they were.

    python tools/latency_check.py                      # 200 requests to http://localhost:8002
    python tools/latency_check.py https://<swaps-app>  # against the deployed service
    python tools/latency_check.py http://localhost:8002 500

This measures from the caller's side, so it includes the network and, on Azure,
any cold start. The SLO itself is measured from the service's own log lines in
Log Analytics (infra/monitoring/slo_swaps.kql); use this to produce traffic and
as a second opinion. It stores real proposals, so run it against production
sparingly.
"""

import json
import statistics
import sys
import time
import urllib.error
import urllib.request

THRESHOLD_MS = 500
TARGET_PERCENT = 99.0

BODY = json.dumps(
    {
        "proposer_name": "latency-check",
        "offered": {"listing_id": 1, "title": "probe A", "owner_name": "probe", "condition": 4, "estimated_value": 35},
        "requested": {
            "listing_id": 2,
            "title": "probe B",
            "owner_name": "probe",
            "condition": 5,
            "estimated_value": 18,
        },
    }
).encode()


def one_request(url: str) -> tuple[float, bool]:
    request = urllib.request.Request(url, data=BODY, method="POST", headers={"Content-Type": "application/json"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
            ok = response.status == 201
    except (urllib.error.URLError, TimeoutError):
        ok = False
    return (time.perf_counter() - start) * 1000, ok


def main() -> int:
    base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8002"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    results = [one_request(f"{base}/swaps") for _ in range(count)]
    durations = sorted(duration for duration, _ in results)
    good = sum(1 for duration, ok in results if ok and duration < THRESHOLD_MS)
    failed = sum(1 for _, ok in results if not ok)
    achieved = 100 * good / count
    cuts = statistics.quantiles(durations, n=100)
    print(f"{count} x POST {base}/swaps")
    print(f"  p50 {cuts[49]:.1f} ms   p95 {cuts[94]:.1f} ms   p99 {cuts[98]:.1f} ms   max {durations[-1]:.1f} ms")
    print(f"  failed: {failed}")
    print(f"  under {THRESHOLD_MS} ms and successful: {good}/{count} = {achieved:.2f}% (target {TARGET_PERCENT}%)")
    return 0 if achieved >= TARGET_PERCENT else 1


if __name__ == "__main__":
    sys.exit(main())
