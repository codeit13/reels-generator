import os
import shutil
from typing import Literal

from app.utils.strings import log_attempt_number
from app.utils.strings import make_cuid
from elevenlabs import Voice, VoiceSettings, save
from elevenlabs.client import ElevenLabs
import httpx
from loguru import logger
from pydantic import BaseModel

from app import tiktokvoice
from app.config import speech_cache_path
from app.utils.path_util import search_file, text_to_sha256_hash
from tenacity import retry, stop_after_attempt, wait_fixed

VOICE_PROVIDER = Literal["elevenlabs", "tiktok", "openai", "airforce"]


class SynthConfig(BaseModel):
    # I don't like this line
    voice_provider: VOICE_PROVIDER = "elevenlabs"
    voice: str = "pNInz6obpgDQGcFmaJgB" # Ellie

    static_mode: bool = False
    """ if we're generating static audio for test """


class SynthGenerator:
    def __init__(self, cwd: str, config: SynthConfig):
        self.config = config
        self.cwd = cwd
        self.cache_key: str | None = None

        self.base = os.path.join(self.cwd, "audio_chunks")

        os.makedirs(self.base, exist_ok=True)

        self.client = ElevenLabs(
            api_key=os.getenv("ELEVENLABS_API_KEY"),
        )

    def set_speech_props(self):
        ky = (
            self.config.voice
            if self.config.static_mode
            else make_cuid(self.config.voice + "_")
        )
        self.speech_path = os.path.join(
            self.base,
            f"{self.config.voice_provider}_{ky}.mp3",
        )
        text_hash = text_to_sha256_hash(self.text)

        self.cache_key = f"{self.config.voice}_{text_hash}"

    async def generate_with_eleven(self, text: str) -> str:
        # Prioritize config.voice over environment variable
        voice_id = self.config.voice or os.environ.get("VOICE") or "21m00Tcm4TlvDq8ikWAM"
        
        # Add logging for debugging
        logger.info(f"Using ElevenLabs voice_id: {voice_id}")
        
        voice = Voice(                        
            voice_id=voice_id,  # Fix syntax error here
            settings=VoiceSettings(
                stability=0.71, similarity_boost=0.5, style=0.0, use_speaker_boost=True
            ),
        )

        audio = self.client.generate(
            text=text, voice=voice, model="eleven_multilingual_v2", stream=False
        )

        save(audio, self.speech_path)

        return self.speech_path

    async def generate_with_tiktok(self, text: str) -> str:
        try:
            result = tiktokvoice.tts(text, voice=str(self.config.voice), filename=self.speech_path)
            # Check if the file was actually created
            if not os.path.exists(self.speech_path) or os.path.getsize(self.speech_path) == 0:
                raise ValueError("TikTok voice generation failed to create audio file")
            return self.speech_path
        except Exception as e:
            logger.error(f"TikTok voice generation error: {e}")
            raise

    async def cache_speech(self, text: str):
        try:
            if not self.cache_key:
                logger.warning("Skipping speech cache because it is not set")
                return

            speech_path = os.path.join(speech_cache_path, f"{self.cache_key}.mp3")
            shutil.copy2(self.speech_path, speech_path)
        except Exception as e:
            logger.exception(f"Error in cache_speech(): {e}")

    async def generate_with_openai(self, text: str) -> str:
        raise NotImplementedError

    async def generate_with_airforce(self, text: str) -> str:
        url = f"https://api.airforce/get-audio?text={text}&voice={self.config.voice}"
        async with httpx.AsyncClient() as client:
            res = await client.get(url)
            save(res.content, self.speech_path)
        return self.speech_path

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(4), after=log_attempt_number) # type: ignore
    async def synth_speech(self, text: str) -> str:
        # Add state tracking for failed providers
        if not hasattr(self, '_failed_providers'):
            self._failed_providers = set()
        
        try:
            # Skip if this provider has already failed
            if self.config.voice_provider.lower() in self._failed_providers:
                logger.warning(f"Skipping previously failed provider: {self.config.voice_provider}")
                # Use TikTok as fallback
                old_provider = self.config.voice_provider
                self.config.voice_provider = "tiktok"
                try:
                    return await self._synth_with_provider(text)
                finally:
                    self.config.voice_provider = old_provider
                
            # Attempt with configured provider
            return await self._synth_with_provider(text)
        except Exception as e:
            logger.error(f"Primary voice provider failed: {e}")
            # Mark this provider as failed
            self._failed_providers.add(self.config.voice_provider.lower())
            
            # Switch to fallback provider
            old_provider = self.config.voice_provider
            self.config.voice_provider = "tiktok"  # Use TikTok as fallback
            logger.info(f"Switching to fallback voice provider: {self.config.voice_provider}")
            try:
                return await self._synth_with_provider(text)
            finally:
                # Restore original setting
                self.config.voice_provider = old_provider

    async def _synth_with_provider(self, text: str) -> str:
        self.text = text
        self.set_speech_props()

        cached_speech = search_file(speech_cache_path, self.cache_key)

        if cached_speech:
            logger.info(f"Found speech in cache: {cached_speech}")
            shutil.copy2(cached_speech, self.speech_path)
            return cached_speech

        logger.info(f"Synthesizing text: {text}")

        genarator = None

        if self.config.voice_provider.lower() == "openai":
            genarator = self.generate_with_openai
        elif self.config.voice_provider.lower() == "airforce":
            genarator = self.generate_with_airforce
        elif self.config.voice_provider.lower() == "tiktok":
            genarator = self.generate_with_tiktok
        elif self.config.voice_provider.lower() == "elevenlabs":
            genarator = self.generate_with_eleven
        else:
            raise ValueError(
                f"voice provider {self.config.voice_provider} is not recognized"
            )

        speech_path = await genarator(text)

        await self.cache_speech(text)

        return speech_path