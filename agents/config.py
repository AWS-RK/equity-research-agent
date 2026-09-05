import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import find_dotenv, load_dotenv


@dataclass
class Config:
    sec_user_agent: str
    api_ninjas_key: str
    alpha_vantage_key: str
    anthropic_api_key: str


def load_config() -> Config:
    # find_dotenv(usecwd=True): search for .env starting from the current working
    # directory, not from this module's file location (the default when no path is
    # given), so tests that chdir into a tmp_path see only their own fixture .env.
    load_dotenv(find_dotenv(usecwd=True))
    sec_user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    api_ninjas_key = os.environ.get("API_NINJAS_KEY", "").strip()
    alpha_vantage_key = os.environ.get("ALPHA_VANTAGE_KEY", "").strip()
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    missing = [
        name
        for name, value in [
            ("SEC_USER_AGENT", sec_user_agent),
            ("API_NINJAS_KEY", api_ninjas_key),
            ("ALPHA_VANTAGE_KEY", alpha_vantage_key),
            ("ANTHROPIC_API_KEY", anthropic_api_key),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Copy .env.example to .env and fill them in."
        )

    return Config(
        sec_user_agent=sec_user_agent,
        api_ninjas_key=api_ninjas_key,
        alpha_vantage_key=alpha_vantage_key,
        anthropic_api_key=anthropic_api_key,
    )


def get_data_dir(ticker: str, base_dir: str = "data") -> Path:
    data_dir = Path(base_dir) / ticker.upper()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
