"""Kokoro Service TTS client implementation."""

import os
import aiohttp
import json
import hashlib
import shutil
from typing import Dict, List, Optional, Any, Union
from loguru import logger
from pathlib import Path

class KokoroServiceClient:
    """Client for Kokoro Service TTS API."""
    
    def __init__(self, base_url: str = "http://kokoro_service:8880"):
        """Initialize the Kokoro Service client."""
        self.base_url = base_url
        
        # Load the voice list from the provided JSON file in the data folder
        kokoro_voices_path = Path(os.path.dirname(os.path.dirname(__file__))) / "data" / "kokoro_voices.json"
        if kokoro_voices_path.exists():
            try:
                with open(kokoro_voices_path, "r") as f:
                    voice_data = json.load(f)
                    self.voices = voice_data.get("voices", [])
                    logger.info(f"Loaded {len(self.voices)} Kokoro voices from data folder")
            except Exception as e:
                logger.error(f"Failed to load Kokoro voices from file: {e}")
                self.voices = ["af_heart"]  # Default fallback
        else:
            logger.warning(f"Kokoro voices file not found at {kokoro_voices_path}")
            self.voices = ["af_heart"]  # Default fallback
    
    def get_voices(self) -> List[Dict[str, str]]:
        """Return the list of available voices in a formatted way.
        
        Returns:
            List of voice dictionaries with id and name
        """
        formatted_voices = []
        
        # Format the voice information for the UI
        for voice_id in self.voices:
            # Parse voice info from ID (e.g., af_heart -> English Female Alloy)
            parts = voice_id.split('_')
            if len(parts) >= 2:
                lang_gender = parts[0]
                name = parts[1]
                
                # Map language codes
                lang_map = {
                    'a': 'English',
                    'b': 'British',
                    'e': 'Spanish',
                    'h': 'Hindi',
                    'i': 'Italian',
                    'j': 'Japanese',
                    'p': 'Portuguese',
                    'z': 'Chinese'
                }
                
                # Get language from first letter
                language = lang_map.get(lang_gender[0], 'Unknown')
                
                # Get gender from second letter
                gender = 'Female' if lang_gender[1] == 'f' else 'Male'
                
                # Format the display name
                display_name = f"{language} {gender} - {name.capitalize()}"
                
                formatted_voices.append({
                    "id": voice_id,
                    "name": display_name
                })
            else:
                # Fallback for voice IDs that don't match the expected format
                formatted_voices.append({
                    "id": voice_id,
                    "name": voice_id
                })
        
        return formatted_voices
    
    async def create_speech(
        self,
        text: str,
        voice: str = "af_heart",
        response_format: str = "mp3",
        speed: float = 1.0
    ) -> Optional[bytes]:
        """Generate speech using Kokoro Service."""
        try:
            # Start with the basic payload that worked in our test
            payload = {
                "input": text,
                "voice": voice
            }
            
            # Add optional parameters if they differ from defaults
            if response_format != "mp3":
                payload["response_format"] = response_format
            
            if speed != 1.0:
                payload["speed"] = speed
                
            logger.info(f"Sending TTS request to Kokoro Service for voice: {voice}")
            logger.debug(f"Payload: {json.dumps(payload)}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/v1/audio/speech",
                    json=payload
                ) as response:
                    if response.status == 200:
                        # Check content type to determine format
                        content_type = response.headers.get('Content-Type', '')
                        logger.debug(f"Response content type: {content_type}")
                        
                        if 'application/json' in content_type:
                            # Process as JSON
                            response_data = await response.json()
                            
                            if "audio" in response_data:
                                # Base64 encoded audio
                                import base64
                                audio_b64 = response_data["audio"]
                                return base64.b64decode(audio_b64)
                            elif "download_link" in response_data:
                                # Download from link
                                download_url = response_data["download_link"]
                                
                                async with session.get(download_url) as dl_response:
                                    if dl_response.status == 200:
                                        return await dl_response.read()
                                    else:
                                        logger.error(f"Failed to download audio: {dl_response.status}")
                                        return None
                            else:
                                logger.error("Response doesn't contain audio data or download link")
                                return None
                        else:
                            # Return the direct audio bytes
                            logger.info("Received direct audio data from Kokoro Service")
                            return await response.read()
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to generate speech: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.exception(f"Error generating speech with Kokoro Service: {e}")
            return None


# Create a singleton instance for reuse
kokoro_client = KokoroServiceClient(
    base_url=os.environ.get("KOKORO_SERVICE_URL", "http://kokoro_service:8880")
)