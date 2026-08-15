"""Connector package. Import here to register all collectors."""
from app.connectors.base import BaseCollector, ConnectorRegistry, CollectResult, FetchItem

# Register all built-in connectors
from app.connectors import tavily_search    # noqa: F401
from app.connectors import ai_research      # noqa: F401
from app.connectors import rss_collector    # noqa: F401
from app.connectors import web_scrape       # noqa: F401
from app.connectors import official_api     # noqa: F401
from app.connectors import search_engines   # noqa: F401
from app.connectors import json_api         # noqa: F401

__all__ = ["BaseCollector", "ConnectorRegistry", "CollectResult", "FetchItem"]
