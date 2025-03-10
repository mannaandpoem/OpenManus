import threading
import tomllib
from pathlib import Path
from typing import Dict

from pydantic import BaseModel, Field


def get_project_root() -> Path:
    """Get the project root directory"""
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = get_project_root()
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"


class LLMSettings(BaseModel):
    model: str = Field(..., description="Model name")
    base_url: str = Field(..., description="API base URL")
    api_key: str = Field(..., description="API key")
    max_tokens: int = Field(4096, description="Maximum number of tokens per request")
    temperature: float = Field(1.0, description="Sampling temperature")
    api_type: str = Field(..., description="AzureOpenai or Openai")
    api_version: str = Field(..., description="Azure Openai version if AzureOpenai")


class AppConfig(BaseModel):
    llm: Dict[str, LLMSettings]


class Config:
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._config = None
                    self._load_initial_config()
                    self._initialized = True

    @staticmethod
    def _get_config_path() -> Path:
        """Find and return the path to a valid configuration file."""
        config_locations = [
            PROJECT_ROOT / "config" / "config.toml",
            PROJECT_ROOT / "config" / "config.example.toml"
        ]
        
        for location in config_locations:
            if location.exists():
                return location
        
        locations_str = "\n".join(f"- {loc}" for loc in config_locations)
        raise FileNotFoundError(
            f"No configuration file found. Please create a config.toml file in one of these locations:\n{locations_str}"
        )

    def _load_config(self) -> dict:
        try:
            config_path = self._get_config_path()
            with config_path.open("rb") as f:
                return tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"Error parsing configuration file: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}")

    def _load_initial_config(self):
        try:
            raw_config = self._load_config()
            base_llm = raw_config.get("llm", {})
                
            llm_overrides = {
                k: v for k, v in base_llm.items() if isinstance(v, dict)
            }

            default_settings = {
                "model": base_llm.get("model"),
                "base_url": base_llm.get("base_url"),
                "api_key": base_llm.get("api_key"),
                "max_tokens": base_llm.get("max_tokens", 4096),
                "temperature": base_llm.get("temperature", 1.0),
                "api_type": base_llm.get("api_type", ""),
                "api_version": base_llm.get("api_version", ""),
            }

            config_dict = {
                "llm": {
                    "default": default_settings,
                    **{
                        name: {**default_settings, **override_config}
                        for name, override_config in llm_overrides.items()
                    },
                }
            }

            self._config = AppConfig(**config_dict)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize configuration: {e}")

    @property
    def llm(self) -> Dict[str, LLMSettings]:
        if not self._config:
            raise RuntimeError("Configuration not initialized")
        return self._config.llm


config = Config()
