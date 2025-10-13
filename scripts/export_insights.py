#!/usr/bin/env python3
"""
Stub: exportiert Tages-Insights als JSON.
Ziel: $VAULT_ROOT/.gewebe/insights/today.json
"""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

def main() -> int:
    vault_root = os.environ.get("VAULT_ROOT", os.path.expanduser("~/Vaults/main"))
    out_dir = Path(vault_root) / ".gewebe" / "insights"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "today.json"

    now = datetime.now(timezone.utc).astimezone()
    payload = {
        "date": now.date().isoformat(),
        "generated_at": now.isoformat(),
        "version": 1,
        "summary": {
            "notes_processed": 0,
            "embeddings_added": 0,
            "graph_edges_new": 0,
            "top_tags": [],
        },
        "meta": {
            "hostname": os.uname().nodename if hasattr(os, "uname") else "unknown",
            "vault_root": vault_root,
        },
    }
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Wrote insights → {out_file}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
