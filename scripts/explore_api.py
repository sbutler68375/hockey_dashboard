"""
Scratch script for Phase 1, Step 1: hit a couple of NHL API endpoints and
print the raw JSON shape so we can see real field names before writing any
collector logic. Not part of the permanent pipeline -- throwaway exploration.
"""

import json

import requests

BASE_URL = "https://api-web.nhle.com/v1"


def peek(url: str, label: str, max_chars: int = 1500) -> None:
    """Fetch a URL and print status + a truncated preview of the JSON."""
    print(f"\n=== {label} ===")
    print(f"GET {url}")
    try:
        resp = requests.get(url, timeout=10)
        print(f"status: {resp.status_code}")
        resp.raise_for_status()
        data = resp.json()
        pretty = json.dumps(data, indent=2)
        print(pretty[:max_chars])
        if len(pretty) > max_chars:
            print(f"... [truncated, {len(pretty)} chars total]")
    except requests.RequestException as exc:
        print(f"REQUEST FAILED: {exc}")


if __name__ == "__main__":
    peek(f"{BASE_URL}/standings/now", "Current standings")
    peek(f"{BASE_URL}/schedule/now", "Current schedule")
    peek(f"{BASE_URL}/roster/TOR/current", "Team roster (Maple Leafs)")
    peek(f"{BASE_URL}/club-stats/TOR/now", "Team stats (Maple Leafs)")
