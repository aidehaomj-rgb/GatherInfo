"""Auto-generated route module."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db

logger = logging.getLogger(__name__)
import time

import httpx

from app.collection_schemas import (
    AutoDiscoverResult, DiscoveredProvider,
    ListModelsResult, ModelConfigCreate, ModelConfigOut, ModelConfigUpdate,
    ModelTestResult,
)
from app.models import ModelConfig

router = APIRouter(prefix="/api/v1", tags=["models"])


def _openai_compatible_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    path = path if path.startswith("/") else f"/{path}"
    if base.endswith("/v1"):
        return f"{base}{path}"
    return f"{base}/v1{path}"



@router.get("/models", response_model=list[ModelConfigOut])
def list_models(db: Session = Depends(get_db)):
    return db.query(ModelConfig).order_by(
        ModelConfig.is_default.desc(), ModelConfig.created_at.desc()
    ).all()


@router.post("/models", response_model=ModelConfigOut, status_code=201)
def create_model(data: ModelConfigCreate, db: Session = Depends(get_db)):
    if db.query(ModelConfig).filter(ModelConfig.id == data.id).first():
        raise HTTPException(400, f"Model '{data.id}' exists")
    if data.is_default:
        db.query(ModelConfig).filter(ModelConfig.is_default == True).update(
            {"is_default": False}
        )
    m = ModelConfig(**data.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@router.get("/models/{model_id}", response_model=ModelConfigOut)
def get_model(model_id: str, db: Session = Depends(get_db)):
    m = db.query(ModelConfig).filter(ModelConfig.id == model_id).first()
    if not m:
        raise HTTPException(404)
    return m


@router.put("/models/{model_id}", response_model=ModelConfigOut)
def update_model(model_id: str, data: ModelConfigUpdate, db: Session = Depends(get_db)):
    m = db.query(ModelConfig).filter(ModelConfig.id == model_id).first()
    if not m:
        raise HTTPException(404)
    payload = data.model_dump(exclude_unset=True)
    if payload.get("is_default"):
        db.query(ModelConfig).filter(
            ModelConfig.id != model_id, ModelConfig.is_default == True
        ).update({"is_default": False})
    for k, v in payload.items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return m


@router.delete("/models/{model_id}")
def delete_model(model_id: str, db: Session = Depends(get_db)):
    m = db.query(ModelConfig).filter(ModelConfig.id == model_id).first()
    if not m:
        raise HTTPException(404)
    db.delete(m)
    db.commit()
    return {"ok": True}


@router.post("/models/{model_id}/test", response_model=ModelTestResult)
async def test_model(model_id: str, db: Session = Depends(get_db)):
    m = db.query(ModelConfig).filter(ModelConfig.id == model_id).first()
    if not m:
        raise HTTPException(404)
    start = time.monotonic()
    try:
        base = (m.base_url or "http://localhost:11434").rstrip("/")
        model_name = m.model_name or ""

        if m.provider == "ollama":
            headers = {"Content-Type": "application/json"}
            if m.api_key:
                headers["Authorization"] = f"Bearer {m.api_key}"
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    r = await client.get(f"{base}/api/tags", headers=headers)
                    if r.status_code != 200:
                        return ModelTestResult(
                            success=False,
                            message=f"Ollama unreachable: {r.status_code}",
                            duration_ms=int((time.monotonic() - start) * 1000),
                        )
                    tags_data = r.json()
                    avail = [mod.get("name", "") for mod in tags_data.get("models", [])]
            except Exception as exc:
                return ModelTestResult(
                    success=False,
                    message=f"Ollama connection failed: {exc}",
                    duration_ms=int((time.monotonic() - start) * 1000),
                )

            test_model = model_name
            if test_model not in avail and test_model.split(":")[0] not in " ".join(avail):
                test_model = avail[0] if avail else model_name
                message = f"Model '{model_name}' not found. Using '{test_model}' instead."
            else:
                message = f"Ollama OK. Found {len(avail)} models."

            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    r = await client.post(f"{base}/api/chat", json={
                        "model": test_model,
                        "messages": [{"role": "user", "content": "Reply exactly: OK"}],
                        "stream": False,
                    }, headers=headers)
                    if r.status_code == 200:
                        data = r.json()
                        reply = data.get("message", {}).get("content", "")[:100]
                        dur = int((time.monotonic() - start) * 1000)
                        return ModelTestResult(success=True, message=message, response_preview=reply, duration_ms=dur)
                    else:
                        return ModelTestResult(
                            success=False,
                            message=f"Ollama model error: {r.text[:100]}",
                            duration_ms=int((time.monotonic() - start) * 1000),
                        )
            except Exception as exc:
                return ModelTestResult(
                    success=False,
                    message=f"Ollama inference failed: {exc}",
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
        else:
            # OpenAI-compatible test
            async with httpx.AsyncClient(timeout=120) as client:
                headers = {"Content-Type": "application/json"}
                if m.api_key:
                    headers["Authorization"] = f"Bearer {m.api_key}"
                url = _openai_compatible_url(base, "/chat/completions")
                r = await client.post(url, json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": "Reply exactly: OK"}],
                    "max_tokens": 10,
                    "temperature": 0,
                }, headers=headers)
                dur = int((time.monotonic() - start) * 1000)
                if r.status_code == 200:
                    data = r.json()
                    reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")[:100]
                    return ModelTestResult(
                        success=True,
                        message=f"Connected to {model_name}",
                        response_preview=reply,
                        duration_ms=dur,
                    )
                else:
                    return ModelTestResult(
                        success=False,
                        message=f"API error {r.status_code}: {r.text[:200]}",
                        duration_ms=dur,
                    )
    except Exception as exc:
        return ModelTestResult(
            success=False,
            message=f"Test failed: {exc}",
            duration_ms=int((time.monotonic() - start) * 1000),
        )


@router.post("/models/{model_id}/list-models", response_model=ListModelsResult)
async def list_available_models(model_id: str, db: Session = Depends(get_db)):
    m = db.query(ModelConfig).filter(ModelConfig.id == model_id).first()
    if not m:
        raise HTTPException(404)
    try:
        base = (m.base_url or "http://localhost:11434").rstrip("/")
        if m.provider == "ollama":
            async with httpx.AsyncClient(timeout=5) as client:
                headers = {}
                if m.api_key:
                    headers["Authorization"] = f"Bearer {m.api_key}"
                r = await client.get(f"{base}/api/tags", headers=headers)
                models = [mod.get("name", "") for mod in r.json().get("models", [])]
                return ListModelsResult(
                    success=True, message=f"Found {len(models)} models",
                    models=models, provider_type="ollama", current_model=m.model_name or "",
                )
        else:
            async with httpx.AsyncClient(timeout=5) as client:
                headers = {}
                if m.api_key:
                    headers["Authorization"] = f"Bearer {m.api_key}"
                r = await client.get(_openai_compatible_url(base, "/models"), headers=headers)
                raw = r.json()
                models = [mod.get("id", "") for mod in raw.get("data", [])]
                return ListModelsResult(
                    success=True, message=f"Found {len(models)} models",
                    models=models, provider_type=m.provider, current_model=m.model_name or "",
                )
    except Exception as exc:
        return ListModelsResult(
            success=False, message=str(exc), models=[],
            provider_type=m.provider, current_model=m.model_name or "",
        )


@router.post("/models/auto-discover", response_model=AutoDiscoverResult)
async def auto_discover_models(db: Session = Depends(get_db)):
    providers: list[DiscoveredProvider] = []

    # Check Ollama
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get("http://localhost:11434/api/tags")
            if r.status_code == 200:
                models = [mod.get("name", "") for mod in r.json().get("models", [])]
                providers.append(DiscoveredProvider(
                    provider="ollama", base_url="http://localhost:11434",
                    models=models, reachable=True, note=f"Found {len(models)} models",
                ))
    except Exception:
        providers.append(DiscoveredProvider(
            provider="ollama", base_url="http://localhost:11434",
            models=[], reachable=False, note="Ollama not running",
        ))

    # Check CC Switch
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get("http://127.0.0.1:15721/v1/models")
            if r.status_code == 200:
                models = [mod.get("id", "") for mod in r.json().get("data", [])]
                providers.append(DiscoveredProvider(
                    provider="cc_switch", base_url="http://127.0.0.1:15721",
                    models=models, reachable=True, note=f"Found {len(models)} models",
                ))
    except Exception:
        pass

    return AutoDiscoverResult(providers=providers)


