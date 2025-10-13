#!/usr/bin/env python3
"""Stub script to inject related blocks into Markdown files.

This is a placeholder for the full implementation.
See `docs/blueprint.md` for the full concept.
"""

from pathlib import Path

RELATED_BLOCK = """<!-- related:auto:start -->\n## Related\n- [[Example]] — (0.00; stub)\n<!-- related:auto:end -->\n"""


def inject_related(note: Path) -> None:
    text = note.read_text(encoding="utf-8") if note.exists() else ""
    if "<!-- related:auto:start -->" in text:
        return
    note.write_text(text + "\n" + RELATED_BLOCK, encoding="utf-8")


def main() -> None:
    notes_dir = Path(".gewebe/notes_stub")
    notes_dir.mkdir(exist_ok=True)
    note = notes_dir / "example.md"
    note.write_text("# Example Note\n", encoding="utf-8")
    inject_related(note)
    print("[stub] update_related → injected block into", note)


if __name__ == "__main__":
    main()
