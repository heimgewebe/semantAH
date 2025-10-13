#!/usr/bin/env python3
"""Stub script for building embeddings and chunk index artifacts.

This is a placeholder for the full implementation.
See `docs/blueprint.md` for the full concept.
"""

from pathlib import Path

OUTPUT = Path(".gewebe/embeddings.parquet")


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if not OUTPUT.exists():
        OUTPUT.write_text("id,text,embedding\n")
    print("[stub] build_index → wrote", OUTPUT)


if __name__ == "__main__":
    main()
