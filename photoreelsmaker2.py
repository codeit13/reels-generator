import asyncio
import os
import logging
from pathlib import Path
from loguru import logger
from app.photo_video_gen import PhotoVideoGenerator
import ffmpeg
import shutil

# Configure logging
os.makedirs("/app/logs", exist_ok=True)
logger.add("/app/logs/test_photo_video.log", rotation="100 MB", level="DEBUG")

async def test_photo_video():
    """Test the photo video generation process with a single test case"""
    logger.info("Starting photo video test")
    
    # Use existing directories in container
    cache_dir = "/app/cache"
    temp_dir = "/app/tmp/photo-reels"
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)
    
    # Initialize the video generator
    generator = PhotoVideoGenerator(None)  # We're not using the base class for this test
    
    # Test data - use paths within the container
    test_photo = f"{cache_dir}/test_photo.jpg"
    test_audio = f"{cache_dir}/test_audio.mp3"
    
    # Create test assets
    if not os.path.exists(test_photo):
        logger.info("Creating test photo...")
        # Generate a simple test image using ffmpeg
        stream = (
            ffmpeg
            .input('color=c=blue:s=1280x720:d=5', f='lavfi')
            .output(test_photo, vframes=1)
            .overwrite_output()
        )
        stream.run()
    
    if not os.path.exists(test_audio):
        logger.info("Creating test audio...")
        # Generate a silent audio file using ffmpeg
        stream = (
            ffmpeg
            .input('anullsrc=r=44100:cl=stereo', f='lavfi', t=5)
            .output(test_audio, acodec='libmp3lame', ar=44100)
            .overwrite_output()
        )
        stream.run()
    
    # Create test subtitle file
    subtitles_path = f"{cache_dir}/test_subtitles.srt"
    with open(subtitles_path, 'w') as f:
        f.write("1\n00:00:00,000 --> 00:00:05,000\nThis is a test subtitle")
    
    # Create test audio clips data
    audio_clips = [{
        "photo_data": {"photo_path": test_photo},
        "audio_path": test_audio
    }]
    
    try:
        # Generate video
        logger.info("Generating test video...")
        result = await generator.generate_video(
            audio_clips=audio_clips,
            subtitles_path=subtitles_path,
            animation_style="kenburns"
        )
        
        logger.info(f"Test successful! Video generated at: {result}")
        return True, result
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False, str(e)

if __name__ == "__main__":
    logger.info("Running photo video test")
    result, message = asyncio.run(test_photo_video())
    if result:
        print(f"✅ Test passed! Output video: {message}")
    else:
        print(f"❌ Test failed: {message}")