import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    sec_user_agent: str
    api_ninjas_key: str
    alpha_vantage_key: str


def load_config(env_path: str = ".env") -> Config:
    # Load .env from the specified path in the current working directory.
    # This allows tests that chdir into a tmp_path to use only their own fixture .env.
    load_dotenv(dotenv_path=env_path)
    sec_user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    api_ninjas_key = os.environ.get("API_NINJAS_KEY", "").strip()
    alpha_vantage_key = os.environ.get("ALPHA_VANTAGE_KEY", "").strip()

    missing = [
        name
        for name, value in [
            ("SEC_USER_AGENT", sec_user_agent),
            ("API_NINJAS_KEY", api_ninjas_key),
            ("ALPHA_VANTAGE_KEY", alpha_vantage_key),
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
    )


def get_data_dir(ticker: str, base_dir: str = "data") -> Path:
    data_dir = Path(base_dir) / ticker.upper()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
