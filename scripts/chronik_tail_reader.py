#!/usr/bin/env python3
"""
Minimaler Reader für Chronik-Tail.
Erzeugt out/insights.daily.json als Lebenszeichen.
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def fetch_data(base_url: str, domain: str, limit: int) -> List[Dict[str, Any]]:
    """Fetch tail events from Chronik with Auth."""
    safe_domain = urllib.parse.quote(domain)
    url = f"{base_url}/v1/tail?domain={safe_domain}&limit={limit}"

    print(f"Fetching from {url}...", file=sys.stderr)

    req = urllib.request.Request(url)

    # Add Auth Header
    auth_token = os.environ.get("CHRONIK_AUTH") or os.environ.get("X_AUTH")
    if auth_token:
        req.add_header("X-Auth", auth_token)

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
                print(f"Warning: Unexpected response format: {type(data)}", file=sys.stderr)
                return []
    except urllib.error.URLError as e:
        print(f"Error fetching data from {url}: {e}", file=sys.stderr)
        raise


def parse_ts(ts: Any) -> Optional[datetime]:
    """Robustly parse timestamp to datetime."""
    if not isinstance(ts, str):
        return None
    try:
        # Handles 2023-12-25T12:00:00Z and similar ISO formats
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def process_data(events: List[Dict[str, Any]], domain: str) -> Dict[str, Any]:
    """Process events into insights."""
    counts_by_event: Counter[str] = Counter()
    counts_by_status: Counter[str] = Counter()

    valid_events: List[Tuple[datetime, Dict[str, Any]]] = []

    # Process events
    for event in events:
        if "event" in event and isinstance(event["event"], str):
            counts_by_event[event["event"]] += 1

        if "status" in event and isinstance(event["status"], str):
            counts_by_status[event["status"]] += 1

        ts_val = event.get("ts") or event.get("timestamp")
        dt = parse_ts(ts_val)
        if dt:
            valid_events.append((dt, event))
        else:
            # Keep event for counts but can't sort by time reliably?
            # Or assume input order? We'll just exclude from sorted sample/last_ts calculation
            # if it has no valid TS.
            pass

    # Sort by timestamp descending (newest first)
    valid_events.sort(key=lambda x: x[0], reverse=True)

    sorted_raw_events = [e for _, e in valid_events]

    # Use sorted events for sample if available, else fallback to raw list
    # (if no timestamps were found)
    sample_source = sorted_raw_events if sorted_raw_events else events
    sample = sample_source[:3] if sample_source else []

    last_ts_str: Optional[str] = None
    if valid_events:
        # valid_events[0] is the newest
        last_ts_str = valid_events[0][0].isoformat()

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": f"chronik:{domain}.tail",
        "counts_by_event": dict(counts_by_event),
        "counts_by_status": dict(counts_by_status),
        "sample": sample,
        "total_count": len(events)
    }

    if last_ts_str:
        result["last_seen_ts"] = last_ts_str

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

    insights = process_data(events, args.domain)

    output_path = args.output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(insights, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Insights written to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
