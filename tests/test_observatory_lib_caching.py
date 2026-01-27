
import json
import os
import time
import pytest
from pathlib import Path
from scripts import observatory_lib

# Skip tests if jsonschema is not installed
try:
    import jsonschema
except ImportError:
    pytest.skip("jsonschema not installed", allow_module_level=True)

def test_caching_behavior(tmp_path):
    """
    Test that the validator cache works correctly:
    - Misses on first access
    - Hits on subsequent access with same file state
    - Misses (reloads) when file content/mtime changes
    """
    # Setup schema
    schema_path = tmp_path / "schema.json"
    schema = {"type": "object", "properties": {"foo": {"type": "string"}}}
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    payload = {"foo": "bar"}

    # Clear cache to start fresh
    observatory_lib._get_cached_validator.cache_clear()

    # 1. First call - should be a cache MISS
    observatory_lib.validate_payload_if_available(payload, schema_path, label="Test1")

    info1 = observatory_lib._get_cached_validator.cache_info()
    assert info1.misses == 1
    assert info1.hits == 0

    # 2. Second call - should be a cache HIT
    observatory_lib.validate_payload_if_available(payload, schema_path, label="Test2")

    info2 = observatory_lib._get_cached_validator.cache_info()
    assert info2.misses == 1
    assert info2.hits == 1

    # 3. Modify schema file to trigger invalidation
    # We write new content. This updates size and/or mtime.
    new_schema = {"type": "object", "properties": {"bar": {"type": "integer"}}}
    # Ensure some time passes or mtime is forced to change
    old_stat = schema_path.stat()
    time.sleep(0.01)

    schema_path.write_text(json.dumps(new_schema), encoding="utf-8")

    # In case the filesystem has coarse mtime resolution (e.g. 1s), force an update if needed.
    # But usually write_text is enough. Let's check.
    new_stat = schema_path.stat()
    if new_stat.st_mtime_ns == old_stat.st_mtime_ns and new_stat.st_size == old_stat.st_size:
        # Force update mtime if it didn't change automatically (unlikely with different content size/time)
        # Use +1s (1_000_000_000 ns) to be safe against coarse resolution
        os.utime(str(schema_path), ns=(new_stat.st_atime_ns, new_stat.st_mtime_ns + 1_000_000_000))

    # 4. Third call - should be a cache MISS (invalidation)
    new_payload = {"bar": 123}
    observatory_lib.validate_payload_if_available(new_payload, schema_path, label="Test3")

    info3 = observatory_lib._get_cached_validator.cache_info()
    assert info3.misses == 2
    assert info3.hits == 1

def test_json_error_handling_no_cache_poisoning(tmp_path, capsys):
    """
    Test that invalid JSON in the schema file:
    - Raises the expected error (handled by print+exit)
    - Does not poison the cache (next valid write works)
    """
    schema_path = tmp_path / "bad_schema.json"
    schema_path.write_text("{ invalid json ", encoding="utf-8")

    payload = {"foo": "bar"}

    # Clear cache
    observatory_lib._get_cached_validator.cache_clear()

    # 1. Invalid JSON should exit(1)
    with pytest.raises(SystemExit) as exc:
        observatory_lib.validate_payload_if_available(payload, schema_path)
    assert exc.value.code == 1

    captured = capsys.readouterr()
    assert "Failed to parse schema JSON" in captured.err

    # Check cache stats - exception means no entry stored
    info = observatory_lib._get_cached_validator.cache_info()
    assert info.misses == 1
    assert info.currsize == 0

    # 2. Fix the file
    valid_schema = {"type": "object", "properties": {"foo": {"type": "string"}}}
    schema_path.write_text(json.dumps(valid_schema), encoding="utf-8")

    # 3. Should now succeed and cache
    observatory_lib.validate_payload_if_available(payload, schema_path)

    info2 = observatory_lib._get_cached_validator.cache_info()
    assert info2.misses == 2 # 1 failed attempt (counted as miss call), 1 success
    assert info2.currsize == 1
