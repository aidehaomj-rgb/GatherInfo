"""Regression tests for one deterministic, user-owned default model."""
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import ModelConfig
from app.model_defaults import get_default_model, reconcile_default_model


def test_user_configured_default_wins_over_seeded_duplicate() -> None:
    engine = create_engine("sqlite:///:memory:")
    ModelConfig.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        seeded = ModelConfig(
            id="cc-switch-deepseek", name="Seeded", provider="cc_switch",
            model_name="seed", is_default=True, is_active=True,
        )
        configured = ModelConfig(
            id="ollama-cloud-user", name="User configured", provider="ollama_cloud",
            base_url="https://ollama.com", api_key="test-key", model_name="glm", is_default=True,
            is_active=True,
        )
        session.add_all([seeded, configured])
        session.commit()

        assert get_default_model(session).id == configured.id
        assert reconcile_default_model(session) is True
        session.commit()
        assert configured.is_default is True
        assert seeded.is_default is False
    finally:
        session.close()
