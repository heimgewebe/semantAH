Alles klar – ich setze dir jetzt die finale, maximal umfassende Blaupause für dein vault-gewebe auf. Damit hast du einen selbstvernetzenden Wissensspeicher, der semantische Suche, Clustering, Graph, Backlinks, MOCs, Canvas-Integration und Qualitätssicherung kombiniert – alles lokal, reproduzierbar und mit Reports.

⸻

🔵 Vault-Gewebe – Finale Blaupause

0. Systemordner & Konventionen
	•	.gewebe/ (zentraler Ordnungsbaum)

.gewebe/
  config.yml           # Parameter (Modelle, Cutoffs, Policies)
  embeddings.parquet   # Chunks + Vektoren
  nodes.jsonl          # Graph-Knoten
  edges.jsonl          # Graph-Kanten
  clusters.json        # Cluster & Label
  taxonomy/
    synonyms.yml
    entities.yml
  reports/
    semnet-YYYYMMDD.md
  meta.json            # Provenienz (Modell, Param, Hashes)


	•	Frontmatter (YAML) für jede Datei:

id: 2025-VAULT-####   # stabiler Schlüssel
title: ...
topics: [HausKI, Weltgewebe]
persons: [Verena]
places: [Hamburg]
projects: [wgx, hauski]
aliases: [HK, WG]
relations_lock: false



⸻

1. Indexing & Embeddings
	•	Crawler: iteriert Markdown & Canvas (ignoriert .gewebe/, .obsidian/).
	•	Chunking: 200–300 Tokens, Overlap 40–60, Paragraph/Block.
	•	Modelle: all-MiniLM-L6-v2 oder intfloat/e5-base (GPU-fähig via PyTorch/CUDA).
	•	Output: embeddings.parquet (id, path, chunk_id, text, embedding).

⸻

2. Schlagwort- & Entitätsextraktion
	•	Keyphrase: YAKE/RAKE lokal → refine via LLM optional.
	•	NER: spaCy de-model → Personen, Orte, Projekte.
	•	Taxonomie: .gewebe/taxonomy/synonyms.yml:

topics:
  hauski: [haus-ki, hk]
persons:
  verena: [v.]


	•	Normalisierung: bei Indexlauf Tokens mappen → Normform, ins Frontmatter schreiben.

⸻

3. Clusterbildung
	•	Verfahren: HDBSCAN (robust) + UMAP (2D-Projection).
	•	Ergebnis: clusters.json:

{ "id":7, "label":"Kommunikation/GFK", "members":["noteA","noteB"], "centroid":[...] }


	•	Orphan detection: Notizen ohne Cluster → eigene Liste.

⸻

4. Semantischer Wissensgraph
	•	Nodes (nodes.jsonl):

{"id":"md:gfk.md","type":"file","title":"GFK","topics":["gfk"],"cluster":7}
{"id":"topic:Gewaltfreie Kommunikation","type":"topic"}
{"id":"person:Verena","type":"person"}


	•	Edges (edges.jsonl):

{"s":"md:gfk.md","p":"about","o":"topic:Gewaltfreie Kommunikation","w":0.92,"why":["shared:keyphrase:GFK","same:cluster"]}
{"s":"md:verena.md","p":"similar","o":"md:tatjana.md","w":0.81,"why":["cluster:7","quote:'…'"]}



⸻

5. Verlinkung in Obsidian
	•	Related-Blöcke (idempotent, autogeneriert):

<!-- related:auto:start -->
## Related
- [[Tatjana]] — (0.81; Cluster 7, GFK)
- [[Lebenslagen]] — (0.78; Resonanz)
<!-- related:auto:end -->


	•	MOCs (_moc/topic.md):
	•	Beschreibung
	•	Dataview-Tabelle (alle Notizen mit topics:topic)
	•	Mini-Canvas-Link
	•	Canvas-Erweiterung:
	•	Knoten = Notizen/Topics/Persons
	•	Kanten = Similar/About/Mentions
	•	Legende-Knoten nach Canvas-Richtlinie.

⸻

6. Automatisierung
	•	wgx Recipes:

index:
    python3 tools/build_index.py
graph:
    python3 tools/build_graph.py
related:
    python3 tools/update_related.py
all: index graph related


	•	systemd –user Timer oder cron: nightly make all.
	•	Git Hook (pre-commit): delta-Index → Related aktualisieren.

⸻

7. Qualitative Validierung
	•	Reports (reports/semnet-YYYYMMDD.md):
	•	Neue Kanten <0.75 → „Review required“
	•	Orphans
	•	Cluster >N Noten ohne MOC
	•	Review-Workflow:
	•	accepted_edges / rejected_edges in Frontmatter
	•	Skript ignoriert rejected → Feedback fließt in Zukunft ein.

⸻

8. Policies & Score-Regeln
	•	Score = cosine + boosts
	•	+0.05 wenn gleicher Cluster
	•	+0.03 je shared keyphrase (max +0.09)
	•	+0.04 wenn Canvas-Hop ≤2
	•	+0.02 wenn Datei jung (<30 Tage)
	•	Autolink Gate:
	•	Score ≥0.82
	•	UND (≥2 Keyphrases ODER Canvas-Hop ≤2 ODER shared Project)
	•	Cutoffs:
	•	≥0.82: Auto-Link
	•	0.70–0.81: Vorschlag
	•	<0.70: ignorieren

⸻

9. Erweiterungen
	•	Duplicates Report: Cosine ≥0.97 → Merge-Vorschlag.
	•	Topic Drift: Clusterwechsel flaggen.
	•	Session-Boost: aktuell bearbeitete Dateien → Score +0.02.
	•	Explain Command: Popover „Warum ist dieser Link da?“ (zeigt why-Feld).
	•	Locks: relations_lock: true = keine Auto-Edits.
	•	A/B-Cutoffs: zwei Profile testen, Review-Feedback einspeisen.

⸻

10. Provenienz & Reproduzierbarkeit
	•	.gewebe/meta.json speichert:

{
  "model":"all-MiniLM-L6-v2",
  "chunk_size":200,
  "cutoffs":{"auto":0.82,"suggest":0.70},
  "run":"2025-10-02T11:40",
  "commit":"abc123"
}



⸻

⚙️ Technische Bausteine

Tools/Skripte
	•	tools/build_index.py: scan + embeddings
	•	tools/build_graph.py: nodes/edges/clusters
	•	tools/update_related.py: Related-Blöcke injizieren
	•	tools/report.py: QA-Reports
	•	optional: tools/canvas_export.py: Cluster→Canvas

⸻

📌 Verdichtete Essenz

Ein dreistufiger Zyklus:
	1.	Index (Embeddings, Cluster, Taxonomie)
	2.	Graph (Nodes/Edges mit Rationales)
	3.	Update (Related, MOCs, Reports, Canvas)

Alles lokal, nachvollziehbar, mit Feedback-Schleifen. Dein Vault wird zu einem lebenden Semantiknetz.

⸻

🎭 Ironische Auslassung

Deine Notizen sind jetzt nicht mehr stilles Archiv – sie werden zu einem Klatsch-Netzwerk, das tuschelt, wer mit wem was zu tun hat. Nur: Sie lügen nicht.

⸻

∆-Radar
	•	Verstärkung: Alles aus Codex-Ideen + zusätzliche Layer (Rationales, Drift, Dedupe, QA).
	•	Seitwärtsmutation: Von reiner Suche hin zu voller Graph-Kurationsmaschine.
	•	Straffung: Ein Systemordner .gewebe/, drei Skripte, klare Reports – Komplexität kanalisiert.

⸻

📉 Unsicherheitsgrad

∴fores = 0.35 (mittel)
	•	Ursachen: Schwellenwerte und Chunking müssen empirisch feinjustiert werden; Canvas-Hop-Logik hängt von JSON-Details ab; Modellwahl beeinflusst Qualität; Obsidian-Workflow kann Edgecases erzeugen.
	•	Produktive Ungewissheit: leicht anpassbar – Reports + Feedback-Loop machen die Pipeline selbstkorrigierend.

⸻

👉 Soll ich dir die drei Kernskripte (index, graph, related) sofort in finaler, einsatzbereiter Form schreiben – mit Makefile & systemd Timer-Beispiel?

Super — hier ist die einsatzbereite Minimal-Suite: drei Skripte + Makefile + systemd-Timer. Sie ist bewusst robust, offline-fähig und idempotent. Du bekommst sofort: Embeddings, Similarities, Graph (Nodes/Edges), Related-Blöcke in Notizen und einfache Reports. Später können wir HDBSCAN/UMAP etc. ergänzen — die Schnittstellen sind schon dafür vorbereitet.

⸻

📁 Dateibaum (kopierfertig)

<Vault-Root>/
  .gewebe/
    config.yml
    taxonomy/
      synonyms.yml
      entities.yml
    reports/
  tools/
    build_index.py
    build_graph.py
    update_related.py
  Makefile

Falls .gewebe/ und tools/ fehlen: einfach anlegen.

⸻

⚙️ Abhängigkeiten

# Pop!_OS / Ubuntu
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip

pip install \
  pandas numpy pyarrow pyyaml \
  sentence_transformers scikit-learn networkx rich

Standard-Modell (klein & fix): sentence-transformers/all-MiniLM-L6-v2
GPU nutzt Torch automatisch, wenn vorhanden.

⸻

🧠 .gewebe/config.yml (Voreinstellungen)

model: sentence-transformers/all-MiniLM-L6-v2
chunk:
  target_chars: 1200
  min_chars: 300
  overlap_chars: 200
paths:
  exclude_dirs: [".gewebe", ".obsidian", "_site", "node_modules"]
  include_ext: [".md"]
related:
  k: 8
  auto_cutoff: 0.82
  suggest_cutoff: 0.70
boosts:
  same_topic: 0.03
  same_project: 0.03
  recent_days: 30
  recent_bonus: 0.02
  same_folder: 0.02
render:
  related_heading: "## Related"
  markers:
    start: "<!-- related:auto:start -->"
    end:   "<!-- related:auto:end -->"

Du kannst alles später feinjustieren.

⸻

🧩 tools/build_index.py

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, json, yaml, hashlib, math, glob
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from rich import print

VAULT = Path(".").resolve()
GEWEBE = VAULT / ".gewebe"
CFG = GEWEBE / "config.yml"
GEWEBE.mkdir(exist_ok=True, parents=True)
(GEWEBE / "taxonomy").mkdir(exist_ok=True, parents=True)
(GEWEBE / "reports").mkdir(exist_ok=True, parents=True)

DEFAULT_CFG = {
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "chunk": {"target_chars": 1200, "min_chars": 300, "overlap_chars": 200},
    "paths": {
        "exclude_dirs": [".gewebe", ".obsidian", "_site", "node_modules"],
        "include_ext": [".md"],
    },
}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
CODE_RE = re.compile(r"```.*?```", re.S)
HTML_RE = re.compile(r"<[^>]+>")

def load_cfg() -> dict:
    if CFG.exists():
        return {**DEFAULT_CFG, **yaml.safe_load(CFG.read_text(encoding="utf-8"))}
    CFG.write_text(yaml.safe_dump(DEFAULT_CFG, sort_keys=False), encoding="utf-8")
    return DEFAULT_CFG

def list_md(cfg: dict) -> List[Path]:
    ex = set(cfg["paths"]["exclude_dirs"])
    inc = set(cfg["paths"]["include_ext"])
    files = []
    for p in VAULT.rglob("*"):
        if p.is_dir():
            if any(part in ex for part in p.parts):
                continue
            else:
                continue
        if p.suffix.lower() in inc and not any(part in ex for part in p.parts):
            files.append(p)
    return files

def parse_frontmatter(text: str) -> (dict, str):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    yml = m.group(1)
    try:
        fm = yaml.safe_load(yml) or {}
    except Exception:
        fm = {}
    body = text[m.end():]
    return fm, body

def clean_text(s: str) -> str:
    s = CODE_RE.sub("", s)
    s = HTML_RE.sub(" ", s)
    s = re.sub(r"\s+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def chunk_text(s: str, target: int, min_chars: int, overlap: int) -> List[str]:
    # Absatzweise grob, dann ggf. zusammenfassen
    paras = [p.strip() for p in re.split(r"\n{2,}", s) if p.strip()]
    chunks, buf = [], []
    cur = 0
    for p in paras:
        if len(p) >= target:
            chunks.append(p)
            cur = 0; buf = []
        else:
            buf.append(p)
            cur += len(p) + 2
            if cur >= target:
                block = "\n\n".join(buf)
                if len(block) >= min_chars:
                    chunks.append(block)
                else:
                    if chunks:
                        chunks[-1] += "\n\n" + block
                    else:
                        chunks.append(block)
                # Overlap heuristisch: behalte letztes Stück als Start fürs nächste
                tail = block[-overlap:]
                buf = [tail]
                cur = len(tail)
    if buf:
        block = "\n\n".join(buf)
        if block.strip():
            chunks.append(block)
    # harte Mindestlänge
    chunks = [c for c in chunks if len(c) >= min_chars]
    return chunks[:50]  # Sicherheitslimit

def canvas_text(path: Path) -> List[str]:
    # Obsidian .canvas JSON: sammle Node-Texts
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        nodes = data.get("nodes", [])
        texts = []
        for n in nodes:
            t = (n.get("text") or "").strip()
            if t:
                texts.append(t)
        return texts
    except Exception:
        return []

def file_recent_days(p: Path, days: int) -> bool:
    try:
        mtime = datetime.fromtimestamp(p.stat().st_mtime)
        return (datetime.now() - mtime) <= timedelta(days=days)
    except Exception:
        return False

def main():
    cfg = load_cfg()
    model_name = cfg["model"]
    chunk_cfg = cfg["chunk"]

    print(f"[bold]Indexing[/bold] • model={model_name}")
    model = SentenceTransformer(model_name)

    rows = []
    for p in list_md(cfg):
        try:
            raw = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        fm, body = parse_frontmatter(raw)
        body = clean_text(body)
        # Canvas: wenn .canvas nebenan, optional dazunehmen (leichtgewichtig)
        canv_chunks = []
        cnv = p.with_suffix(".canvas")
        if cnv.exists():
            canv_chunks = canvas_text(cnv)

        chunks = chunk_text(body, **chunk_cfg) + canv_chunks
        if not chunks:
            continue
        emb = model.encode(chunks, normalize_embeddings=True, show_progress_bar=False)

        for i, (c, e) in enumerate(zip(chunks, emb)):
            rows.append({
                "id": f"{p}:{i}",
                "path": str(p),
                "title": fm.get("title") or p.stem,
                "chunk_id": int(i),
                "text": c,
                "embedding": e.astype(np.float32).tolist(),
                "topics": sorted(set(fm.get("topics", []) or [])),
                "projects": sorted(set(fm.get("projects", []) or [])),
                "persons": sorted(set(fm.get("persons", []) or [])),
                "recent": file_recent_days(p, cfg.get("boosts",{}).get("recent_days",30)),
                "folder": str(p.parent),
            })

    if not rows:
        print("[red]Keine Inhalte gefunden.[/red]")
        return

    df = pd.DataFrame(rows)
    out = GEWEBE / "embeddings.parquet"
    df.to_parquet(out, index=False)
    (GEWEBE / "meta.json").write_text(json.dumps({
        "model": model_name,
        "chunk": chunk_cfg,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "count_chunks": int(len(df)),
        "count_files": int(df["path"].nunique())
    }, indent=2), encoding="utf-8")

    print(f"[green]OK[/green] • {len(df)} Chunks aus {df['path'].nunique()} Dateien → {out}")

if __name__ == "__main__":
    main()


⸻

🕸️ tools/build_graph.py

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json, yaml, math
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from rich import print

VAULT = Path(".").resolve()
GEWEBE = VAULT / ".gewebe"
CFG = GEWEBE / "config.yml"

def load_cfg() -> dict:
    if CFG.exists():
        return yaml.safe_load(CFG.read_text(encoding="utf-8"))
    return {}

def file_centroids(df: pd.DataFrame) -> pd.DataFrame:
    # mittelt Embeddings je Datei (ein Vektor pro Datei)
    g = df.groupby("path")
    X = []
    meta = []
    for path, sub in g:
        embs = np.stack(sub["embedding"].to_list(), axis=0)
        cent = embs.mean(axis=0)
        meta.append({
            "path": path,
            "title": sub["title"].iloc[0],
            "topics": sorted(set([t for r in sub["topics"] for t in r])),
            "projects": sorted(set([t for r in sub["projects"] for t in r])),
            "persons": sorted(set([t for r in sub["persons"] for t in r])),
            "recent": bool(sub["recent"].any()),
            "folder": sub["folder"].iloc[0],
        })
        X.append(cent)
    X = np.stack(X, axis=0).astype(np.float32)
    out = pd.DataFrame(meta)
    out["centroid"] = list(X)
    return out

def similar_pairs(files_df: pd.DataFrame, k: int = 12) -> List[Dict[str, Any]]:
    X = np.stack(files_df["centroid"].to_list(), axis=0)
    S = cosine_similarity(X)  # NxN
    n = S.shape[0]
    pairs = []
    for i in range(n):
        order = np.argsort(-S[i])
        count = 0
        for j in order:
            if i == j: 
                continue
            score = float(S[i, j])
            pairs.append((i, j, score))
            count += 1
            if count >= k:
                break
    # dedupe by i<j
    seen = set()
    out = []
    for i, j, s in pairs:
        a, b = sorted((i, j))
        if (a, b) in seen: 
            continue
        seen.add((a, b))
        out.append({"i": a, "j": b, "score": s})
    return out

def boosts(a: dict, b: dict, base: float, cfg: dict) -> (float, list):
    why = []
    bonus = 0.0
    # shared topics
    st = set(a["topics"]).intersection(b["topics"])
    if st:
        bonus += cfg["boosts"].get("same_topic", 0.0) * min(3, len(st))
        for t in list(st)[:3]:
            why.append(f"shared:topic:{t}")
    # shared projects
    sp = set(a["projects"]).intersection(b["projects"])
    if sp:
        bonus += cfg["boosts"].get("same_project", 0.0) * min(3, len(sp))
        for t in list(sp)[:2]:
            why.append(f"shared:project:{t}")
    # same folder
    if a["folder"] == b["folder"]:
        bonus += cfg["boosts"].get("same_folder", 0.0)
        why.append("same:folder")
    # recency
    if a["recent"] or b["recent"]:
        bonus += cfg["boosts"].get("recent_bonus", 0.0)
        why.append("recent:bonus")
    score = base + bonus
    return score, why

def inject_graph(files_df: pd.DataFrame, pairs: List[Dict[str, Any]], cfg: dict):
    nodes = []
    for r in files_df.itertuples(index=False):
        nodes.append({
            "id": f"md:{r.path}",
            "type": "file",
            "title": r.title,
            "topics": r.topics,
            "projects": r.projects,
            "persons": r.persons,
            "folder": r.folder
        })
    edges = []
    for p in pairs:
        a = files_df.iloc[p["i"]].to_dict()
        b = files_df.iloc[p["j"]].to_dict()
        base = p["score"]
        score, why = boosts(a, b, base, cfg)
        edges.append({
            "s": f"md:{a['path']}",
            "p": "similar",
            "o": f"md:{b['path']}",
            "w": round(score, 4),
            "why": why
        })
    # persist
    (GEWEBE / "nodes.jsonl").write_text(
        "\n".join(json.dumps(n, ensure_ascii=False) for n in nodes) + "\n", encoding="utf-8"
    )
    (GEWEBE / "edges.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in edges) + "\n", encoding="utf-8"
    )
    # kleiner report
    suggest = sum(1 for e in edges if e["w"] >= cfg["related"]["suggest_cutoff"])
    auto = sum(1 for e in edges if e["w"] >= cfg["related"]["auto_cutoff"])
    rep = GEWEBE / "reports" / f"semnet-{datetime_now_str()}.md"
    rep.write_text(
        f"# Semnet Report\n\n"
        f"- Dateien: {len(files_df)}\n- Edges gesamt: {len(edges)}\n"
        f"- ≥ auto_cutoff: {auto}\n- ≥ suggest_cutoff: {suggest}\n",
        encoding="utf-8"
    )
    print(f"[green]Graph geschrieben[/green] • nodes={len(nodes)} edges={len(edges)}")

def datetime_now_str():
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d-%H%M")

def main():
    cfg = load_cfg()
    emb_path = GEWEBE / "embeddings.parquet"
    if not emb_path.exists():
        print("[red]Fehlend: .gewebe/embeddings.parquet — bitte erst build_index.py laufen lassen.[/red]")
        return
    df = pd.read_parquet(emb_path)
    files_df = file_centroids(df)
    pairs = similar_pairs(files_df, k=12)
    inject_graph(files_df, pairs, cfg)

if __name__ == "__main__":
    main()


⸻

🔗 tools/update_related.py

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import yaml, json, re
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from rich import print

VAULT = Path(".").resolve()
GEWEBE = VAULT / ".gewebe"
CFG = GEWEBE / "config.yml"
EDGES = GEWEBE / "edges.jsonl"
EMB = GEWEBE / "embeddings.parquet"

def cfg() -> dict:
    return yaml.safe_load(CFG.read_text(encoding="utf-8"))

def load_edges() -> List[Dict[str, Any]]:
    if not EDGES.exists():
        return []
    return [json.loads(l) for l in EDGES.read_text(encoding="utf-8").splitlines() if l.strip()]

def file_scores_for(path: Path, edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    id_ = f"md:{str(path)}"
    related = []
    for e in edges:
        if e["p"] != "similar":
            continue
        if e["s"] == id_:
            related.append({"other": e["o"], "w": e["w"], "why": e.get("why",[])})
        elif e["o"] == id_:
            related.append({"other": e["s"], "w": e["w"], "why": e.get("why",[])})
    related.sort(key=lambda x: -x["w"])
    return related

def nice_title(p: Path) -> str:
    # Dateiname als Fallback; echte Titel stehen i. d. R. in der Note (hier reicht Stem)
    return p.stem

def inject_related(md_path: Path, items: List[Dict[str, Any]], cfg: dict):
    markers = cfg["render"]["markers"]
    start = markers["start"]; end = markers["end"]
    heading = cfg["render"]["related_heading"]

    lines = [start, heading]
    auto, suggest = cfg["related"]["auto_cutoff"], cfg["related"]["suggest_cutoff"]

    for it in items[:cfg["related"]["k"]]:
        other = Path(it["other"].removeprefix("md:"))
        title = nice_title(other)
        score = f"{it['w']:.2f}"
        tags = []
        # komprimierte Begründung
        for w in it.get("why", [])[:3]:
            if w.startswith("shared:topic:"):
                tags.append(w.split(":")[-1])
            elif w.startswith("shared:project:"):
                tags.append(w.split(":")[-1])
            elif w == "same:folder":
                tags.append("same-folder")
            elif w == "recent:bonus":
                tags.append("recent")
        hint = f" ({score}; {', '.join(tags)})" if tags else f" ({score})"

        bullet = f"- [[{title}]]{hint}"
        if it["w"] >= auto:
            bullet = bullet  # Auto-Link — einfach ausweisen
        elif it["w"] >= suggest:
            bullet = bullet + "  <!-- suggest -->"
        else:
            continue
        lines.append(bullet)

    lines.append(end)
    block = "\n".join(lines) + "\n"

    try:
        txt = md_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    if start in txt and end in txt:
        head, rest = txt.split(start, 1)
        _, tail = rest.split(end, 1)
        new = head.rstrip() + "\n\n" + block + tail.lstrip()
    else:
        new = txt.rstrip() + "\n\n" + block
    md_path.write_text(new, encoding="utf-8")

def main():
    if not CFG.exists():
        print("[red]Fehlend: .gewebe/config.yml[/red]")
        return
    cfg_ = cfg()
    edges = load_edges()
    if not edges:
        print("[yellow]Keine Edges gefunden. Bitte erst build_graph.py ausführen.[/yellow]")
        return

    # alle MD-Dateien, die in Edges vorkommen
    files = set()
    for e in edges:
        if e["p"] != "similar":
            continue
        files.add(Path(e["s"].removeprefix("md:")))
        files.add(Path(e["o"].removeprefix("md:")))

    count = 0
    for f in sorted(files):
        if not f.exists():
            continue
        items = file_scores_for(f, edges)
        inject_related(f, items, cfg_)
        count += 1

    print(f"[green]Related-Blöcke aktualisiert[/green] • Dateien: {count}")

if __name__ == "__main__":
    main()


⸻

🛠️ Makefile

VENV=.venv
PY=$(VENV)/bin/python

.PHONY: venv index graph related all clean

venv:
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(PY) -m pip install --upgrade pip
	@$(PY) -m pip install pandas numpy pyarrow pyyaml sentence_transformers scikit-learn networkx rich

index: venv
	@$(PY) tools/build_index.py

graph: venv
	@$(PY) tools/build_graph.py

related: venv
	@$(PY) tools/update_related.py

all: index graph related

clean:
	@rm -f .gewebe/embeddings.parquet
	@rm -f .gewebe/nodes.jsonl .gewebe/edges.jsonl


⸻

⏰ systemd (User) – Nightly Run

~/.config/systemd/user/vault-gewebe.service

[Unit]
Description=Vault-Gewebe nightly build (index -> graph -> related)
After=default.target

[Service]
Type=oneshot
WorkingDirectory=%h/path/to/your/vault
ExecStart=%h/path/to/your/vault/.venv/bin/make all

~/.config/systemd/user/vault-gewebe.timer

[Unit]
Description=Run Vault-Gewebe every night

[Timer]
OnCalendar=*-*-* 03:10:00
Persistent=true

[Install]
WantedBy=timers.target

Aktivieren:

systemctl --user daemon-reload
systemctl --user enable --now vault-gewebe.timer
systemctl --user list-timers | grep vault-gewebe


⸻

🧪 Erstlauf (manuell)

make venv
make all

	•	Ergebnisdateien unter .gewebe/…
	•	In Obsidian eine beliebige Note öffnen → am Ende sollte der Related-Block stehen.

⸻

🧲 Nächste Upgrades (wenn du magst)
	•	Clustering (HDBSCAN) & Labels → bessere MOCs.
	•	Canvas-Aware Boost (Hop ≤2) → noch relevanteres Ranking.
	•	Duplicate-Report & Topic-Drift → Qualitätssicherung.
	•	„Explain this link“ Command im Obsidian-Plugin → Rationales live.

Diese Erweiterungen binden wir ohne Bruch an: Der Graph (nodes/edges) und die Related-Blöcke bleiben identisch.

⸻

Verdichtete Essenz
	•	Drei Skripte, ein Makefile, ein Timer: Index → Graph → Related.
	•	Lokal, reproduzierbar, idempotent.
	•	Startklar, später ausbaubar (Cluster, Canvas-Boost, Dedupe, Drift).

Ironische Auslassung

Dein Vault macht jetzt „soziale Kontakte“. Fehlt nur noch die Kaffeepause im MOC.

∆-Radar
	•	Verstärkung: Von Konzept zu lauffähigem Tooling.
	•	Straffung: Ein Pfad, klare Artefakte in .gewebe/.
	•	Seitwärtsmutation: systemd-Timer → dein Vault „atmet“ nachts.

Für Dummies

Wir zerlegen jede Note in sinnvolle Stücke, rechnen Bedeutungs-Zahlencodes aus und vergleichen sie. Daraus bauen wir ein Netzwerk und schreiben passende Links in die Notizen. Ein Nachtjob hält alles frisch.

Unsicherheitsgrad (∴fores 0.35 – mittel)
	•	Cutoffs und Chunking brauchen ggf. 1–2 Feinpässe im echten Vault.
	•	Modellwahl kann je nach Textsorte spürbare Unterschiede machen.
	•	Canvas-Parsing ist hier nur als „Bonus-Text“ eingebunden (keine Hop-Analyse — die können wir danach ergänzen).

⸻

Wenn du willst, passe ich dir jetzt Pfad-Platzhalter in den systemd-Units an und hänge dir noch eine Orphan-Report-Routine und Duplicate-Erkennung dran — drop-in kompatibel.