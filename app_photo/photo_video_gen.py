from typing import Dict, List, Optional, Any, Literal
from pathlib import Path
import os
import tempfile
import ffmpeg
from PIL import Image
from loguru import logger
from pydantic import BaseModel
import time
import shutil
import multiprocessing

class PhotoAnimationConfig(BaseModel):
    """Configuration for photo animations."""
    style: str = "kenburns"  # kenburns, zoom, pan, static
    duration: float = 5.0
    transition: str = "fade"
    transition_duration: float = 1.0

class PhotoVideoGenerator:
    def __init__(self, base_class):
        """
        Initialize the Photo Video Generator.
        
        Args:
            base_class: The parent engine class
        """
        self.base_class = base_class
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temp directory: {self.temp_dir}")
    
    def _apply_kenburns_effect(self, input_path, output_path, duration=5):
        """
        Apply Ken Burns effect to a photo.
        
        Args:
            input_path: Path to input image
            output_path: Path to output video
            duration: Duration of the effect in seconds
        """
        try:
            # First verify the input image exists and can be opened
            if not os.path.exists(input_path):
                logger.error(f"Input image does not exist: {input_path}")
                raise FileNotFoundError(f"Input image not found: {input_path}")
                
            # Get image dimensions
            img = Image.open(input_path)
            width, height = img.size
            img.close()  # Close image after reading dimensions
            
            # Ensure width and height are even (required by some codecs)
            width = width if width % 2 == 0 else width - 1
            height = height if height % 2 == 0 else height - 1
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Determine zoom direction randomly (in or out)
            import random
            zoom_in = random.choice([True, False])
            
            if zoom_in:
                # Zoom in effect
                scale_start = 1.0
                scale_end = 1.3
            else:
                # Zoom out effect
                scale_start = 1.3
                scale_end = 1.0
                
            # Determine pan direction randomly
            pan_x = random.uniform(-0.1, 0.1)
            pan_y = random.uniform(-0.1, 0.1)
            
            # Apply zoom and pan effect with ffmpeg
            logger.debug(f"Running ffmpeg kenburns effect on {input_path}")
            
            try:
                stream = (
                    ffmpeg
                    .input(input_path, loop=1, t=duration)
                    .filter('scale', width, height)
                    .filter(
                        'zoompan',
                        z=f'if(lte(on,1),{scale_start},{scale_start}+((on-1)/({duration*25}-1))*({scale_end}-{scale_start}))', 
                        x=f'iw/2-(iw/zoom/2)+{pan_x}*iw',
                        y=f'ih/2-(ih/zoom/2)+{pan_y}*ih',
                        d=duration*25,
                        s=f'{width}x{height}'
                    )
                    .output(output_path, vcodec='libx264', pix_fmt='yuv420p')
                    .global_args('-loglevel', 'warning')  # Add more logging
                    .overwrite_output()
                    .run(capture_stderr=True)  # Capture stderr for debugging
                )
                
                return output_path
            except ffmpeg.Error as e:
                # Log detailed FFmpeg error
                stderr = e.stderr.decode('utf-8') if e.stderr else "No error details"
                logger.error(f"FFmpeg error: {stderr}")
                raise Exception(f"FFmpeg error: {stderr}")
                
        except Exception as e:
            logger.error(f"Error applying kenburns effect: {str(e)}")
            # Return a path to a default image or raise the exception
            raise
    
    def _apply_pan_effect(self, input_path, output_path, duration=5):
        """Apply panning effect to a photo."""
        # Get image dimensions
        img = Image.open(input_path)
        width, height = img.size
        
        # Choose a random pan direction
        import random
        directions = ['left', 'right', 'up', 'down']
        direction = random.choice(directions)
        
        # Configure pan parameters based on direction
        if direction == 'left':
            x_expr = f'if(lte(on,1),0,(on-1)/({duration*25}-1)*(iw*0.2))'
            y_expr = '0'
        elif direction == 'right':
            x_expr = f'if(lte(on,1),iw*0.2,(1-(on-1)/({duration*25}-1))*(iw*0.2))'
            y_expr = '0'
        elif direction == 'up':
            x_expr = '0'
            y_expr = f'if(lte(on,1),0,(on-1)/({duration*25}-1)*(ih*0.2))'
        else:  # down
            x_expr = '0'
            y_expr = f'if(lte(on,1),ih*0.2,(1-(on-1)/({duration*25}-1))*(ih*0.2))'
        
        # Apply pan effect
        stream = (
            ffmpeg
            .input(input_path, loop=1, t=duration)
            .filter('scale', width, height)
            .filter(
                'crop',
                'iw*0.8', 'ih*0.8',  # crop to 80% of original size
                x_expr, y_expr
            )
            .filter('scale', width, height)  # scale back to original size
            .output(output_path, vcodec='libx264', pix_fmt='yuv420p')
            .overwrite_output()
            .run(quiet=False)
        )
        
        return output_path
    
    def _apply_simple_effect(self, input_path, output_path, duration=5):
        """Create a video from a static photo."""
        stream = (
            ffmpeg
            .input(input_path, loop=1, t=duration)
            .output(output_path, vcodec='libx264', pix_fmt='yuv420p')
            .overwrite_output()
            .run(quiet=False)
        )
        
        return output_path
    
    def _create_photo_video_segment(self, photo_path, output_path, animation="kenburns", duration=5):
        """
        Create a video segment from a photo with animation.
        
        Args:
            photo_path: Path to the input photo
            output_path: Path to save the video segment
            animation: Animation style (kenburns, pan, static)
            duration: Duration of the segment in seconds
            
        Returns:
            Path to the created video segment
        """
        logger.info(f"Creating video segment from photo with {animation} animation")
        
        try:
            if animation == "kenburns":
                return self._apply_kenburns_effect(photo_path, output_path, duration)
            elif animation == "pan":
                return self._apply_pan_effect(photo_path, output_path, duration)
            else:  # static or fallback
                return self._apply_simple_effect(photo_path, output_path, duration)
        except Exception as e:
            # If any animation fails, fall back to simple effect
            logger.error(f"Animation '{animation}' failed: {e}. Falling back to static photo.")
            return self._apply_simple_effect(photo_path, output_path, duration)
    
    def _apply_transition(self, clip1, clip2, output_path, transition="fade", duration=1.0):
        """Apply transition between two video clips."""
        try:
            if transition == "fade":
                # Create a crossfade transition
                clip1_stream = ffmpeg.input(clip1)
                clip2_stream = ffmpeg.input(clip2)
                
                # Get durations of clips
                clip1_info = ffmpeg.probe(clip1)
                clip1_duration = float(clip1_info['format']['duration'])
                
                # Create transition with xfade filter
                # FIXED: Corrected xfade filter syntax
                stream = ffmpeg.concat(
                    clip1_stream.video.filter('setpts', 'PTS-STARTPTS').filter('fade', type='out', start_time=clip1_duration-duration, duration=duration),
                    clip2_stream.video.filter('setpts', 'PTS-STARTPTS').filter('fade', type='in', duration=duration),
                    v=1, a=0
                )
                
                # Output the result
                ffmpeg.output(stream, output_path).run(overwrite_output=True, quiet=False)
                
                return output_path
            else:
                # For other transitions, just concatenate
                ffmpeg.concat(
                    ffmpeg.input(clip1).video,
                    ffmpeg.input(clip2).video,
                    v=1, a=0
                ).output(output_path).run(overwrite_output=True, quiet=False)
                
                return output_path
        except ffmpeg.Error as e:
            logger.error(f"FFmpeg error in transition: {e.stderr.decode('utf-8') if e.stderr else 'Unknown error'}")
            # Fall back to simple concatenation
            return self._simple_concat(clip1, clip2, output_path)
    
    def _simple_concat(self, clip1, clip2, output_path):
        """Simple concatenation fallback when transitions fail."""
        try:
            # Create a concat file
            concat_file = os.path.join(self.temp_dir, "simple_concat.txt")
            with open(concat_file, 'w') as f:
                f.write(f"file '{clip1}'\n")
                f.write(f"file '{clip2}'\n")
            
            # Use concat demuxer
            ffmpeg.input(concat_file, format='concat', safe=0).output(
                output_path, c='copy'
            ).run(overwrite_output=True, quiet=False)
            
            return output_path
        except Exception as e:
            logger.error(f"Simple concat failed: {e}")
            # Just return the first clip as fallback
            return clip1
    
    def _add_audio_to_video(self, video_path, audio_path, output_path):
        """
        Add audio to a video.
        
        Args:
            video_path: Path to the video file
            audio_path: Path to the audio file
            output_path: Path to save the result
            
        Returns:
            Path to the video with audio
        """
        # Get the durations
        video_info = ffmpeg.probe(video_path)
        video_duration = float(video_info['format']['duration'])
        
        audio_info = ffmpeg.probe(audio_path)
        audio_duration = float(audio_info['format']['duration'])
        
        # If video is shorter than audio, extend it
        if video_duration < audio_duration:
            # Create a temporary file for extended video
            temp_video = os.path.join(self.temp_dir, "extended_video.mp4")
            
            # Get last frame and append it to extend the video
            stream = (
                ffmpeg
                .input(video_path)
                .filter('tpad', stop_mode='clone', stop_duration=audio_duration-video_duration)
                .output(temp_video)
                .overwrite_output()
                .run(quiet=False)
            )
            
            video_path = temp_video
        
        # Add audio to video
        stream = (
            ffmpeg
            .input(video_path)
            .input(audio_path)
            .output(output_path, vcodec='copy', acodec='aac')
            .overwrite_output()
            .run(quiet=False)
        )
        
        return output_path
    
    def _apply_subtitles(self, video_path, subtitles_path, output_path):
        """More reliable subtitle application method"""
        # First check if subtitles file exists and has content
        if not os.path.exists(subtitles_path) or os.path.getsize(subtitles_path) == 0:
            logger.warning(f"Empty or missing subtitles file: {subtitles_path}. Skipping subtitles.")
            # Just copy the video if no valid subtitles
            shutil.copy(video_path, output_path)
            return output_path
        
        # Fix potential path issues by copying subtitles to temp dir with simple name
        temp_subs = os.path.join(self.temp_dir, "temp_subs.srt")
        shutil.copy(subtitles_path, temp_subs)
        
        # Escape special characters in path for subtitles filter
        escaped_subs = temp_subs.replace(":", "\\:").replace("'", "\\'")
        
        try:
            # Build FFmpeg command
            stream = (
                ffmpeg
                .input(video_path)
                .filter('subtitles', escaped_subs)
                .output(output_path)
                .overwrite_output()
            )
            
            # Use timeout function
            return self._run_ffmpeg_command(stream, "adding subtitles")
        except Exception as e:
            logger.error(f"Failed to add subtitles: {e}")
            # Fall back to video without subtitles if this fails
            logger.warning("Using video without subtitles as fallback")
            shutil.copy(video_path, output_path)
            return output_path
    
    async def generate_video(self, 
                     audio_clips: List[Dict], 
                     subtitles_path: str, 
                     aspect_ratio: str = "16:9",
                     animation_style: str = "kenburns",
                     transition_style: str = "fade",
                     background_music_path: str = None) -> str:
        """
        Generate a video from photos and audio clips.
        
        Args:
            audio_clips: List of dictionaries with audio and photo data
            subtitles_path: Path to subtitles file
            aspect_ratio: Aspect ratio for the video
            animation_style: Animation style for photos
            transition_style: Transition style between segments
            background_music_path: Optional path to background music
            
        Returns:
            Path to the final generated video
        """
        # Add at the beginning of generate_video:
        import shutil
        import os
        # Use the output directory as reference or fall back to current directory
        disk_space_path = os.environ.get("PHOTO_OUTPUT_DIR", "./outputs/photos")
        os.makedirs(os.path.dirname(disk_space_path), exist_ok=True)  # Ensure directory exists
        disk_space = shutil.disk_usage(os.path.abspath(disk_space_path))
        
        free_space_gb = disk_space.free / (1024**3)
        logger.info(f"Available disk space: {free_space_gb:.2f} GB")
        if free_space_gb < 1.0:
            logger.warning("Low disk space! This may cause the process to hang.")
        
        logger.info("Starting video segment generation...")
        logger.info(f"Generating video from {len(audio_clips)} photo segments")
        
        # Create individual video segments
        video_segments = []
        
        for i, clip in enumerate(audio_clips):
            logger.info(f"Processing segment {i+1}/{len(audio_clips)}...")
            photo_path = clip["photo_data"]["photo_path"]
            audio_path = clip["audio_path"]
            
            # Get audio duration using ffmpeg probe
            audio_info = ffmpeg.probe(audio_path)
            audio_duration = float(audio_info['format']['duration'])
            
            # Use audio duration for the photo animation (minimum 3 seconds for very short clips)
            actual_duration = max(audio_duration, 3.0)
            
            # Create segment output path
            segment_path = os.path.join(self.temp_dir, f"segment_{i}.mp4")
            
            # Create video from photo
            video_only_path = os.path.join(self.temp_dir, f"video_only_{i}.mp4")
            self._create_photo_video_segment(
                photo_path=photo_path,
                output_path=video_only_path,
                animation=animation_style,
                duration=actual_duration  # Match the audio duration
            )
            
            # Add audio to segment
            self._add_audio_to_video(
                video_path=video_only_path,
                audio_path=audio_path,
                output_path=segment_path
            )
            
            video_segments.append(segment_path)
            logger.info(f"Completed segment {i+1}/{len(audio_clips)}")
        
        # Combine segments with transitions
        combined_segments = []
        
        if len(video_segments) == 1:
            # Only one segment, no transitions needed
            combined_segments = video_segments
        else:
            # Apply transitions between segments
            for i in range(len(video_segments) - 1):
                output_path = os.path.join(self.temp_dir, f"transition_{i}.mp4")
                
                self._apply_transition(
                    clip1=video_segments[i],
                    clip2=video_segments[i+1],
                    output_path=output_path,
                    transition=transition_style
                )
                
                combined_segments.append(output_path)
            
            # Add the last segment
            combined_segments.append(video_segments[-1])
        
        # Create a concatenation file for ffmpeg
        concat_file = os.path.join(self.temp_dir, "concat.txt")
        with open(concat_file, 'w') as f:
            for segment in combined_segments:
                f.write(f"file '{segment}'\n")
        
        # Concatenate all segments
        merged_video = os.path.join(self.temp_dir, "merged_video.mp4")
        
        ffmpeg.input(concat_file, format='concat', safe=0).output(
            merged_video, c='copy'
        ).run(overwrite_output=True)
        
        # Add subtitles
        final_video_with_subs = os.path.join(self.temp_dir, "final_with_subs.mp4")
        self._apply_subtitles(
            video_path=merged_video,
            subtitles_path=subtitles_path,
            output_path=final_video_with_subs
        )
        
        # Add background music if provided
        if background_music_path:
            final_output = os.path.join(
                os.environ.get("PHOTO_OUTPUT_DIR", "./outputs/photos"), 
                f"photo_reel_{int(time.time())}.mp4"
            )
            
            # Ensure output directory exists
            output_dir = os.path.dirname(final_output)
            os.makedirs(output_dir, exist_ok=True)
            
            try:
                # Mix original audio with background music
                stream = (
                    ffmpeg
                    .input(final_video_with_subs)
                    .input(background_music_path)
                    .filter_complex('[0:a][1:a]amix=inputs=2:duration=longest:dropout_transition=2[aout]')
                    .global_args('-map', '0:v', '-map', '[aout]')
                    .output(final_output)
                    .overwrite_output()
                )
                self._run_ffmpeg_command(stream, "adding background music")
            except Exception as e:
                logger.error(f"Failed to add background music: {e}")
                # Fall back to copying without background music
                shutil.copy(final_video_with_subs, final_output)
        else:
            # Copy the file to final location
            final_output = os.path.join(
                os.environ.get("PHOTO_OUTPUT_DIR", "./outputs/photos"), 
                f"photo_reel_{int(time.time())}.mp4"
            )
            
            # Ensure output directory exists
            output_dir = os.path.dirname(final_output)
            os.makedirs(output_dir, exist_ok=True)
            
            # Copy the file
            shutil.copy(final_video_with_subs, final_output)

        # Cleanup temp files to free space
        try:
            for file_path in video_segments + [merged_video, final_video_with_subs, concat_file]:
                if os.path.exists(file_path):
                    os.remove(file_path)
            logger.debug("Cleaned up temporary video files")
        except Exception as e:
            logger.warning(f"Error cleaning up temp files: {e}")
        
        logger.info(f"Video generation complete. Output: {final_output}")
        return final_output

    def _run_ffmpeg_command(self, stream, description="FFmpeg operation"):
        """Run FFmpeg command with consistent error handling"""
        logger.debug(f"Running FFmpeg: {description}")
        try:
            return run_with_timeout(stream, timeout=300)
        except Exception as e:
            logger.error(f"FFmpeg {description} failed: {str(e)}")
            raise RuntimeError(f"FFmpeg operation failed: {str(e)}")

def run_with_timeout(stream, timeout=300):
    """Run ffmpeg command with a reliable timeout limit"""
    import subprocess
    import threading
    
    # Get the command that would be run
    cmd = stream.compile()
    logger.debug(f"Running FFmpeg command: {' '.join(cmd)}")
    
    # Create process
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    # Function to kill process if it runs too long
    def kill_process():
        if process.poll() is None:  # If process is still running
            logger.warning(f"FFmpeg process timed out after {timeout}s, killing it")
            process.kill()
    
    # Start timer
    timer = threading.Timer(timeout, kill_process)
    timer.start()
    
    try:
        # Wait for process to complete
        stdout, stderr = process.communicate()
        
        # Check if successful
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {stderr}")
            raise subprocess.CalledProcessError(process.returncode, cmd, stderr)
            
        return stdout
    finally:
        timer.cancel()  # Ensure timer is cancelled

def run_ffmpeg_safely(stream, description="FFmpeg operation", timeout=300):
    """Safe wrapper for FFmpeg operations with timeout"""
    import time
    start_time = time.time()
    logger.info(f"Starting FFmpeg operation: {description}")
    
    try:
        # Use the existing timeout function
        result = run_with_timeout(stream, timeout=timeout)
        elapsed = time.time() - start_time
        logger.info(f"Completed FFmpeg {description} in {elapsed:.1f}s")
        return result
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"FFmpeg {description} failed after {elapsed:.1f}s: {str(e)}")
        raise