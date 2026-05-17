from memory_with_receipts.core.config import Settings


def test_settings_defaults_are_safe_for_local_development():
    settings = Settings()

    assert settings.app_name == "Memory With Receipts"
    assert settings.environment == "test"
    assert settings.log_level == "INFO"
    assert "postgresql+asyncpg" in settings.database_url
