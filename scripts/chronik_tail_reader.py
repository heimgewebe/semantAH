#!/usr/bin/env python3
"""
Minimal chronik tail reader.
Fetches recent events from a chronik instance, calculates basic stats,
and produces an insights artifact.
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from urllib.error import URLError, HTTPError

def parse_ts(ts_str):
    """
    Robust timestamp parsing.
    Expects ISO format, handles 'Z' replacement.
    """
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        return None

def main():
    parser = argparse.ArgumentParser(description="Minimal chronik tail reader")
    parser.add_argument("--url", default=os.environ.get("CHRONIK_URL", "http://localhost:8080"), help="Chronik URL")
    parser.add_argument("--domain", default="aussen", help="Domain to fetch (default: aussen)")
    parser.add_argument("--limit", type=int, default=200, help="Limit number of items (default: 200)")
    parser.add_argument("--output", default="out/insights.daily.json", help="Output JSON file path")

    args = parser.parse_args()

    # Auth check
    auth_token = os.environ.get("CHRONIK_AUTH") or os.environ.get("X_AUTH")
    if not auth_token:
        print("CHRONIK_AUTH fehlt – /v1/tail ist auth-geschützt.", file=sys.stderr)
        sys.exit(2)

    # URL Encoding
    encoded_domain = urllib.parse.quote(args.domain)
    url = f"{args.url.rstrip('/')}/v1/tail?domain={encoded_domain}&limit={args.limit}"

    # Request setup
    req = urllib.request.Request(url)
    req.add_header("X-Auth", auth_token)

    meta_returned = None
    meta_dropped = None
    data = []

    try:
        with urllib.request.urlopen(req) as response:
            data = json.load(response)

            # Meta headers
            meta_returned = response.getheader("X-Chronik-Lines-Returned")
            meta_dropped = response.getheader("X-Chronik-Lines-Dropped")

    except HTTPError as e:
        print(f"HTTP Error fetching data: {e.code} {e.reason}", file=sys.stderr)
        try:
            body = e.read().decode('utf-8', errors='replace')
            print(f"Response body: {body}", file=sys.stderr)
        except Exception:
            pass
        sys.exit(1)
    except URLError as e:
        print(f"URL Error fetching data: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error fetching data: {e}", file=sys.stderr)
        sys.exit(1)

    # Processing
    counts_by_event = {}
    counts_by_status = {}
    valid_events = []

    missing_event_field = 0
    missing_status_field = 0
    missing_ts_field = 0

    raw_events = data if isinstance(data, list) else []

    for item in raw_events:
        # Counts - honest counting
        event_name = item.get("event")
        if isinstance(event_name, str):
            counts_by_event[event_name] = counts_by_event.get(event_name, 0) + 1
        else:
            missing_event_field += 1

        status = item.get("status")
        if isinstance(status, str):
            counts_by_status[status] = counts_by_status.get(status, 0) + 1
        else:
            missing_status_field += 1

        # Timestamp fallback
        ts_str = item.get("ts") or item.get("timestamp")
        dt = parse_ts(ts_str)

        if dt:
            # item with parsed datetime for sorting
            valid_events.append({"dt": dt, "item": item})
        else:
            missing_ts_field += 1

    # Sort by dt desc
    valid_events.sort(key=lambda x: x["dt"], reverse=True)

    # Sample
    if valid_events:
        sample_items = [x["item"] for x in valid_events[:3]]
        last_seen_ts = valid_events[0]["dt"].isoformat()
    else:
        # fallback to first 3 raw if no valid timestamps found
        sample_items = raw_events[:3]
        last_seen_ts = None

    # Output construction
    output_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": f"chronik:{args.domain}.tail",
        "counts_by_event": counts_by_event,
        "counts_by_status": counts_by_status,
        "last_seen_ts": last_seen_ts,
        "sample": sample_items,
        "total_count": len(raw_events),
        "meta": {
            "lines_returned": meta_returned,
            "lines_dropped": meta_dropped,
            "missing_event_field": missing_event_field,
            "missing_status_field": missing_status_field,
            "missing_ts_field": missing_ts_field
        }
    }

    # Ensure output directory exists
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(args.output, "w") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
        f.write("\n")

if __name__ == "__main__":
    main()
