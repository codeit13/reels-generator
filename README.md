# ReelsMaker

ReelsMaker is a powerful application for generating short-form video content (reels) by combining text, speech, and visual elements. It leverages AI technologies for script generation, text-to-speech conversion, image/video selection, and subtitle creation to produce engaging video content.

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Core Components](#core-components)
  - [Main Application (reelsmaker.py)](#main-application-reelsmakerpy)
  - [Reels Generation Engine (reels_maker.py)](#reels-generation-engine-reels_makerpy)
  - [Video Generation (video_gen.py)](#video-generation-video_genpy)
  - [Speech Synthesis (synth_gen.py)](#speech-synthesis-synth_genpy)
  - [Subtitle Generation (subtitle_gen.py)](#subtitle-generation-subtitle_genpy)
  - [Prompt Generation (prompt_gen.py)](#prompt-generation-prompt_genpy)
  - [Image Generation (image_gen.py)](#image-generation-image_genpy)
  - [Video Sources](#video-sources)
  - [Configuration (config.py)](#configuration-configpy)
- [Workflow](#workflow)
- [Setup and Installation](#setup-and-installation)

## Overview

ReelsMaker is a Streamlit-based application that allows users to generate short-form videos (reels) for platforms like Instagram, TikTok, and YouTube Shorts. The application provides a user-friendly interface for inputting prompts or scripts, selecting voice options, and customizing video appearance. It then orchestrates multiple AI services to generate a complete video with synchronized speech, visuals, and subtitles.

## Project Structure

The project follows a modular architecture with specialized components for each part of the video generation process:

```
reelsmaker/
├── reelsmaker.py           # Main Streamlit application entry point
├── app/
│   ├── base.py             # Base classes and common functionality
│   ├── config.py           # Configuration settings and environment variables
│   ├── effects.py          # Video effects (zoom, transitions)
│   ├── image_gen.py        # AI image generation
│   ├── kokoro_service.py   # Kokoro voice service integration
│   ├── pexel.py            # Pexels stock video API integration
│   ├── prompt_gen.py       # AI prompt generation for scripts and keywords
│   ├── reels_maker.py      # Core reels generation engine
│   ├── sakugabooru.py      # Anime video source integration
│   ├── subtitle_gen.py     # Subtitle generation and formatting
│   ├── synth_gen.py        # Text-to-speech synthesis
│   ├── tiktokvoice.py      # TikTok voice integration
│   ├── video_gen.py        # Video processing and composition
│   └── utils/              # Utility functions and helpers
├── cache/                  # Caching for assets (videos, images, speech)
├── data/                   # Static data files
└── tmp/                    # Temporary files during processing
```

## Core Components

### Main Application (reelsmaker.py)

The main Streamlit application that provides the user interface and orchestrates the video generation process.

**Key Functions:**
- `main()`: The main Streamlit application entry point that creates the UI and handles user interactions
- `create_timer()`: Creates a JavaScript timer to track video generation progress
- `clear_queue()`: Clears pending jobs from the queue
- `validate_audio_file()`: Validates uploaded audio files
- `add_log_diagnostics()`: Adds diagnostic information about logging after video generation

The application allows users to:
- Enter a prompt or script for video generation
- Select voice providers (Kokoro, ElevenLabs, TikTok)
- Choose voice options and speech rate
- Upload custom background music
- Configure video settings (aspect ratio, subtitles, watermark)
- Monitor generation progress with a live timer
- Download the final video

### Reels Generation Engine (reels_maker.py)

The core engine that coordinates the entire video generation process.

**Key Classes:**
- `ReelsMakerConfig`: Configuration settings for the reels generation process
- `ReelsMaker`: Main engine class that orchestrates the video generation workflow

**Key Methods:**
- `generate_script()`: Generates a script from a prompt using AI
- `generate_search_terms()`: Generates search terms for finding relevant stock videos
- `start()`: Initiates the video generation process
- `process_videos()`: Processes videos for the final composition
- `process_audio()`: Processes audio for the final composition
- `generate_subtitles()`: Generates subtitles for the video
- `concatenate_clips()`: Combines multiple video clips into a single video

This component serves as the central orchestrator, coordinating all other components to produce the final video.

### Video Generation (video_gen.py)

Handles video processing, effects, and composition.

**Key Classes:**
- `VideoGeneratorConfig`: Configuration settings for video generation
- `VideoGenerator`: Main class for video processing and effects

**Key Methods:**
- `get_video_url()`: Retrieves video URLs based on search terms
- `add_watermark()`: Adds watermark to videos
- `add_subtitles()`: Adds subtitles to videos
- `create_gif()`: Creates a GIF preview of the video
- `apply_zoom_effect()`: Applies zoom effects to videos
- `process_video()`: Processes a video with effects, subtitles, and audio

This component handles all video-related operations, including adding effects, subtitles, and combining with audio.

### Speech Synthesis (synth_gen.py)

Manages text-to-speech conversion using various providers.

**Key Classes:**
- `SynthConfig`: Configuration for speech synthesis
- `SynthGenerator`: Main class for generating speech from text

**Key Methods:**
- `synth_speech()`: Synthesizes speech from text using the selected provider
- `generate_with_eleven()`: Generates speech using ElevenLabs
- `generate_with_tiktok()`: Generates speech using TikTok voices
- `generate_with_kokoro()`: Generates speech using Kokoro service
- `split_audio()`: Splits audio files into segments based on sentences

This component handles all text-to-speech operations, supporting multiple voice providers and caching for efficiency.

### Subtitle Generation (subtitle_gen.py)

Creates and formats subtitles for videos.

**Key Classes:**
- `SubtitleConfig`: Configuration for subtitle generation
- `SubtitleGenerator`: Main class for generating subtitles

**Key Methods:**
- `generate_subtitles()`: Generates subtitles from sentences and durations
- `wordify()`: Formats subtitles for better readability
- `locally_generate_subtitles()`: Creates SRT format subtitles

This component handles the creation and formatting of subtitles, ensuring they're properly synchronized with the audio.

### Prompt Generation (prompt_gen.py)

Generates scripts, keywords, and image prompts using AI.

**Key Classes:**
- `PromptGenerator`: Main class for generating various types of prompts

**Key Methods:**
- `generate_script()`: Generates a script from a prompt
- `generate_stock_image_keywords()`: Generates keywords for stock image/video search
- `sentences_to_images()`: Converts sentences to image generation prompts
- `generate_content()`: Generates content based on a prompt

This component leverages AI models to generate scripts, search keywords, and image prompts based on user input.

### Image Generation (image_gen.py)

Generates images using AI services.

**Key Classes:**
- `ImageGeneratorConfig`: Configuration for image generation
- `ImageGenerator`: Main class for generating images

**Key Methods:**
- `generate_image()`: Generates an image from a prompt
- `generate_with_together()`: Generates images using Together AI
- `generate_with_deepinfra()`: Generates images using DeepInfra
- `generate_maybe_anyai_pollination()`: Generates images using AnyAI or Pollination

This component handles AI image generation, supporting multiple providers and styles.

### Video Sources

The application uses two main sources for video content:

1. **Pexels API (pexel.py)**: 
   - `search_for_stock_videos()`: Searches for stock videos on Pexels
   - `filter_negative_content()`: Filters out inappropriate content
   - `get_orientation()`: Determines video orientation

2. **Sakugabooru (sakugabooru.py)**:
   - `search_for_anime_videos()`: Searches for anime videos
   - `get_random_videos_by_pattern()`: Fetches videos matching patterns
   - `fetch_tags()`: Retrieves tags for anime content

These components provide the visual content for the videos, with content filtering to ensure appropriateness.

### Configuration (config.py)

Manages application settings and environment variables.

**Key Components:**
- `__Settings`: Pydantic model for application settings
- Cache path definitions for various assets
- Environment variable loading and management

This component centralizes configuration management, ensuring consistent settings across the application.

## Workflow

The typical workflow of the application is:

1. User inputs a prompt or script in the Streamlit interface
2. The application generates or uses the provided script
3. The script is converted to speech using the selected voice provider
4. Search terms are generated from the script to find relevant videos
5. Videos are downloaded and processed with effects
6. Subtitles are generated and added to the video
7. Audio (speech and optional background music) is combined with the video
8. The final video is rendered and made available for download

## Setup and Installation

To set up the ReelsMaker application:

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables in `.env` file:
   - API keys for various services (OpenAI, ElevenLabs, Pexels, etc.)
   - Configuration settings
4. Run the application: `streamlit run reelsmaker.py`

## API Keys Required

The application requires API keys for several services:
- OpenAI API for script generation
- ElevenLabs API for voice synthesis
- Pexels API for stock videos
- Together AI or DeepInfra for image generation

These should be configured in the `.env` file before running the application.
