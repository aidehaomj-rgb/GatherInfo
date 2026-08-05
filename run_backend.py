"""Start backend server on port 8109 and keep running."""
import uvicorn, sys, os
from pathlib import Path
from project_env import load_backend_env
load_backend_env(Path(__file__).resolve().parent)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.chdir(os.path.dirname(__file__))
from app.main import create_app
app = create_app()
print(f"Starting GatherInfo backend on port 8109...", flush=True)
uvicorn.run(app, host='127.0.0.1', port=8109, log_level='info')
