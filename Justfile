export-insights:
	VAULT_ROOT=${VAULT_ROOT:-~/Vaults/main}
	@echo "Exporting insights to ${VAULT_ROOT}/.gewebe/insights/today.json"
	VAULT_ROOT=${VAULT_ROOT} uv run scripts/export_insights.py
