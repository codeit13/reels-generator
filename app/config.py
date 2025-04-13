import os
import json
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Literal

from loguru import logger
load_dotenv()

parent = os.getcwd()

videos_cache_path = os.path.join(parent, "cache/videos_cache")
speech_cache_path = os.path.join(parent, "cache/speech_cache")
audios_cache_path = os.path.join(parent, "cache/audios_cache")
images_cache_path = os.path.join(parent, "cache/images_cache")
fonts_cache_path = os.path.join(parent, "cache/fonts_cache")
llm_cache_path = os.path.join(parent, "cache/llm_cache")

def ensure_caches():
    os.makedirs(videos_cache_path, exist_ok=True)
    os.makedirs(speech_cache_path, exist_ok=True)
    os.makedirs(audios_cache_path, exist_ok=True)
    os.makedirs(images_cache_path, exist_ok=True)
    os.makedirs(fonts_cache_path, exist_ok=True)
    os.makedirs(llm_cache_path, exist_ok=True)


ensure_caches()



env_file = ".env"
mode = os.getenv("ENV")

if mode == "production":
    logger.info("Running in production mode:" + env_file)
    env_file = ".env.production"

logger.debug(f"Loading env file: {env_file}")

# loading env for prisma schema that don't have access to this settings class
load_dotenv(env_file)


class __Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=env_file, extra="ignore")

    IMAGE_PROVIDER: Literal["pollination", "deepinfra", "together"] = "deepinfra"
    TOGETHER_API_KEY: str | None = Field(default=None)    
    OPENAI_MODEL_NAME: str | None = Field(default="gpt-3.5-turbo")
    # SENTRY_DSN: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None, validation_alias='OPENAI_API_KEY')
    subtitle_max_chars: int = Field(default=35, validation_alias='SUBTITLE_MAX_CHARS')

# all ways use this settings rather than using __Settings()
settings = __Settings()  # type: ignore

if not mode == "production":
    # us pass and comment out the code below it when disabling logging
    # pass
    # Create a safe version of settings without API keys
    safe_settings = settings.model_dump()
    # Remove sensitive keys
    for key in list(safe_settings.keys()):
        if "API_KEY" in key or "KEY" in key:
            safe_settings[key] = "***REDACTED***"
    # Log the safe version correctly
    logger.debug(json.dumps(safe_settings, indent=3))
