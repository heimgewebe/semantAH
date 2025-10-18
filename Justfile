ingest-leitstand:
	@test -f leitstand/data/aussen.jsonl || { echo "fehlend: leitstand/data/aussen.jsonl"; exit 1; }
	uv run cli/ingest_leitstand.py leitstand/data/aussen.jsonl
