import json
import os
import shlex
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest


def _prebuild_indexd(timeout_s: float = 300.0) -> None:
    """
    Baut das 'indexd'-Binary vor dem Start des Servers.
    Verhindert, dass der Health-Check wegen kalter Builds in CI zu früh ausfällt.
    """
    try:
        # Schneller Check: Wenn das Release/Debug-Binary schon existiert, überspringen wir den Build nicht,
        # sondern verlassen uns trotzdem auf cargo's inkrementellen Build (schnell, no-op).
        cmd = ["cargo", "build", "-q", "-p", "indexd"]
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
        )
    except subprocess.CalledProcessError as e:
        out = e.stdout.decode("utf-8", "replace") if e.stdout else ""
        pytest.fail(f"Prebuild of indexd failed (rc={e.returncode}). Output:\n{out}")
    except subprocess.TimeoutExpired as e:
        pytest.fail(
            "Prebuild of indexd timed out after "
            f"{timeout_s:.0f}s. Command: {shlex.join(e.cmd) if isinstance(e.cmd, (list, tuple)) else e.cmd}"
        )


def _healthz_deadline_from_env(default: float = 120.0) -> float:
    """Erlaubt Override der Health-Check-Deadline via ENV (INDEXD_E2E_HEALTHZ_DEADLINE)."""
    val = os.environ.get("INDEXD_E2E_HEALTHZ_DEADLINE")
    return float(val) if val else default


def _http_json(url: str, payload: dict | None = None, timeout: float = 5.0):
    req = urllib.request.Request(url)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req.add_header("content-type", "application/json")
    else:
        data = None
    with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
        body = resp.read()
        ctype = resp.headers.get("content-type", "")
        if "application/json" in ctype:
            return json.loads(body.decode("utf-8"))
        return body.decode("utf-8")


def _wait_for_healthz(base: str, deadline_s: float = 15.0):
    url = f"{base}/healthz"
    start = time.time()
    last_err: Exception | None = None
    while time.time() - start < deadline_s:
        try:
            text = _http_json(url, None, timeout=1.5)
            if text == "ok":
                return
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(0.25)
    raise RuntimeError(f"healthz did not become ready: {last_err!r}")


@contextmanager
def run_indexd():
    """
    Baut 'indexd' vorab, startet dann 'cargo run -p indexd' im Hintergrund auf Port 8080,
    wartet auf /healthz (mit großzügiger Deadline) und räumt beim Verlassen auf.
    """
    # 0) Vorab-Build (kann auf kalten CI-Runnern mehrere Minuten dauern)
    _prebuild_indexd()
    env = os.environ.copy()
    # persistenz in tmp, damit Tests nichts in echte Arbeitsverzeichnisse schreiben
    tmp_state = Path.cwd() / ".test-indexd-state"
    tmp_state.mkdir(exist_ok=True)
    env["INDEXD_DB_PATH"] = str(tmp_state / "store.jsonl")

    proc = subprocess.Popen(
        ["cargo", "run", "-q", "-p", "indexd"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    try:
        # 1) Auf Health warten – großzügige Default-Deadline, via ENV überschreibbar
        _wait_for_healthz(
            "http://127.0.0.1:8080",
            deadline_s=_healthz_deadline_from_env(default=120.0),
        )
        yield proc
    finally:
        # Sauber beenden
        try:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        finally:
            # Logausgabe im Fehlerfall anhängen
            if proc.stdout:
                out = proc.stdout.read().decode("utf-8", "replace")
                sys.stdout.write("\n[indexd output]\n")
                sys.stdout.write(out)
                sys.stdout.write("\n[/indexd output]\n")


@pytest.mark.integration
def test_push_index_script_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # 1) Start server
    with run_indexd():
        base = "http://127.0.0.1:8080"

        # 2) Schreibe Minimal-Parquet in isoliertem Arbeitsverzeichnis
        work = tmp_path / "work"
        (work / ".gewebe").mkdir(parents=True)
        parquet = work / ".gewebe" / "embeddings.parquet"
        df = pd.DataFrame(
            [
                {
                    "doc_id": "D1",
                    "namespace": "ns",
                    "id": "c1",
                    "text": "hello world",
                    "embedding": [1.0, 0.0],
                }
            ]
        )
        # pandas benötigt i.d.R. pyarrow/fastparquet – in diesem Projekt sollte pyarrow verfügbar sein.
        df.to_parquet(parquet)

        # 3) push_index.py gegen den laufenden Dienst ausführen
        # Hinweis: wir setzen CWD auf 'work', damit der Default-Pfad funktioniert;
        # übergeben aber explizit --embeddings zur Sicherheit.
        script = Path(__file__).parent.parent / "scripts" / "push_index.py"
        cmd = [
            sys.executable,
            str(script),
            "--embeddings",
            str(parquet),
            "--endpoint",
            f"{base}/index/upsert",
        ]
        proc = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=25)
        if proc.returncode != 0:
            pytest.fail(
                f"push_index.py failed: rc={proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )

        # 4) Suche absetzen und Treffer prüfen
        payload = {
            "query": "hello",
            "k": 5,
            "namespace": "ns",
            "embedding": [1.0, 0.0],
        }
        res = _http_json(f"{base}/index/search", payload, timeout=5.0)
        results = res.get("results", [])
        assert len(results) == 1
        assert results[0]["doc_id"] == "D1"
        assert results[0]["chunk_id"] == "c1"
        assert results[0]["score"] > 0.0
