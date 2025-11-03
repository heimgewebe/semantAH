### 📄 examples/semantah.example.yml

**Größe:** 468 B | **md5:** `3b83836d29ebe7d2b69c90988f4280e8`

```yaml
vault_path: /path/to/your/obsidian-vault
out_dir: .gewebe
embedder:
  provider: ollama          # oder: openai
  model: nomic-embed-text   # Beispielmodell (lokal)
index:
  top_k: 20
graph:
  cutoffs:
    # Beide Optionen anbieten – je nach aktuellem Parser:
    # (A) Ko-Vorkommen/gewichtete Kante:
    min_cooccur: 2
    min_weight: 0.15
    # (B) Falls der aktuelle Code noch auf Similarity-Schwelle hört:
    # min_similarity: 0.35
related:
  write_back: false
```

