# semantAH: Mitschreiber-Index

Semantische Suche über Kontext-Embeddings aus mitschreiber.

## Index
- Name: `idx_os_embed`
- Space: cosine
- Payload: `app`, `window`, `keyphrases[]`, `hash_id`

## Ingest
- Quelle: chronik (ETL/Stream)
- Dedup: über `hash_id`

## Realtime
- Optional: lokaler Websocket/IPC vom mitschreiber (nur im RAM) für “contextual candidates”.

## Query-Operatoren (Beispiele)
- `near:("oauth flow") app:code window:projX`
- `since:7d mode:deepwork`

## Datenschutz
- **Kein Rohtext** im Index.
- `privacy.raw_retained=false` im Payload.
