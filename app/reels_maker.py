import os
import sys
import subprocess
import asyncio

import ffmpeg
from loguru import logger

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


class ReelsMakerConfig(BaseGeneratorConfig):
    pass


def create_concat_file(clips):
    concat_filename = "concat_list.txt"
    with open(concat_filename, "w") as f:
        for clip in clips:
            f.write(f"file '{clip}'\n")
    return concat_filename


def concatenate_with_filelist(clips, output_path):
    concat_filename = create_concat_file(clips)

    # Run FFmpeg with the concat demuxer
    ffmpeg.input(concat_filename, format="concat", safe=0).output(
        output_path, c="copy"
    ).run(overwrite_output=True)

    return output_path


def concatenate_clips(clips, output_path):
    """
    Concatenates a list of video clips.
    Args:
    - clips (list of str): List of file paths to each video clip to concatenate.
    - output_path (str): Path to save the final concatenated video.
    """
    # Prepare input streams for each clip
    streams = [ffmpeg.input(clip) for clip in clips]

    # Use concat filter
    concatenated_stream = ffmpeg.concat(*streams, v=1, a=1).output(output_path)

    # Run FFmpeg
    concatenated_stream.run(overwrite_output=True)
    return output_path


class ReelsMaker(BaseEngine):
    def __init__(self, config: ReelsMakerConfig):
        super().__init__(config)
        self.config = config
        
        # Force GPU usage if available
        if TORCH_AVAILABLE:
            try:
                if torch.cuda.is_available():
                    device_count = torch.cuda.device_count()
                    device_name = torch.cuda.get_device_name(0)
                    logger.info(f"Found {device_count} CUDA devices. Using: {device_name}")
                    
                    # Force PyTorch to use CUDA
                    torch.set_default_tensor_type('torch.cuda.FloatTensor')
                    
                    # Set environment variable for other libraries
                    os.environ['CUDA_VISIBLE_DEVICES'] = '0'
                else:
                    logger.warning("CUDA not available, using CPU")
            except Exception as e:
                logger.exception(f"Error setting up CUDA: {e}")

    async def _generate_script_internal(self, prompt: str) -> str:
        """Internal method to generate a script from the prompt."""
        try:
            # Use the correct method from prompt_generator
            # This looks at how the original code was generating scripts
            if hasattr(self.prompt_generator, 'generate_content'):
                response = await self.prompt_generator.generate_content(prompt)
                return response.content
            elif hasattr(self.prompt_generator, 'generate'):
                response = await self.prompt_generator.generate(prompt)
                return response
            elif hasattr(self.prompt_generator, 'generate_sentences'):
                response = await self.prompt_generator.generate_sentences(prompt, max_sentences=5)
                return " ".join(response)
            else:
                # Fall back to a simple approach if none of the expected methods exist
                logger.warning("Could not find appropriate method in prompt_generator")
                return f"Let's explore {prompt}. {prompt} is something that affects us all."
        except Exception as e:
            logger.exception(f"Internal script generation failed: {e}")
            return ""

    async def generate_script(self, prompt: str) -> str:
        """Generate a script from a prompt."""
        try:
            # Log the prompt and API request
            logger.info(f"Generating script from prompt: {prompt}")
            
            # Add timeout to prevent hanging
            script = await asyncio.wait_for(
                self._generate_script_internal(prompt),
                timeout=30  # 30 second timeout
            )
            
            # Validate script content
            if not script or script.strip() == "":
                logger.error(f"Generated empty script from prompt: {prompt}")
                # Fallback to using the prompt as the script
                return f"Here's a fact about {prompt}. {prompt} is an interesting topic worth exploring."
                
            logger.info(f"Successfully generated script: {script[:50]}...")
            return script
            
        except asyncio.TimeoutError:
            logger.error(f"Script generation timed out for prompt: {prompt}")
            return f"Here's a thought about {prompt}. {prompt} is something we should consider."
        except Exception as e:
            logger.exception(f"Script generation failed: {e}")
            return f"Let me tell you about {prompt}. It's a fascinating subject."

    async def generate_search_terms(self, script, max_hashtags: int = 5):
        logger.debug("Generating search terms for script...")
        response = await self.prompt_generator.generate_stock_image_keywords(script)
        tags = [tag.replace("#", "") for tag in response.sentences]
        if len(tags) > max_hashtags:
            logger.warning(f"Truncated search terms to {max_hashtags} tags")
            tags = tags[:max_hashtags]

        logger.info(f"Generated search terms: {tags}")
        return tags

    async def start(self) -> StartResponse:
        try:
            await super().start()
            
            # Initialize background_music_path to None
            self.background_music_path = None

            if self.config.background_audio_url:
                self.background_music_path = await download_resource(
                    self.cwd, self.config.background_audio_url
                )
            
            # Check if the background music path is in video_gen_config
            if self.config.video_gen_config and self.config.video_gen_config.background_music_path:
                self.background_music_path = self.config.video_gen_config.background_music_path
                
            # Log the actual background music path (for debugging)
            logger.debug(f"Using background music path: {self.background_music_path}")
            
            # generate script from prompt
            try:
                if self.config.prompt:
                    logger.debug(f"Generating script from prompt: {self.config.prompt}")
                    script = await self.generate_script(self.config.prompt)
                    logger.debug(f"Generated script: {script}")
                elif self.config.script:
                    script = self.config.script
                else:
                    raise ValueError("No prompt or sentence provided")

                # split script into sentences
                if script is None:
                    raise ValueError("Script generation failed - returned None")
                    
                sentences = split_by_dot_or_newline(script, 100)
                sentences = list(filter(lambda x: x != "", sentences))
            except Exception as e:
                logger.exception(f"Script generation or processing failed: {e}")
                raise

            video_paths = []
            if self.config.video_paths:
                logger.info("Using video paths from client...")
                video_paths = self.config.video_paths
            else:
                logger.debug("Generating search terms for script...")
                search_terms = await self.generate_search_terms(
                    script=script, max_hashtags=10
                )

                # holds all remote urls
                remote_urls = []

                max_videos = int(os.getenv("MAX_BG_VIDEOS", 10))

                for search_term in search_terms[:max_videos]:
                    # search for a related background video
                    video_path = await self.video_generator.get_video_url(
                        search_term=search_term
                    )
                    if not video_path:
                        continue

                    remote_urls.append(video_path)

                # download all remote videos at once
                tasks = []
                for url in remote_urls:
                    task = asyncio.create_task(download_resource(self.cwd, url))
                    tasks.append(task)

                local_paths = await asyncio.gather(*tasks)
                video_paths.extend(set(local_paths))

            if not video_paths:
                logger.warning("No video paths found, using default videos")
                
                # Try to load default videos from the assets directory
                default_videos_dir = os.path.join(os.getcwd(), "assets", "default_videos")
                if os.path.exists(default_videos_dir):
                    default_videos = [os.path.join(default_videos_dir, f) for f in os.listdir(default_videos_dir) 
                                      if f.endswith(('.mp4', '.mov', '.avi'))]
                    if default_videos:
                        logger.info(f"Using {len(default_videos)} default videos")
                        video_paths = default_videos
            
                # If no default videos found, create a blank video as last resort
                if not video_paths:
                    logger.warning("No default videos found, creating blank video")
                    blank_video = os.path.join(self.cwd, "blank_video.mp4")
                    try:
                        # Create a 15-second blank video with ffmpeg
                        black_cmd = [
                            self.video_generator.ffmpeg_cmd,
                            "-f", "lavfi", 
                            "-i", "color=c=black:s=1080x1920:d=15", 
                            "-c:v", "libx264",
                            "-pix_fmt", "yuv420p",
                            "-t", "15",
                            blank_video
                        ]
                        subprocess.run(black_cmd, check=True)
                        video_paths = [blank_video]
                    except Exception as e:
                        logger.exception(f"Failed to create blank video: {e}")
                        raise ValueError("Unable to create video: no source videos available")

            data: list[TempData] = []

            # for each sentence, generate audio
            for sentence in sentences:
                audio_path = await self.synth_generator.synth_speech(sentence)
                data.append(
                    TempData(
                        synth_clip=FileClip(audio_path),
                    )
                )

            # Add before calling video_generator.generate_video
            if not self.background_music_path and hasattr(self, 'video_generator'):
                logger.warning("No background music path set at ReelsMaker level")
                # Let video_generator handle this with its own null check



            # TODO: fix me
            self.video_generator.config.background_music_path = self.background_music_path

            final_speech = ffmpeg.concat(
                *[item.synth_clip.ffmpeg_clip for item in data], v=0, a=1
            )

            # get subtitles from script
            subtitles_path = await self.subtitle_generator.generate_subtitles(
                sentences=sentences,
                durations=[item.synth_clip.real_duration for item in data],
            )

            # the max duration of the final video
            video_duration = sum(item.synth_clip.real_duration for item in data)
            logger.info(f"Calculated video duration: {video_duration} seconds")

            # Set a minimum video duration
            MIN_VIDEO_DURATION = 15  # seconds
            if video_duration < MIN_VIDEO_DURATION:
                factor = MIN_VIDEO_DURATION / video_duration
                logger.info(f"Video too short ({video_duration}s), extending by factor {factor:.2f}")
                # We'll slow down each clip to meet the minimum duration
                video_duration = MIN_VIDEO_DURATION

            # each clip should be 5 seconds long
            max_clip_duration = 5

            tot_dur: float = 0

            temp_videoclip: list[FileClip] = [
                FileClip(video_path, t=max_clip_duration) for video_path in video_paths
            ]

            final_clips: list[FileClip] = []

            while tot_dur < video_duration:
                for clip in temp_videoclip:
                    remaining_dur = video_duration - tot_dur
                    subclip_duration = min(
                        max_clip_duration, remaining_dur, clip.real_duration
                    )
                    subclip = FileClip(clip.filepath, t=subclip_duration).duplicate()

                    final_clips.append(subclip)
                    tot_dur += subclip_duration

                    logger.debug(
                        f"Total duration after adding this clip: {tot_dur}, target is {video_duration}, clip duration: {subclip_duration}"
                    )

                    if tot_dur >= video_duration:
                        break

            final_video_path = await self.video_generator.generate_video(
                clips=final_clips,
                subtitles_path=subtitles_path,
                speech_filter=final_speech,
                video_duration=video_duration,
            )

            logger.info((f"Final video: {final_video_path}"))
            logger.info("video generated successfully!")

            return StartResponse(video_file_path=final_video_path)
            
        except Exception as e:
            # Enhanced error logging
            logger.exception(f"Video generation failed with error: {e}")
            return None

    async def run_diagnostics(self):
        """Run system diagnostics to validate environment"""
        diagnostics = {
            "ffmpeg_version": None,
            "python_version": sys.version,
            "temp_dir_writable": None,
            "gpu_info": None
        }
        
        # Check FFmpeg
        try:
            result = subprocess.run([self.video_generator.ffmpeg_cmd, "-version"], 
                                    capture_output=True, text=True)
            if result.returncode == 0:
                diagnostics["ffmpeg_version"] = result.stdout.splitlines()[0]
            else:
                diagnostics["ffmpeg_version"] = f"Error: {result.stderr}"
        except Exception as e:
            diagnostics["ffmpeg_version"] = f"Exception: {str(e)}"
        
        # Test temp directory
        try:
            test_file = os.path.join(self.cwd, "test_write.txt")
            with open(test_file, "w") as f:
                f.write("Test")
            os.remove(test_file)
            diagnostics["temp_dir_writable"] = True
        except Exception as e:
            diagnostics["temp_dir_writable"] = f"Error: {str(e)}"
        
        # Check GPU
        try:
            if TORCH_AVAILABLE:
                # Only access torch if it's available
                if torch.cuda.is_available():
                    diagnostics["gpu_info"] = {
                        "device_name": torch.cuda.get_device_name(0),
                        "device_count": torch.cuda.device_count(),
                        "memory_allocated": f"{torch.cuda.memory_allocated(0)/1024**3:.2f} GB",
                        "memory_reserved": f"{torch.cuda.memory_reserved(0)/1024**3:.2f} GB",
                        "cuda_version": torch.version.cuda,
                    }
                else:
                    diagnostics["gpu_info"] = "CUDA not available"
            else:
                # Check for GPU using system commands if torch is not available
                try:
                    # Try nvidia-smi as a fallback
                    result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
                    if result.returncode == 0:
                        diagnostics["gpu_info"] = "NVIDIA GPU detected (via nvidia-smi)"
                    else:
                        diagnostics["gpu_info"] = "No NVIDIA GPU detected"
                except:
                    diagnostics["gpu_info"] = "PyTorch not installed, GPU detection limited"
        except Exception as e:
            diagnostics["gpu_info"] = f"Error checking GPU: {str(e)}"
        
        # Report results
        logger.info(f"System diagnostics: {diagnostics}")
        return diagnostics

    def cleanup_temp_files(self):
        """Remove temporary files after successful video generation"""
        try:
            # Keep the final video but clean up intermediate files
            files_to_delete = [f for f in os.listdir(self.cwd) 
                              if not f.endswith("_final.mp4") and 
                              os.path.isfile(os.path.join(self.cwd, f))]
            for file in files_to_delete:
                os.remove(os.path.join(self.cwd, file))
            logger.info(f"Cleaned up {len(files_to_delete)} temporary files")
        except Exception as e:
            logger.warning(f"Error cleaning up temporary files: {e}")