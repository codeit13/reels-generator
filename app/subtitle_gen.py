import os
from datetime import timedelta

import srt_equalizer
from loguru import logger
from pydantic import BaseModel

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.base import BaseEngine


class SubtitleConfig(BaseModel):
    cwd: str
    job_id: str
    # Default is now loaded from settings via BaseGeneratorConfig,
    # but keep a fallback default here just in case.
    max_chars: int = 35  # Keep a fallback default


class SubtitleGenerator:
    def __init__(self, base_class: "BaseEngine", config: Optional[SubtitleConfig] = None):  # Make config optional for compatibility
        self.base_class = base_class
        # Use the passed config object if provided, otherwise create a default one
        if config:
            self.config = config
        else:
            # Fallback if config is not passed (e.g., from BaseEngine init)
            self.config = SubtitleConfig(
                cwd=base_class.cwd,
                job_id=base_class.config.job_id,
                # max_chars will use the default from SubtitleConfig definition
            )
        logger.info(f"SubtitleGenerator initialized with max_chars: {self.config.max_chars}")

    async def wordify(self, srt_path: str, max_chars: int) -> None:  # Keep max_chars argument here
        """Wordify the srt file, each line is a word

        Example:
        --------------
        1
        00:00:00,000 --> 00:00:00,333
        Imagine

        2
        00:00:00,333 --> 00:00:00,762
        waking up

        3
        00:00:00,762 --> 00:00:01,143
        each day
        ----------------
        """
        logger.debug(f"Running srt_equalizer with max_chars: {max_chars}")
        srt_equalizer.equalize_srt_file(srt_path, srt_path, max_chars)

    async def generate_subtitles(
        self,
        sentences: list[str],
        durations: list[float],
    ) -> str:
        logger.info("Generating subtitles...")
        logger.debug(f"Starting subtitle generation with {len(sentences)} sentences")

        if hasattr(self.base_class.config.video_gen_config, 'font_name'):
            font_name = self.base_class.config.video_gen_config.font_name
            stroke_width = self.base_class.config.video_gen_config.stroke_width
            font_name, stroke_width = validate_font_params(font_name, stroke_width)
            self.base_class.config.video_gen_config.font_name = font_name
            self.base_class.config.video_gen_config.stroke_width = stroke_width

        subtitles_path = os.path.join(self.config.cwd, f"{self.config.job_id}.srt")

        subtitles = await self.locally_generate_subtitles(
            sentences=sentences, durations=durations
        )
        with open(subtitles_path, "w+") as file:
            file.write(subtitles)

        await self.wordify(srt_path=subtitles_path, max_chars=self.config.max_chars)

        self.debug_subtitle_file(subtitles_path)
        logger.debug(f"Writing subtitles to {subtitles_path}")
        return subtitles_path

    async def locally_generate_subtitles(
        self, sentences: list[str], durations: list[float]
    ) -> str:
        logger.debug("using local subtitle generation...")

        def convert_to_srt_time_format(total_seconds):
            # Convert total seconds to the SRT time format: HH:MM:SS,mmm
            if total_seconds == 0:
                return "0:00:00,0"
            return str(timedelta(seconds=total_seconds)).rstrip("0").replace(".", ",")

        start_time = 0
        subtitles = []

        for i, (sentence, duration) in enumerate(zip(sentences, durations), start=1):
            end_time = start_time + duration

            # Format: subtitle index, start time --> end time, sentence
            subtitle_entry = f"{i}\n{convert_to_srt_time_format(start_time)} --> {convert_to_srt_time_format(end_time)}\n{sentence}\n"
            subtitles.append(subtitle_entry)

            start_time += duration  # Update start time for the next subtitle

        logger.debug(f"Generated {len(subtitles)} subtitle entries")
        return "\n".join(subtitles)

    def debug_subtitle_file(self, subtitle_path):
        """Debug the subtitle file content"""
        try:
            if os.path.exists(subtitle_path):
                with open(subtitle_path, 'r') as f:
                    content = f.read(500)  # Read first 500 chars
                    logger.debug(f"SRT file preview:\n{content}\n...")
                    logger.debug(f"SRT file size: {os.path.getsize(subtitle_path)} bytes")
            else:
                logger.error(f"Subtitle file not found: {subtitle_path}")
        except Exception as e:
            logger.error(f"Error reading subtitle file: {e}")


def validate_font_params(font_name, stroke_width):
    """Validate font parameters to prevent crashes."""
    valid_fonts = ["Arial", "Luckiest Guy", "Roboto"]
    if not font_name or font_name not in valid_fonts:
        logger.warning(f"Invalid font {font_name}, falling back to default")
        font_name = "Luckiest Guy"  # Default fallback

    try:
        stroke_width = int(stroke_width)
        if stroke_width < 0 or stroke_width > 5:
            logger.warning(f"Invalid stroke width {stroke_width}, using default")
            stroke_width = 2
    except (ValueError, TypeError):
        logger.warning(f"Invalid stroke width value, using default")
        stroke_width = 2

    logger.debug(f"UI stroke_width value: {stroke_width}")
    return font_name, stroke_width