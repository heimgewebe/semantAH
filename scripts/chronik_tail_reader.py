#!/usr/bin/env python3
"""
Minimaler Reader für Chronik-Tail.
Erzeugt out/insights.daily.json als Lebenszeichen.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def fetch_data(base_url: str, domain: str, limit: int) -> List[Dict[str, Any]]:
    """Fetch tail events from Chronik."""
    url = f"{base_url}/v1/tail?domain={domain}&limit={limit}"
    print(f"Fetching from {url}...", file=sys.stderr)

    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as response:
            if response.status != 200:
                raise RuntimeError(f"Failed to fetch data: HTTP {response.status}")
            data = json.loads(response.read().decode('utf-8'))

            # Expecting a list of events or an object with 'items'
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "items" in data:
                return data["items"]
            else:
                # Fallback: maybe the dict itself is an event? Unlikely for 'tail'.
                print(f"Warning: Unexpected response format: {type(data)}", file=sys.stderr)
                return []
    except urllib.error.URLError as e:
        print(f"Error fetching data from {url}: {e}", file=sys.stderr)
        raise


def process_data(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process events into insights."""
    counts_by_event: Counter[str] = Counter()
    counts_by_status: Counter[str] = Counter()
    last_ts: Optional[str] = None

    # Process events
    for event in events:
        if "event" in event and isinstance(event["event"], str):
            counts_by_event[event["event"]] += 1

        if "status" in event and isinstance(event["status"], str):
            counts_by_status[event["status"]] += 1

        ts = event.get("ts") or event.get("timestamp")
        if ts and isinstance(ts, str):
            if last_ts is None or ts > last_ts:
                last_ts = ts

    # "optional sample mit 3 Events"
    # Assuming tail returns most recent first or last, we just take first 3 available in list
    sample = events[:3] if events else []

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "chronik:aussen.tail",
        "counts_by_event": dict(counts_by_event),
        "counts_by_status": dict(counts_by_status),
        "sample": sample,
        "total_count": len(events)
    }

    if last_ts:
        result["last_seen_ts"] = last_ts

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch daily insights from Chronik.")
    parser.add_argument("--url", default=os.environ.get("CHRONIK_URL", "http://localhost:8080"), help="Base URL for Chronik")
    parser.add_argument("--domain", default="aussen", help="Domain to fetch (default: aussen)")
    parser.add_argument("--limit", type=int, default=200, help="Number of events to fetch")
    parser.add_argument("--output", default="out/insights.daily.json", help="Output file path")

    args = parser.parse_args()

    try:
        events = fetch_data(args.url, args.domain, args.limit)
    except Exception as e:
        print(f"Failed to run job: {e}", file=sys.stderr)
        return 1

    insights = process_data(events)

    output_path = args.output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(insights, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Insights written to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
