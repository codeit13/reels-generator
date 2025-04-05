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
    test_voice = "af_alloy"  # Use a common voice
    
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