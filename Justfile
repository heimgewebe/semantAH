ingest-leitstand:
	@test -f leitstand/data/aussen.jsonl || { echo "fehlend: leitstand/data/aussen.jsonl"; exit 1; }
	uv run cli/ingest_leitstand.py leitstand/data/aussen.jsonl
default: lint


# Lokaler Helper: Schnelltests & Linter – sicher mit Null-Trennung und Quoting
lint:
    @set -euo pipefail; \
    mapfile -d '' files < <(git ls-files -z -- '*.sh' '*.bash' || true); \
    if [ "${#files[@]}" -eq 0 ]; then echo "keine Shell-Dateien"; exit 0; fi; \
    printf '%s\0' "${files[@]}" | xargs -0 bash -n; \
    shfmt -d -i 2 -ci -sr -- "${files[@]}"; \
    shellcheck -S style -- "${files[@]}"
