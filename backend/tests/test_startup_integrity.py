"""Startup integrity checks for syntax/import errors that break the API server."""
from pathlib import Path
import compileall
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_backend_app_compiles() -> None:
    """All backend app modules should compile before uvicorn tries to import them."""
    app_dir = Path(__file__).resolve().parents[1] / "app"
    assert compileall.compile_dir(str(app_dir), quiet=1)


def test_create_app_builds_without_import_errors() -> None:
    """FastAPI app factory should be importable and construct the app."""
    from app.main import create_app

    app = create_app()

    assert app.title == "TradeRadar"
