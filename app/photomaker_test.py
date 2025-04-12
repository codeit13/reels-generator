import os
import sys
import asyncio
from pathlib import Path
from loguru import logger

# Add the parent directory to the path to allow importing app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.photo_reels_maker import PhotoReelsMaker, PhotoReelsMakerConfig
from app.base import StartResponse
from app.synth_gen import VoiceProvider

async def test_photo_reels_maker():
    """Test function for the photo reels maker."""
    logger.info("Starting PhotoReelsMaker test")
    
    # Create configuration
    config = PhotoReelsMakerConfig(
        prompt="beautiful nature landscapes with mountains and lakes",
        voice="af_heart",  # Using default Kokoro voice
        voice_provider=VoiceProvider.KOKORO,
        speech_rate=0.8,
        aspect_ratio="16:9",  # Landscape mode
        max_photos=5,
        photo_duration=5.0,
        animation_style="kenburns",
        transition_style="fade"
    )
    
    # Create photo reels maker
    maker = PhotoReelsMaker(config)
    
    # Start the process
    response = await maker.start()
    
    # Check the result
    if response.status == "success":
        logger.success(f"Successfully created photo video: {response.video_file_path}")
        logger.info(f"Video file size: {os.path.getsize(response.video_file_path) / (1024 * 1024):.2f} MB")
    else:
        logger.error(f"Failed to create photo video. Status: {response.status}")

if __name__ == "__main__":
    # Ensure required environment variables are set
    if not os.environ.get("PEXELS_API_KEY"):
        logger.error("PEXELS_API_KEY environment variable not set")
        logger.info("Set it using: export PEXELS_API_KEY='your_key_here'")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_dir = os.environ.get("PHOTO_OUTPUT_DIR", "./outputs/photos")
    os.makedirs(output_dir, exist_ok=True)
    
    # Run the test
    asyncio.run(test_photo_reels_maker())