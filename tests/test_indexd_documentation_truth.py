from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_canonical_indexd_architecture_is_linked() -> None:
    architecture = read("docs/indexd-architecture.md")
    assert "keinen HNSW" in architecture
    assert "filters` ist Teil" in architecture
    assert "INDEXD_DB_PATH" in architecture
    assert "O(n × d)" in architecture
    assert "indexd-architecture.md" in read("docs/README.md")
    assert "indexd-architecture.md" in read("README.md")
    assert "indexd-architecture.md" in read("crates/indexd/README.md")


def test_current_indexd_docs_do_not_claim_stub_or_ann_store() -> None:
    crate_readme = read("crates/indexd/README.md")
    api = read("docs/indexd-api.md")
    assert "Aktuell noch Stub" not in crate_readme
    assert "Aktuell liefert der Stub" not in api
    assert '"rationale": ["Tag match' not in api
    assert "filters`-Feld wird akzeptiert, aber noch nicht ausgewertet" in api
    assert "HNSW/Faiss/andere ANN-Indizes" in crate_readme


def test_historical_hnsw_documents_are_marked_non_authoritative() -> None:
    for relative in (
        "docs/hauski.md",
        "docs/blueprint.md",
        "docs/semantAH brainstorm.md",
    ):
        prefix = read(relative)[:800]
        assert "Status: historischer Entwurf" in prefix, relative
        assert "indexd-architecture.md" in prefix, relative


def test_strategy_and_roadmap_match_live_persistence_boundary() -> None:
    strategy = read("docs/semantAH/comprehensive-optimization-strategy.md")
    roadmap = read("docs/roadmap.md")
    config = read("docs/config-reference.md")
    assert "Es fehlen Persistenz" not in strategy
    assert "JSONL-Laden beim Start" in strategy
    assert "damals vorgesehene HNSW-Wrapper wurde nicht umgesetzt" in roadmap
    assert "ausschließlich aus `INDEXD_DB_PATH`" in config
    assert "HTTP-Stub" not in config
    assert "server stub" not in read("crates/indexd/src/main.rs")


def test_documented_indexd_links_resolve() -> None:
    expected = ROOT / "docs/indexd-architecture.md"
    assert expected.is_file()
    for relative in (
        "README.md",
        "docs/README.md",
        "docs/hauski.md",
        "docs/blueprint.md",
        "docs/semantAH brainstorm.md",
        "crates/indexd/README.md",
    ):
        assert "indexd-architecture.md" in read(relative), relative
