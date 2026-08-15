"""Default model selection shared by collection, translation, and reporting."""
from sqlalchemy.orm import Session

from app.models import ModelConfig

# These IDs belong to built-in examples. They must never outrank a user-configured
# default when a legacy database contains more than one default flag.
BUILTIN_MODEL_IDS = frozenset({
    "ollama-default", "cc-switch-deepseek", "deepseek-api", "qwen-api", "openai-fallback",
})


def _default_priority(model: ModelConfig) -> tuple[int, int, str]:
    return (
        0 if bool(model.api_key) else 1,
        0 if model.id not in BUILTIN_MODEL_IDS else 1,
        model.id,
    )


def get_default_model(db: Session) -> ModelConfig | None:
    """Return the single effective active default model without guessing a fallback."""
    defaults = db.query(ModelConfig).filter(
        ModelConfig.is_default == True,
        ModelConfig.is_active == True,
    ).all()
    return min(defaults, key=_default_priority) if defaults else None


def reconcile_default_model(db: Session) -> bool:
    """Repair legacy duplicate defaults while preserving every model record."""
    defaults = db.query(ModelConfig).filter(ModelConfig.is_default == True).all()
    active_default = get_default_model(db)
    chosen = active_default or (min(defaults, key=_default_priority) if defaults else None)
    if not chosen or len(defaults) <= 1:
        return False
    for model in defaults:
        model.is_default = model.id == chosen.id
    return True
