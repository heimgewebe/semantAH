#!/usr/bin/env python3
import json, os, datetime, sys

# VAULT_ROOT muss gesetzt sein (z.B. ~/Vaults/main)
vault_root = os.path.expanduser(os.environ.get("VAULT_ROOT",""))
if not vault_root:
    print("ERROR: set VAULT_ROOT to your vault path", file=sys.stderr); sys.exit(2)

out_dir = os.path.join(vault_root, ".gewebe", "insights")
os.makedirs(out_dir, exist_ok=True)

today = datetime.date.today().isoformat()
# TODO: echte Aggregation aus Index/Graph; dies ist ein kontraktkonformer Stub ≤10KB
payload = {
  "ts": today,
  "topics": [["Heimgewebe-Architektur", 0.88], ["Backup-Policy", 0.76]],
  "questions": ["Wie definieren wir Reward X?"],
  "deltas": [{"topic":"Backup-Policy","trend":"+1"}]
}

out_file = os.path.join(out_dir, "today.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False)
print(out_file)
