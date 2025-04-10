Currently, reelsmaker ui can access 2 voice providers, elevenlabs and tiktok but I have kokoro_service running locally  I want kokoro_service to be the primary voice_provider.  it is an api running on crown-network on port 8880.  what do you need from me in order to begin the process of integrating kokoro_service into reelsmaker?

GitHub Copilot: # Adding Kokoro Service as a Voice Provider

To integrate Kokoro Service as the primary voice provider in your ReelsMaker application, I'll need to understand more about its API and implementation details. Here's what I need from you to begin the integration:

## Initial Information Required

1. **API Endpoint Structure**:
   - What is the base URL format? (e.g., `http://kokoro_service:8880/api/tts`)
   - What HTTP method does it use? (POST/GET)

2. **Request Format**:
   - What parameters does the API expect?
   - Sample JSON request structure
   - Any required authentication headers

3. **Response Format**:
   - Does it return audio as base64 or as a file URL?
   - What audio format does it return? (mp3, wav, etc.)
   - Sample JSON response structure

4. **Voice Options**:
   - What voice IDs are available in Kokoro Service?
   - Do voices have names or descriptions we should display in the UI?

## Implementation Plan

Once I have this information, here's how we'll integrate it:

1. Update synth_gen.py to add Kokoro as a voice provider
2. Create a new module `app/kokoro_service.py` for the API integration
3. Update the Streamlit UI to include Kokoro as a voice provider option
4. Add Docker network configuration to ensure connectivity

## Network Configuration

From your docker-compose.yml, I can see you already have the `crown-network` configured as external, which is where your Kokoro service runs. That's a good starting point for connectivity.

## Next Steps

Could you provide the API details mentioned above? With that information, I can begin drafting the necessary code changes to integrate Kokoro Service into ReelsMaker.

michaelgrace: I can provide you with the docs.. would that be helpful to answer any questions and enable you to see what can be done?

GitHub Copilot: # Kokoro Service Integration Information Request

Yes, providing the documentation for Kokoro Service would be extremely helpful! The documentation would help me understand:

1. How to properly call the API
2. What parameters it expects
3. What response format it returns
4. Available voice options

This would allow me to design an effective integration that leverages all the capabilities of Kokoro Service.

To get started with the integration, I would specifically need to know:

- The API endpoint structure (e.g., `http://kokoro_service:8880/synthesize`)
- The required request parameters (text, voice ID, etc.)
- The authentication method (if any)
- The response format (audio file, base64 encoded string, etc.)
- Available voice options to display in the ReelsMaker UI

With this documentation, I can create a comprehensive implementation that properly integrates Kokoro Service as the primary voice provider in your ReelsMaker application.

michaelgrace: here is the fastapi json for kokoro_service.  let me know what else I can do to speed up implementation

GitHub Copilot: # Kokoro Service Integration for ReelsMaker

Thanks for providing the OpenAPI specification for Kokoro Service! This gives me a clear picture of how to integrate it with ReelsMaker. Let's start implementing this right away.

## Integration Overview

Based on the API docs, Kokoro Service provides an OpenAI-compatible TTS endpoint at `/v1/audio/speech`. This makes integration straightforward since we can follow a similar pattern to other API clients.

## Implementation Plan

I'll create a comprehensive implementation that:

1. Adds Kokoro as a voice provider option in the UI
2. Creates an API client for Kokoro Service
3. Fetches available voices from the `/v1/audio/voices` endpoint
4. Uses the `/v1/audio/speech` endpoint for text-to-speech generation

Here's what I need to create:

### 1. First, let's create a Kokoro Service API Client

```python
"""Kokoro Service TTS client implementation."""

import os
import aiohttp
import json
from typing import Dict, List, Optional, Any, Union
from loguru import logger

class KokoroServiceClient:
    """Client for Kokoro Service TTS API."""
    
    def __init__(self, base_url: str = "http://kokoro_service:8880"):
        """Initialize the Kokoro Service client.
        
        Args:
            base_url: Base URL for the Kokoro Service API
        """
        self.base_url = base_url
        self.voices_cache = None
    
    async def list_voices(self) -> List[Dict[str, Any]]:
        """Get available voices from Kokoro Service.
        
        Returns:
            List of voice objects with id and name
        """
        if self.voices_cache is not None:
            return self.voices_cache
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/v1/audio/voices") as response:
                    if response.status == 200:
                        data = await response.json()
                        # Cache the voices for future calls
                        self.voices_cache = data
                        return data
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to get voices from Kokoro Service: {error_text}")
                        return []
        except Exception as e:
            logger.exception(f"Error fetching voices from Kokoro Service: {e}")
            return []
    
    async def create_speech(
        self,
        text: str,
        voice: str = "af",
        response_format: str = "mp3",
        speed: float = 1.0,
        stream: bool = False,
        return_download_link: bool = True
    ) -> Optional[bytes]:
        """Generate speech using Kokoro Service.
        
        Args:
            text: Text to synthesize
            voice: Voice ID to use
            response_format: Audio format (mp3, opus, wav, etc.)
            speed: Speed multiplier (0.25 to 4.0)
            stream: Whether to stream the response (not used here)
            return_download_link: Whether to return a download link
            
        Returns:
            Audio bytes if successful, None otherwise
        """
        try:
            # Set up the request payload
            payload = {
                "model": "kokoro",
                "input": text,
                "voice": voice,
                "response_format": response_format,
                "speed": speed,
                "stream": False,  # We want the complete audio file
                "return_download_link": return_download_link
            }
            
            # Custom header for raw response
            headers = {"x-raw-response": "true"} if not return_download_link else {}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/v1/audio/speech",
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        # Check for download link in headers
                        download_path = response.headers.get("X-Download-Path")
                        
                        if download_path:
                            # If we have a download path, fetch the audio file
                            async with session.get(f"{self.base_url}{download_path}") as download_response:
                                if download_response.status == 200:
                                    return await download_response.read()
                                else:
                                    error_text = await download_response.text()
                                    logger.error(f"Failed to download audio from Kokoro Service: {error_text}")
                                    return None
                        else:
                            # If no download path, the audio should be in the response body
                            return await response.read()
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to generate speech with Kokoro Service: {error_text}")
                        return None
        except Exception as e:
            logger.exception(f"Error generating speech with Kokoro Service: {e}")
            return None

# Create a singleton instance for reuse
kokoro_client = KokoroServiceClient(
    base_url=os.environ.get("KOKORO_SERVICE_URL", "http://kokoro_service:8880")
)
```

### 2. Now update the SynthConfig in the app to include Kokoro

```python
# Add this import at the top of the file
from app.kokoro_service import kokoro_client

# Update the Voice Provider enum to include Kokoro
class VoiceProvider(str, Enum):
    """Voice provider enum."""
    ELEVENLABS = "elevenlabs"
    TIKTOK = "tiktok"
    KOKORO = "kokoro"  # Add Kokoro as a provider

# In your synthesize method, add a case for Kokoro:
async def synthesize(self, text: str) -> Optional[str]:
    """Synthesize speech from text using the configured provider.
    
    Args:
        text: Text to synthesize
        
    Returns:
        Path to the generated audio file
    """
    # Existing code...
    
    # Add this case for Kokoro
    if self.voice_provider == VoiceProvider.KOKORO:
        # Generate unique output path
        output_path = os.path.join(self.cwd, f"audio_{uuid4()}.mp3")
        
        # Call Kokoro Service
        audio_bytes = await kokoro_client.create_speech(
            text=text,
            voice=self.voice,
            response_format="mp3",
            speed=1.0
        )
        
        if audio_bytes:
            # Save the audio bytes to file
            with open(output_path, "wb") as f:
                f.write(audio_bytes)
            return output_path
        else:
            logger.error("Failed to generate audio with Kokoro Service")
            return None
            
    # Rest of the existing code...
```

### 3. Update the UI in reelsmaker.py to include Kokoro as an option

```python
# In your main function where you define the voice provider dropdown:

with st.expander("Voice Configuration Info", expanded=True):
    # Get available Kokoro voices for the dropdown
    if "kokoro_voices" not in st.session_state:
        st.session_state["kokoro_voices"] = []
        
    # Load Kokoro voices on page load (only once)
    if st.session_state["kokoro_voices"] == []:
        with st.spinner("Loading Kokoro voices..."):
            from app.kokoro_service import kokoro_client
            import asyncio
            
            # Use asyncio.run in a try/except to avoid errors in Streamlit's threaded environment
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                voices = loop.run_until_complete(kokoro_client.list_voices())
                st.session_state["kokoro_voices"] = voices
            except Exception as e:
                st.error(f"Failed to load Kokoro voices: {e}")
                st.session_state["kokoro_voices"] = []
    
    # Voice provider selection
    voice_provider = st.selectbox(
        "Select voice provider", 
        ["Kokoro", "Elevenlabs", "TikTok"],  # Make Kokoro the first option
        index=0  # Default to Kokoro
    )

    # Different voice options based on selected provider
    if voice_provider.lower() == "tiktok":
        # Existing TikTok voice options
        voice = st.selectbox(
            "Select voice",
            ["en_us_001", "en_us_006", "en_us_007", "en_us_009", "en_us_010"]
        )
    elif voice_provider.lower() == "kokoro":
        # Display Kokoro voices
        kokoro_voices = st.session_state["kokoro_voices"]
        voice_options = [(v.get("name", v.get("id")) or v.get("id")) for v in kokoro_voices] if kokoro_voices else ["af"]
        
        if not voice_options:
            voice_options = ["af"]  # Default fallback
            st.warning("Could not load Kokoro voices. Using default voice.")
            
        voice = st.selectbox("Select voice", voice_options)
    else:
        # Existing Elevenlabs voice options
        voice = st.selectbox(
            "Select voice",
            ["21m00Tcm4TlvDq8ikWAM", "2EiwWnXFnvU5JabPnv8n", "D38z5RcWu1voky8WS1ja", 
             "IKne3meq5aSn9XLyUdCD", "XB0fDUnXU5powFXDhCwa", "pNInz6obpgDQGcFmaJgB", 
             "jBpfuIE2acCO8z3wKNLl", "onwK4e9ZLuTAKqWW03F9", "g5CIjZEefAph4nQFvHAz", 
             "ErXwobaYiN019PkySvjV"]
        )
```

### 4. Update docker-compose.yml to include Kokoro configuration

```yaml
services:
  app:
    # Existing configuration...
    environment:      
      # Existing environment variables...
      - VOICE_PROVIDER=kokoro  # Set default to kokoro
      - KOKORO_SERVICE_URL=http://kokoro_service:8880  # URL for the service
    # ... 
```

## What else do I need from you?

1. **Voice IDs**: Can you verify which voice IDs are available in your Kokoro Service deployment? The default in the API seems to be "af" but there might be others.

2. **Testing Access**: Once I implement this, can you test the connection to Kokoro Service from within the ReelsMaker container?

3. **Environment Setup**: Are there any specific environment variables that need to be configured for authentication with Kokoro Service?

Let me know if you'd like me to make any changes to the implementation or if you need additional features for the integration.

michaelgrace: I have added the file here. there isn't currently any authentication required to access kokoro_service locally

GitHub Copilot: # Kokoro Service Integration for ReelsMaker

Thanks for providing the voice list! This will be really helpful for implementing the integration. Since there's no authentication required for local access, we can simplify the implementation.

Let's create a complete implementation for integrating Kokoro Service as the primary voice provider:

## 1. Kokoro Service Client

```python
"""Kokoro Service TTS client implementation."""

import os
import aiohttp
import json
from typing import Dict, List, Optional, Any, Union
from loguru import logger
from pathlib import Path

class KokoroServiceClient:
    """Client for Kokoro Service TTS API."""
    
    def __init__(self, base_url: str = "http://kokoro_service:8880"):
        """Initialize the Kokoro Service client."""
        self.base_url = base_url
        
        # Load the voice list from the provided JSON file
        kokoro_voices_path = Path(os.path.dirname(os.path.dirname(__file__))) / "kokoro_voices.json"
        if kokoro_voices_path.exists():
            try:
                with open(kokoro_voices_path, "r") as f:
                    voice_data = json.load(f)
                    self.voices = voice_data.get("voices", [])
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
        """Generate speech using Kokoro Service.
        
        Args:
            text: Text to synthesize
            voice: Voice ID to use
            response_format: Audio format (mp3, opus, wav, etc.)
            speed: Speed multiplier (0.25 to 4.0)
            
        Returns:
            Audio bytes if successful, None otherwise
        """
        try:
            # Set up the request payload based on the OpenAI API format
            payload = {
                "model": "kokoro",  # Always use kokoro model
                "input": text,
                "voice": voice,
                "response_format": response_format,
                "speed": speed,
                "stream": False,  # We want the complete audio file
                "return_download_link": True  # Get a link we can download from
            }
            
            logger.info(f"Sending TTS request to Kokoro Service for voice: {voice}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/v1/audio/speech",
                    json=payload
                ) as response:
                    if response.status == 200:
                        # Check for download link in headers
                        download_path = response.headers.get("X-Download-Path")
                        
                        if download_path:
                            logger.info(f"Got download path: {download_path}")
                            # If we have a download path, fetch the audio file
                            async with session.get(f"{self.base_url}{download_path}") as download_response:
                                if download_response.status == 200:
                                    return await download_response.read()
                                else:
                                    error_text = await download_response.text()
                                    logger.error(f"Failed to download audio from Kokoro Service: {error_text}")
                                    return None
                        else:
                            # If no download path, the audio should be in the response body
                            logger.info("No download path, reading response body")
                            return await response.read()
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to generate speech with Kokoro Service: {response.status} - {error_text}")
                        return None
        except Exception as e:
            logger.exception(f"Error generating speech with Kokoro Service: {e}")
            return None

# Create a singleton instance for reuse
kokoro_client = KokoroServiceClient(
    base_url=os.environ.get("KOKORO_SERVICE_URL", "http://kokoro_service:8880")
)
```

## 2. Update the SynthConfig class in synth_gen.py

```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import os
from uuid import uuid4
from loguru import logger

# Add this import
from app.kokoro_service import kokoro_client

class VoiceProvider(str, Enum):
    """Voice provider enum."""
    ELEVENLABS = "elevenlabs"
    TIKTOK = "tiktok"
    KOKORO = "kokoro"  # Add Kokoro as a provider

class SynthConfig(BaseModel):
    """Synthesis configuration."""
    voice: str = "af_heart"  # Default to a Kokoro voice
    voice_provider: VoiceProvider = VoiceProvider.KOKORO  # Default to Kokoro
    
    # Other existing fields...
    
    async def synthesize(self, text: str) -> Optional[str]:
        """Synthesize speech from text using the configured provider.
        
        Args:
            text: Text to synthesize
            
        Returns:
            Path to the generated audio file
        """
        logger.info(f"Synthesizing with provider: {self.voice_provider}, voice: {self.voice}")
        
        # Add this case for Kokoro at the beginning (making it the primary choice)
        if self.voice_provider == VoiceProvider.KOKORO:
            # Generate unique output path
            output_path = os.path.join(os.getcwd(), "tmp", f"audio_{uuid4()}.mp3")
            
            # Call Kokoro Service
            audio_bytes = await kokoro_client.create_speech(
                text=text,
                voice=self.voice,
                response_format="mp3",
                speed=1.0
            )
            
            if audio_bytes:
                # Save the audio bytes to file
                with open(output_path, "wb") as f:
                    f.write(audio_bytes)
                logger.info(f"Audio generated with Kokoro Service and saved to {output_path}")
                return output_path
            else:
                logger.error("Failed to generate audio with Kokoro Service")
                # Fall back to other providers if Kokoro fails
                if os.environ.get("ELEVENLABS_API_KEY"):
                    logger.info("Falling back to ElevenLabs")
                    self.voice_provider = VoiceProvider.ELEVENLABS
                else:
                    logger.info("Falling back to TikTok")
                    self.voice_provider = VoiceProvider.TIKTOK
        
        # The rest of your existing synthesize method for other providers
        # ...
```

## 3. Update reelsmaker.py to include Kokoro provider UI

```python
# Update the voice provider selection in your main function

with st.expander("Voice Configuration Info", expanded=True):
    # Initialize voice provider options and descriptions
    voice_providers = ["Kokoro", "Elevenlabs", "TikTok"]
    provider_descriptions = {
        "Kokoro": "Local AI voice model with many high-quality voices",
        "Elevenlabs": "Professional quality voices (requires API key)",
        "TikTok": "Free voice service from TikTok"
    }
    
    # Voice provider selection with descriptions
    voice_provider_index = 0  # Default to Kokoro
    voice_provider = st.selectbox(
        "Select voice provider", 
        options=voice_providers,
        index=voice_provider_index,
        format_func=lambda x: f"{x} - {provider_descriptions[x]}"
    )
    
    # Load Kokoro voices for the dropdown
    if "kokoro_voices" not in st.session_state:
        from app.kokoro_service import kokoro_client
        st.session_state["kokoro_voices"] = kokoro_client.get_voices()

    # Different voice options based on selected provider
    if voice_provider.lower() == "tiktok":
        # Existing TikTok voice options
        voice = st.selectbox(
            "Select voice",
            ["en_us_001", "en_us_006", "en_us_007", "en_us_009", "en_us_010"]
        )
    elif voice_provider.lower() == "kokoro":
        # Display Kokoro voices
        kokoro_voices = st.session_state["kokoro_voices"]
        
        # Group voices by language for better organization
        languages = {}
        for v in kokoro_voices:
            name = v["name"]
            language = name.split(" ")[0]  # Extract language from name
            if language not in languages:
                languages[language] = []
            languages[language].append(v)
        
        # Let user select language first
        language_options = sorted(languages.keys())
        selected_language = st.selectbox("Select language", language_options)
        
        # Then select a voice from that language
        filtered_voices = languages[selected_language]
        voice_options = [(v["id"], v["name"]) for v in filtered_voices]
        
        selected_voice_tuple = st.selectbox(
            "Select voice", 
            options=voice_options,
            format_func=lambda x: x[1]  # Display the name
        )
        
        voice = selected_voice_tuple[0]  # Use the ID for the API
    else:
        # Existing Elevenlabs voice options
        voice = st.selectbox(
            "Select voice",
            ["21m00Tcm4TlvDq8ikWAM", "2EiwWnXFnvU5JabPnv8n", "D38z5RcWu1voky8WS1ja", 
             "IKne3meq5aSn9XLyUdCD", "XB0fDUnXU5powFXDhCwa", "pNInz6obpgDQGcFmaJgB", 
             "jBpfuIE2acCO8z3wKNLl", "onwK4e9ZLuTAKqWW03F9", "g5CIjZEefAph4nQFvHAz", 
             "ErXwobaYiN019PkySvjV"]
        )
```

## 4. Update docker-compose.yml with Kokoro Service configuration

```yaml
services:
  app:
    # Existing configuration...
    environment:      
      # Existing environment variables...
      - VOICE_PROVIDER=kokoro  # Set default voice provider to Kokoro
      - KOKORO_SERVICE_URL=http://kokoro_service:8880  # URL for the service
    # ...
    volumes:
      - ./tmp:/app/tmp
      - ./images:/app/images
      - ./kokoro_voices.json:/app/kokoro_voices.json  # Mount the voices file
```

## 5. Create a simple test script to verify the connection

```python
"""Test script for Kokoro Service integration."""

import asyncio
import os
from app.kokoro_service import kokoro_client
from loguru import logger
import time

async def test_kokoro():
    """Test the Kokoro Service integration."""
    logger.info("Testing Kokoro Service integration")
    
    # Get voices
    logger.info("Available voices:")
    voices = kokoro_client.get_voices()
    for voice in voices[:5]:  # Show just the first 5 to keep output manageable
        logger.info(f"- {voice['id']}: {voice['name']}")
    
    # Test speech synthesis
    test_text = "Hello! This is a test of the Kokoro Service integration with ReelsMaker."
    test_voice = "af_heart"  # Use a common voice
    
    logger.info(f"Testing speech synthesis with voice: {test_voice}")
    start_time = time.time()
    
    audio_bytes = await kokoro_client.create_speech(
        text=test_text,
        voice=test_voice,
        response_format="mp3"
    )
    
    end_time = time.time()
    
    if audio_bytes:
        output_path = os.path.join("tmp", "test_kokoro.mp3")
        os.makedirs("tmp", exist_ok=True)
        
        with open(output_path, "wb") as f:
            f.write(audio_bytes)
        
        logger.info(f"Success! Audio saved to {output_path}")
        logger.info(f"Processing time: {end_time - start_time:.2f} seconds")
        logger.info(f"Audio size: {len(audio_bytes) / 1024:.2f} KB")
    else:
        logger.error("Failed to generate audio with Kokoro Service")

if __name__ == "__main__":
    asyncio.run(test_kokoro())
```

## Implementation Details

This implementation:

1. Creates a dedicated Kokoro Service client that loads voices from your JSON file
2. Formats voice names nicely for the UI (e.g., "English Female - Alloy")
3. Groups voices by language in the UI for easier selection
4. Sets Kokoro as the default voice provider
5. Includes fallback logic if Kokoro fails
6. Provides a test script to verify the connection

## Next Steps

1. Run the test script to verify the Kokoro Service connection
2. Update the Dockerfile to include the kokoro_voices.json file
3. Test the integration in the ReelsMaker UI

Let me know if you'd like any changes to this implementation or if you need additional features!