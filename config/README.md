# Versioned configuration

`snapshots/` contains the local business configuration committed for review and deployment:

- `collection_categories.json`: collection category definitions
- `information_sources.json`: information source metadata and collection settings
- `prompt_templates.json`: reusable prompts
- `topics.json`: topic management settings and source bindings
- `mcp_tools.json`: MCP/search tool configuration
- `supply_chain.json`: supply-chain investigations, entities, procurement cases, shipments, linked evidence, open-source evidence, and generated analysis
- `content_archive.json`: collected items, analysis reports, tags and item relations, plus multi-round research jobs, cases, entities, and evidence

The snapshot deliberately excludes runtime counters, execution history and timestamps. Credential values are never exported; secret fields use `${REDACTED}` and `api_key_ref` records the environment-variable name where one is configured.

Regenerate the snapshot from the local database with:

```powershell
$env:PYTHONPATH='backend'
backend\.venv\Scripts\python.exe backend\scripts\export_versioned_config.py
```
