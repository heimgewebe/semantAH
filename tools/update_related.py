#!/usr/bin/env python3
"""Stub script to SHOW related blocks for Markdown files.

This is a placeholder for the full implementation.
See `docs/blueprint.md` for the full concept.

In this version, it operates in "dry-run" mode by default,
printing the changes to standard output instead of modifying files.
"""

from pathlib import Path

RELATED_BLOCK = """<!-- related:auto:start -->
## Related
- [[Example]] — (0.00; stub)
<!-- related:auto:end -->"""


def show_related_for_note(note: Path) -> None:
    """Prints the related block that would be injected."""
    text = note.read_text(encoding="utf-8") if note.exists() else ""
    if "<!-- related:auto:start -->" in text:
        print(f"[dry-run] Block already exists in {note}, skipping.")
        return

    print(f"--- Changes for {note} ---")
    print(text + "\n" + RELATED_BLOCK)
    print("--- End of changes ---\n")


def main() -> None:
    """Iterates over notes and shows the related blocks."""
    notes_dir = Path("notes")
    if not notes_dir.is_dir():
        print(f"Directory not found: {notes_dir}")
        return

    print("[dry-run] Showing related blocks to be injected.\n")
    for note in notes_dir.glob("*.md"):
        show_related_for_note(note)


if __name__ == "__main__":
    main()
