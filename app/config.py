import os
import threading
import tomllib
from pathlib import Path
from typing import Dict, Optional

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

class WebSearchSettings(BaseModel):
    open_web_search:bool = Field(False, description="Is open web search")
    api_url: str = Field(..., description="Web search API URL")
    api_key: str = Field(..., description="Web search API Key")
    num_results: int = Field(5, description="Default number of search results")

class AppConfig(BaseModel):
    llm: Dict[str, LLMSettings]
    web_search: WebSearchSettings


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
        root = PROJECT_ROOT
        config_path = root / "config" / "config.toml"
        if config_path.exists():
            return config_path
        example_path = root / "config" / "config.example.toml"
        if example_path.exists():
            return example_path
        raise FileNotFoundError("No configuration file found in config directory")

    def _load_config(self) -> dict:
        config_path = self._get_config_path()
        with config_path.open("rb") as f:
            return tomllib.load(f)

    def _load_initial_config(self):
        raw_config = self._load_config()
        base_llm = raw_config.get("llm", {})
        llm_overrides = {
            k: v for k, v in raw_config.get("llm", {}).items() if isinstance(v, dict)
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

        # 解析 web_search 配置，并允许环境变量覆盖
        web_search_config = raw_config.get("web_search", {})
        web_search_settings = WebSearchSettings(
            open_web_search=web_search_config.get("open_web_search", False),
            api_url=web_search_config.get("api_url", ""),
            api_key=web_search_config.get("api_key", ""),
            num_results=web_search_config.get("num_results", 10),
        )

        config_dict = {
            "llm": {
                "default": LLMSettings(**default_settings),
                **{
                    name: LLMSettings(**{**default_settings, **override_config})
                    for name, override_config in llm_overrides.items()
                },
            },
            "web_search": web_search_settings,  # 直接赋值 WebSearchSettings 对象
        }

        self._config = AppConfig(**config_dict)

    @property
    def llm(self) -> Dict[str, LLMSettings]:
        return self._config.llm

    @property
    def web_search(self) -> WebSearchSettings:
        return self._config.web_search


config = Config()
