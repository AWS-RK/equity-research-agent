import pytest

from agents.config import load_config, get_data_dir


def test_load_config_reads_all_four_vars(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        'SEC_USER_AGENT="Test User test@example.com"\n'
        "API_NINJAS_KEY=abc123\n"
        "ALPHA_VANTAGE_KEY=xyz789\n"
        "ANTHROPIC_API_KEY=sk-ant-test123\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.delenv("API_NINJAS_KEY", raising=False)
    monkeypatch.delenv("ALPHA_VANTAGE_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    config = load_config()

    assert config.sec_user_agent == "Test User test@example.com"
    assert config.api_ninjas_key == "abc123"
    assert config.alpha_vantage_key == "xyz789"
    assert config.anthropic_api_key == "sk-ant-test123"


def test_load_config_raises_on_missing_var(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.delenv("API_NINJAS_KEY", raising=False)
    monkeypatch.delenv("ALPHA_VANTAGE_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SEC_USER_AGENT"):
        load_config()


def test_get_data_dir_creates_directory(tmp_path):
    data_dir = get_data_dir("snow", base_dir=str(tmp_path))

    assert data_dir == tmp_path / "SNOW"
    assert data_dir.is_dir()
