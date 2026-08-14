from backend.scripts.export_versioned_config import sanitize


def test_sanitize_redacts_credentials_without_redacting_keyword_settings() -> None:
    value = {
        "api_key": "secret-value",
        "nested": {"access_token": "token-value", "keyword_param": "query"},
        "prefer_default_keywords": True,
    }

    assert sanitize(value) == {
        "api_key": "${REDACTED}",
        "nested": {"access_token": "${REDACTED}", "keyword_param": "query"},
        "prefer_default_keywords": True,
    }
