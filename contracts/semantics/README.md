# Semantics contracts

These JSON Schemas describe the contracts exchanged between the semantic pipeline
and downstream consumers. Example payloads in `examples/` double as
human-readable documentation and validation fixtures:

- `*-valid.json` payloads must satisfy their corresponding schema.
- `*-invalid.json` payloads are intentionally malformed and the CI job asserts
  that they fail validation. This guards against accidentally weakening a
  schema.

The GitHub Actions workflow uses [`ajv-cli`](https://github.com/ajv-validator/ajv-cli)
with the `@` syntax (for example, `-d @path/to/sample.json`) to load JSON from
files relative to the repository root.
