from loguru import logger
import os
import ffmpeg
import aiohttp
import tempfile
from pathlib import Path
import multiprocessing
import time
import shutil

# Make PyTorch optional
TORCH_AVAILABLE = False
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    # PyTorch not available, but we can still proceed
    pass

from app.base import (
    BaseEngine,
    BaseGeneratorConfig,
    FileClip,
    StartResponse,
    TempData,
)
from app.utils.strings import split_by_dot_or_newline
from app.utils.path_util import download_resource
from app.utils.metrics_logger import MetricsLogger
from app.photo_video_gen import PhotoVideoGenerator
from app.synth_gen import SynthGenerator, SynthConfig, VoiceProvider
from app.photo_pexel import search_for_stock_photos
from typing import List, Dict, Optional, Any, Union

class PhotoReelsMakerConfig(BaseGeneratorConfig):
    max_photos: int = 3  # Default max photos per segment
    photo_duration: float = 5.0  # Default duration for each photo in seconds
    animation_style: str = "kenburns"  # Default animation style
    transition_style: str = "fade"  # Default transition style
    photo_endpoint_type: str = "search"  # Default endpoint type
    voice: str = "af_heart"  # Default voice ID
    voice_provider: VoiceProvider = VoiceProvider.KOKORO  # Default voice provider
    speech_rate: float = 1.0  # Default speech rate
    aspect_ratio: str = "16:9"  # Default aspect ratio (16:9, 9:16, or 1:1)
    background_audio_url: Optional[str] = None  # Background music URL

class PhotoReelsMaker(BaseEngine):
    def __init__(self, config: PhotoReelsMakerConfig):
        super().__init__(config)
        self.config = config
        
        # Initialize metrics logger
        self.metrics_logger = MetricsLogger(enabled=True)
        self.metrics_logger.initialize()
        
        # Initialize photo video generator
        self.photo_video_generator = PhotoVideoGenerator(self)
        
        # Initialize the synthesizer for audio generation
        self.synth_config = SynthConfig(
            voice=self.config.voice,
            voice_provider=self.config.voice_provider,
            speech_rate=self.config.speech_rate
        )
        self.synth_generator = SynthGenerator(self.cwd, self.synth_config)
        
        # Initialize audio_clips to avoid AttributeError in cleanup
        self.audio_clips = []
        self.subtitles_path = None

    async def generate_script(self, prompt: str) -> str:
        """Generate a script based on the provided prompt."""
        logger.info(f"Generating script for prompt: {prompt}")
        
        # If script is already provided in config, use it
        if self.config.script:
            return self.config.script
            
        # Otherwise generate it using LLM
        try:
            script = await self._generate_script_internal(prompt)
            return script
        except Exception as e:
            logger.error(f"Failed to generate script: {e}")
            # Return a simple default script as fallback
            return "This is a photo story about nature and its beauty."

    async def _generate_script_internal(self, prompt: str) -> str:
        """Internal method to generate a script using LLM."""
        # This is a simplified placeholder - in production this would use your LLM integration
        return f"Here is a story about {prompt}. It showcases beautiful imagery with an engaging narrative."
        
    async def generate_search_terms(self, script, max_hashtags: int = 5):
        """Generate search terms based on the script for photo searches."""
        # For simplicity, we'll just use the sentences as search terms
        # In production, you might want to use LLM to extract better keywords
        sentences = split_by_dot_or_newline(script)
        search_terms = [sentence.strip() for sentence in sentences if sentence.strip()]
        
        # Limit to first few sentences if too many
        if len(search_terms) > max_hashtags:
            search_terms = search_terms[:max_hashtags]
            
        logger.info(f"Generated {len(search_terms)} search terms from script")
        return search_terms

    async def download_photos(self, search_terms: List[str], orientation: str = None, endpoint_type: str = "search"):
        """Download photos based on search terms."""
        logger.info(f"Downloading photos for {len(search_terms)} search terms using {endpoint_type} endpoint")
        
        photos_data = []
        
        for term in search_terms:
            try:
                # Search for photos using the Pexels API with specified endpoint
                photos = await search_for_stock_photos(
                    limit=1,  # Just get one photo per search term
                    query=term,
                    orientation=orientation,
                    endpoint_type=endpoint_type,  # Use the new parameter
                    metrics_logger=self.metrics_logger
                )
                
                if photos:
                    # Get the first photo
                    photo = photos[0]
                    
                    # Download the photo
                    photo_url = photo['src']['large']  # Use large size for better quality
                    
                    # Create a temporary file to store the photo
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        # Download the image
                        async with aiohttp.ClientSession() as session:
                            async with session.get(photo_url) as resp:
                                if resp.status == 200:
                                    content = await resp.read()
                                    tmp.write(content)
                                    photo_path = tmp.name
                                else:
                                    logger.error(f"Failed to download photo: {resp.status}")
                                    continue
                    
                    # Add the photo data to our list
                    photos_data.append({
                        "term": term,
                        "photo_path": photo_path,
                        "metadata": photo
                    })
                    logger.info(f"Downloaded photo for term '{term}'")
                else:
                    logger.warning(f"No photos found for term '{term}'")
            except Exception as e:
                logger.error(f"Error downloading photo for term '{term}': {e}")
        
        return photos_data

    def check_cancellation(self, st_state):
        """Check if the user requested to cancel the process."""
        if st_state and hasattr(st_state, "get") and st_state.get("cancel_requested", False):
            logger.info("Cancellation requested by user")
            return True
        return False

    async def start(self, st_state=None) -> StartResponse:
        """
        Start the photo-to-video generation process.
        
        Args:
            st_state: Optional state object for cancellation checking
            
        Returns:
            StartResponse with the path to the generated video
        """
        # Get the script
        script = await self.generate_script(self.config.prompt)
        self.config.script = script  # Store for later use
        
        # Extract search terms from the script
        search_terms = await self.generate_search_terms(script)
        
        # Determine orientation based on aspect ratio
        orientation = "landscape"  # Default
        if self.config.aspect_ratio == "9:16":
            orientation = "portrait"
        elif self.config.aspect_ratio == "1:1":
            orientation = "square"
        
        # Download photos for each search term
        photo_data = await self.download_photos(search_terms, orientation, self.config.photo_endpoint_type)
        
        # Check if photos were found
        if not photo_data:
            logger.error("No photos could be downloaded. Cannot continue with video generation.")
            return StartResponse(status="error", error_message="No photos found", video_file_path=None)

        # Check for cancellation
        if self.check_cancellation(st_state):
            self.cleanup_temp_files()
            return StartResponse(status="cancelled", video_file_path=None)
        
        # Create audio for each segment
        sentences = split_by_dot_or_newline(script)
        self.audio_clips = []  # Store on the instance instead of local variable
        
        for i, sentence in enumerate(sentences):
            # Only process if we have photos available
            if i >= len(photo_data):
                logger.warning(f"No photo available for sentence {i+1}, skipping")
                continue
                
            try:
                audio_path = await self.synth_generator.synth_speech(sentence)
                if audio_path:
                    self.audio_clips.append({
                        "sentence": sentence,
                        "audio_path": audio_path,
                        "photo_data": photo_data[i]
                    })
                else:
                    # Generate silent audio as a fallback if TTS fails
                    logger.warning(f"Failed to generate audio for sentence {i+1}, creating silent audio")
                    silent_audio_path = await self._generate_silent_audio(len(sentence) / 15)  # Rough estimate
                    self.audio_clips.append({
                        "sentence": sentence,
                        "audio_path": silent_audio_path,
                        "photo_data": photo_data[i]
                    })
            except Exception as e:
                # Generate silent audio as a fallback if TTS fails
                logger.error(f"Error generating audio for sentence {i+1}: {e}")
                silent_audio_path = await self._generate_silent_audio(len(sentence) / 15)  # Rough estimate
                self.audio_clips.append({
                    "sentence": sentence,
                    "audio_path": silent_audio_path,
                    "photo_data": photo_data[i]
                })
        
        # Check for cancellation again
        if self.check_cancellation(st_state):
            self.cleanup_temp_files()
            return StartResponse(status="cancelled", video_file_path=None)
        
        # Check if audio clips were generated
        if len(self.audio_clips) == 0:
            logger.error("No audio clips were generated. Cannot create video.")
            return StartResponse(status="error", error_message="Failed to generate audio", video_file_path="")
        
        # Generate subtitles
        subtitles_path = await self.generate_subtitles(self.audio_clips)
        
        # Generate the final video
        video_path = await self.photo_video_generator.generate_video(
            audio_clips=self.audio_clips,
            subtitles_path=subtitles_path,
            aspect_ratio=self.config.aspect_ratio,
            animation_style=self.config.animation_style,
            transition_style=self.config.transition_style,
            background_music_path=self.config.background_audio_url
        )
        
        return StartResponse(
            status="success",
            video_file_path=video_path
        )
    
    async def generate_subtitles(self, audio_clips):
        """
        Generate subtitles for the audio clips.
        
        Args:
            audio_clips: List of dictionaries with sentence and audio path
            
        Returns:
            Path to the generated subtitles file
        """
        import pysrt
        from datetime import timedelta
        from pydub import AudioSegment
        
        subs = pysrt.SubRipFile()
        
        current_time = 0  # Start time in seconds
        
        for i, clip in enumerate(audio_clips):
            # Get audio duration
            audio = AudioSegment.from_file(clip["audio_path"])
            duration = len(audio) / 1000.0  # Convert ms to seconds
            
            # Create subtitle
            # FIX: Convert timedelta to hours, minutes, seconds, milliseconds
            start_time_td = timedelta(seconds=current_time)
            end_time_td = timedelta(seconds=current_time + duration)
            
            # Convert timedelta to components for SubRipTime
            start_hours, remainder = divmod(start_time_td.seconds, 3600)
            start_minutes, start_seconds = divmod(remainder, 60)
            start_milliseconds = start_time_td.microseconds // 1000
            
            end_hours, remainder = divmod(end_time_td.seconds, 3600)
            end_minutes, end_seconds = divmod(remainder, 60)
            end_milliseconds = end_time_td.microseconds // 1000
            
            # Create SubRipTime objects with the components
            start = pysrt.SubRipTime(hours=start_hours, minutes=start_minutes, 
                                   seconds=start_seconds, milliseconds=start_milliseconds)
            end = pysrt.SubRipTime(hours=end_hours, minutes=end_minutes, 
                                 seconds=end_seconds, milliseconds=end_milliseconds)
            
            # Create the subtitle item
            subtitle = pysrt.SubRipItem(index=i+1, start=start, end=end, text=clip["sentence"])
            subs.append(subtitle)
            
            # Update current time for next subtitle
            current_time += duration
        
        # Write subtitles to file
        subtitle_path = os.path.join(self.cwd, "tmp", f"subtitles_{int(time.time())}.srt")
        os.makedirs(os.path.dirname(subtitle_path), exist_ok=True)
        subs.save(subtitle_path, encoding='utf-8')
        
        return subtitle_path
    
    async def _generate_silent_audio(self, duration=3.0):
        """Generate silent audio as a fallback when TTS fails"""
        from pydub import AudioSegment
        import os

        # Create temp directory if it doesn't exist
        os.makedirs(os.path.join(self.cwd, "tmp"), exist_ok=True)
        
        # Generate a silent audio segment
        silent_audio = AudioSegment.silent(duration=int(duration * 1000))
        
        # Save to file
        output_path = os.path.join(self.cwd, "tmp", f"silent_{int(time.time())}.wav")
        silent_audio.export(output_path, format="wav")
        
        return output_path

    def cleanup_temp_files(self):
        """Clean up temporary files created during processing."""
        try:
            # Clean up downloaded photos
            for clip in self.audio_clips:
                if "photo_data" in clip and "photo_path" in clip["photo_data"]:
                    if os.path.exists(clip["photo_data"]["photo_path"]):
                        os.remove(clip["photo_data"]["photo_path"])
            
            # Clean up subtitles file
            if hasattr(self, "subtitles_path") and os.path.exists(self.subtitles_path):
                os.remove(self.subtitles_path)
                
            logger.info("Temporary files cleaned up successfully")
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {e}")