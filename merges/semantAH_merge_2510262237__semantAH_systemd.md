### 📄 semantAH/systemd/vault-gewebe.service

**Größe:** 209 B | **md5:** `c8d19aaf3b4ea255f1671886b89596f5`

```plaintext
[Unit]
Description=semantAH nightly index build (index -> graph -> related)
After=default.target

[Service]
Type=oneshot
WorkingDirectory=%h/path/to/your/vault
ExecStart=%h/path/to/semantAH/.venv/bin/make all
```

### 📄 semantAH/systemd/vault-gewebe.timer

**Größe:** 134 B | **md5:** `08dba76201e550bc6446a15d74db51a2`

```plaintext
[Unit]
Description=Run semantAH nightly at 03:10

[Timer]
OnCalendar=*-*-* 03:10:00
Persistent=true

[Install]
WantedBy=timers.target
```

