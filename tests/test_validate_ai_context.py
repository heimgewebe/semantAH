import copy
import pytest
import yaml
from scripts.ai_context import validate_ai_context


@pytest.fixture
def get_str_data():
    return {
        "project": {"name": "test-project", "meta": {"version": "1.0"}},
        "other": 123,
    }


@pytest.mark.parametrize(
    "path, expected",
    [
        # Happy path
        ("project.name", "test-project"),
        ("project.meta.version", "1.0"),
        # Missing keys
        ("project.missing", ""),
        ("missing", ""),
        # Not a string
        ("other", ""),
        # Intermediate not a dict
        ("other.something", ""),
    ],
)
def test_get_str(get_str_data, path, expected):
    assert validate_ai_context.get_str(get_str_data, path) == expected


@pytest.fixture
def get_list_data():
    return {
        "ai_guidance": {"do": ["test-do"], "meta": {"tags": ["tag1", "tag2"]}},
        "other": 123,
    }


@pytest.mark.parametrize(
    "path, expected",
    [
        # Happy path
        ("ai_guidance.do", ["test-do"]),
        ("ai_guidance.meta.tags", ["tag1", "tag2"]),
        # Missing keys
        ("ai_guidance.missing", []),
        ("missing", []),
        # Not a list
        ("other", []),
        # Intermediate not a dict
        ("other.something", []),
    ],
)
def test_get_list(get_list_data, path, expected):
    assert validate_ai_context.get_list(get_list_data, path) == expected


@pytest.mark.parametrize(
    "data, expected",
    [
        # True cases
        ("This is a TODO item", True),
        ("This is a FIXME item", True),
        ("This is a TBD item", True),
        ("Lorem ipsum dolor", True),
        ("todo item", True),  # Case-insensitive
        # Nested true cases
        (["safe", "TODO"], True),
        ({"key": "FIXME"}, True),
        ({"key": ["safe", {"inner": "lorem"}]}, True),
        # False cases
        ("This is safe", False),
        (["safe", 123], False),
        ({"key": "safe"}, False),
        (None, False),
        (123, False),
    ],
)
def test_has_placeholders(data, expected):
    assert validate_ai_context.has_placeholders(data) is expected


def test_validate_one(tmp_path):
    # Valid YAML
    valid_data = {
        "project": {"name": "Test", "summary": "Testing logic", "role": "Tester"},
        "ai_guidance": {"do": ["test everything"], "dont": ["miss anything"]},
    }
    p = tmp_path / "valid.ai-context.yml"
    p.write_text(yaml.dump(valid_data), encoding="utf-8")
    assert validate_ai_context.validate_one(p) == []

    # Missing project fields
    invalid_data = {
        "project": {
            "name": " ",
            "summary": "",
            # role missing
        },
        "ai_guidance": {"do": [], "dont": []},
    }
    p = tmp_path / "invalid.ai-context.yml"
    p.write_text(yaml.dump(invalid_data), encoding="utf-8")
    errs = validate_ai_context.validate_one(p)
    assert "missing project.name" in errs
    assert "missing project.summary" in errs
    assert "missing project.role" in errs
    assert "ai_guidance.do must not be empty" in errs
    assert "ai_guidance.dont must not be empty" in errs

    # With placeholders
    placeholder_data = copy.deepcopy(valid_data)
    placeholder_data["project"]["name"] = "TODO project"
    p = tmp_path / "placeholder.ai-context.yml"
    p.write_text(yaml.dump(placeholder_data), encoding="utf-8")
    errs = validate_ai_context.validate_one(p)
    assert "contains placeholders (TODO/TBD/FIXME/lorem/ipsum)" in errs


def test_validate_file(tmp_path):
    # Valid file
    valid_data = {
        "project": {"name": "T", "summary": "S", "role": "R"},
        "ai_guidance": {"do": ["D"], "dont": ["X"]},
    }
    p = tmp_path / "test.ai-context.yml"
    p.write_text(yaml.dump(valid_data), encoding="utf-8")
    assert validate_ai_context.validate_file(p) == 0

    # Invalid file
    invalid_data = {"project": {"name": ""}}
    p2 = tmp_path / "bad.ai-context.yml"
    p2.write_text(yaml.dump(invalid_data), encoding="utf-8")
    assert validate_ai_context.validate_file(p2) == 2

    # Missing file
    with pytest.raises(SystemExit) as excinfo:
        validate_ai_context.validate_file(tmp_path / "missing.yml")
    assert excinfo.value.code == 2


def test_validate_templates(tmp_path):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    valid_data = {
        "project": {"name": "T", "summary": "S", "role": "R"},
        "ai_guidance": {"do": ["D"], "dont": ["X"]},
    }

    # No template files
    with pytest.raises(SystemExit) as excinfo:
        validate_ai_context.validate_templates(templates_dir)
    assert excinfo.value.code == 2

    # All valid
    (templates_dir / "one.ai-context.yml").write_text(
        yaml.dump(valid_data), encoding="utf-8"
    )
    (templates_dir / "two.ai-context.yml").write_text(
        yaml.dump(valid_data), encoding="utf-8"
    )
    assert validate_ai_context.validate_templates(templates_dir) == 0

    # One invalid
    invalid_data = {"project": {"name": ""}}
    (templates_dir / "bad.ai-context.yml").write_text(
        yaml.dump(invalid_data), encoding="utf-8"
    )
    assert validate_ai_context.validate_templates(templates_dir) == 2

    # Missing dir
    with pytest.raises(SystemExit) as excinfo:
        validate_ai_context.validate_templates(tmp_path / "not-there")
    assert excinfo.value.code == 2
