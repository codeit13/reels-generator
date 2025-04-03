import asyncio
import multiprocessing
import os
import typing
import time
import threading
from uuid import uuid4

from loguru import logger
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile
from app.reels_maker import ReelsMaker, ReelsMakerConfig
from app.synth_gen import SynthConfig
from app.video_gen import VideoGeneratorConfig

# Add this import if not already present
import os.path

# Near the beginning of your main() function, add:
st.session_state.setdefault("last_video_path", None)
if "last_video_bytes" not in st.session_state:
    st.session_state["last_video_bytes"] = None



if "queue" not in st.session_state:
    st.session_state["queue"] = {}

# Add this new dictionary for tracking job timestamps
if "job_timestamps" not in st.session_state:
    st.session_state["job_timestamps"] = {}

queue: dict[str, ReelsMakerConfig] = st.session_state["queue"]
job_timestamps = st.session_state["job_timestamps"]  # Reference the timestamps dict


# Add to reelsmaker.py where the queue is defined
def clear_queue():
    """Clear all pending jobs from the queue"""
    global queue
    if 'queue' in globals():
        queue.clear()  # Correct way to clear a dictionary
        logger.info("Queue cleared successfully")

# Call this when starting a new generation
if "queue_initialized" not in st.session_state:
    clear_queue()
    st.session_state["queue_initialized"] = True


MAX_CONCURRENT = 2  # Adjust based on your server's resources

async def download_to_path(dest: str, buff: UploadedFile) -> str:
    with open(dest, "wb") as f:
        f.write(buff.getbuffer())
    return dest


# Add this function to check audio file validity
async def validate_audio_file(file_path):
    try:
        # Use FFmpeg to probe the file
        import subprocess
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", file_path, "-f", "null", "-"],
            stderr=subprocess.PIPE,
            text=True
        )
        # If there's output, there were errors
        if result.stderr:
            logger.warning(f"Audio validation errors: {result.stderr}")
            return False
        return True
    except Exception as e:
        logger.error(f"Audio validation failed: {e}")
        return False


def format_elapsed_time(seconds):
    """Format seconds into minutes and seconds display"""
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}m {seconds}s"


async def main():
    # Add this line at the beginning of main()
    cwd = os.path.join(os.getcwd(), "tmp")
    os.makedirs(cwd, exist_ok=True)
    
    st.title("AI Reels Story Maker")
    st.write("Create Engaging Faceless Videos for Social Media in Seconds")
    st.write(
        "Our tools make it easy to create captivating faceless videos that boost engagement and reach on social media in seconds."
    )
    st.divider()

    sentence_tab, prompt_tab = st.tabs(
        ["Text to Speech", "Text to Speech 2"]
    )

    with sentence_tab:
        # Create a container for the text area and character count
        input_container = st.container()
        
        # Add the text area
        sentence = input_container.text_area(
            label="Enter your quote",
            placeholder="Nothing is impossible. The word itself says 'I'm possible!, Champions keep playing until they get it right, You are never too old to set another goal or to dream a new dream.",
            height=100,
            key="sentence_input"  # Add a key for on_change detection
        )
        
        # Display character count below the text area
        char_count = len(sentence) if sentence else 0
        color = "#ff4b4b" if char_count > 200 else ("#ffaa4b" if char_count > 150 else "#4bb543")
        input_container.markdown(f"<p style='color:{color};text-align:right;margin-top:-15px;'>Character count: {char_count}</p>", unsafe_allow_html=True)

    with prompt_tab:
        prompt = st.text_area(
            label="Enter your prompt",
            placeholder="A motivation quote about life & pleasure",
            height=100,
        )


    with st.expander("Voice Configuration Info", expanded=True):
        # st.write("### Voice Configuration Info")
        # st.write(f"**Provider:** {voice_provider}")
        # st.write(f"**Voice ID:** {voice}")

        # Create a more detailed voice selection system
        voice_provider = st.selectbox(
            "Select voice provider", 
            ["Elevenlabs","TikTok"]
        )

        # Different voice options based on selected provider
        if voice_provider.lower() == "tiktok":  # Add .lower() to ensure case-insensitive comparison
            voice = st.selectbox(
                "Choose a TikTok voice", 
                [
                    "en_male_narration", 
                    "en_us_001",
                    "en_us_002",  # Male
                    "en_us_006",  # Female
                    "en_us_009",  # Female
                    "en_us_010"   # Male
                ]
            )
        else:  # elevenlabs
            voice = st.selectbox(
                "Choose an ElevenLabs voice", 
                [
                    "21m00Tcm4TlvDq8ikWAM",     # Rachel
                    "2EiwWnXFnvU5JabPnv8n",     # Clyde
                    "D38z5RcWu1voky8WS1ja",     # Adam                    
                    "XB0fDUnXU5powFXDhCwa",     # Josh
                    "pNInz6obpgDQGcFmaJgB",     # "Elli (Female)",
                    "jBpfuIE2acCO8z3wKNLl",     # "Bella (Female)",
                    "onwK4e9ZLuTAKqWW03F9",     # "Thomas (Male)",
                    "g5CIjZEefAph4nQFvHAz",     # "Daniel (Male)",
                    "IKne3meq5aSn9XLyUdCD",     # Antoni
                    "ErXwobaYiN019PkySvjV"     # "Antoni 2 (Male)"  # Newer Antoni
                ],
                format_func=lambda x: {
                    "21m00Tcm4TlvDq8ikWAM": "Rachel (Female)",
                    "2EiwWnXFnvU5JabPnv8n": "Clyde (Male)",
                    "D38z5RcWu1voky8WS1ja": "Adam (Male)",                    
                    "XB0fDUnXU5powFXDhCwa": "Josh (Male)",
                    "pNInz6obpgDQGcFmaJgB": "Elli (Female)",
                    "jBpfuIE2acCO8z3wKNLl": "Bella (Female)",
                    "onwK4e9ZLuTAKqWW03F9": "Thomas (Male)",
                    "g5CIjZEefAph4nQFvHAz": "Daniel (Male)",
                    "IKne3meq5aSn9XLyUdCD": "Antoni (Male)",
                    "ErXwobaYiN019PkySvjV": "Antoni 2 (Male)"  # Newer Antoni
                }.get(x, x)
            )

        # Display voice configuration info (moved outside expander to avoid nesting)        
        st.write(f"**Provider:** {voice_provider}")
        st.write(f"**Voice ID:** {voice}")

        # For ElevenLabs, show the human-readable name
        if voice_provider.lower() == "elevenlabs":
            voice_names = {
                "21m00Tcm4TlvDq8ikWAM": "Rachel (Female)",
                "2EiwWnXFnvU5JabPnv8n": "Clyde (Male)",
                "D38z5RcWu1voky8WS1ja": "Adam (Male)",
                "IKne3meq5aSn9XLyUdCD": "Antoni (Male)",
                "XB0fDUnXU5powFXDhCwa": "Josh (Male)",
                "pNInz6obpgDQGcFmaJgB": "Elli (Female)",
                "jBpfuIE2acCO8z3wKNLl": "Bella (Female)",
                "onwK4e9ZLuTAKqWW03F9": "Thomas (Male)",
                "g5CIjZEefAph4nQFvHAz": "Daniel (Male)",
                "ErXwobaYiN019PkySvjV": "Antoni (Male)"
            }
            st.write(f"**Voice Name:** {voice_names.get(voice, 'Unknown')}")

        # Show environment overrides if present
        env_provider = os.environ.get("VOICE_PROVIDER")
        env_voice = os.environ.get("VOICE")

        if env_provider:
            st.warning(f"⚠️ Environment override for provider: {env_provider}")
        if env_voice:
            st.warning(f"⚠️ Environment override for voice: {env_voice}")





    # First expander for Inputs section
    with st.expander("Inputs (Video, Audio & Voice)", expanded=False):
        st.write("Choose background videos")
        auto_video_tab, upload_video_tab = st.tabs(["Auto Add video", "Upload Videos"])

        # with auto_video_tab:
        #     st.write(
        #         "We'll automatically download background videos related to your prompt, usefull when you don't have a background video"
        #     )

        with upload_video_tab:
            uploaded_videos = st.file_uploader(
                "Upload a background videos",
                type=["mp4", "webm"],
                accept_multiple_files=True,
            )

        st.write("Choose a background audio")
        upload_audio_tab, audio_url_tab = st.tabs(["Upload audio", "Enter Audio Url"])

        with upload_audio_tab:
            uploaded_audio = st.file_uploader(
                "Upload a background audio", type=["mp3", "webm"]
            )

        with audio_url_tab:
            st.warning("Sorry, this feature is not available yet")
            background_audio_url = st.text_input(
                "Enter a background audio URL", placeholder="Enter URL"
            )

        # Inside the first expander for Inputs section, add this after the auto_video_tab section

        with auto_video_tab:
            # st.write(
            #     "We'll automatically download background videos related to your prompt, usefull when you don't have a background video"
            # )
            
            # Add video count control
            max_bg_videos = int(os.getenv("MAX_BG_VIDEOS", 20))  # Default to 20 if not set

            max_videos = st.slider(
                "Number of videos to download",
                min_value=1,
                max_value=max_bg_videos,  # Use environment variable
                value=min(11, max_bg_videos),  # Default to 11, but don't exceed max
                step=1,
                help="How many background videos to download from Pexels"
            )
        
        # Subtitles controls
        st.write("Subtitle Appearance")
        col1, col2, col3 = st.columns(3)

        with col1:
            text_color = st.color_picker("Subtitles Text color", value="#ffffff")

        with col2:
            stroke_color = st.color_picker("Subtitles Stroke color", value="#000000")

        with col3:
            bg_color = st.color_picker(
                "Subtitles Background color (None)",
                value=None,
            )

        col4, col5, col6 = st.columns(3)
        with col4:
            stroke_width = st.number_input("Border", value=2, step=1, min_value=1)

        with col5:
            fontsize = st.number_input("Font size", value=100, step=5, min_value=10)

        with col6:
            subtitles_position = st.selectbox("Subtitles position", ["center,center"])




    # Second expander for Video Processing options
    with st.expander("Video Processing Options", expanded=False):
        st.subheader("Video Format")
        aspect_ratio = st.selectbox(
            "Aspect Ratio",
            options=[
                "Landscape (16:9) - YouTube/Facebook", 
                "Portrait (9:16) - Instagram/TikTok",             
                "Square (1:1) - Instagram"
            ],
            index=0,  # Default to portrait for reels
            help="Choose the aspect ratio based on your target platform"
        )

        # Extract just the ratio value for the config
        aspect_ratio_map = {
            "Portrait (9:16) - Instagram/TikTok": "9:16",
            "Landscape (16:9) - YouTube/Facebook": "16:9",
            "Square (1:1) - Instagram": "1:1"
        }
        aspect_ratio_value = aspect_ratio_map[aspect_ratio]



        # Change the video quality slider to use CPU presets
        video_quality = st.select_slider(
            "Video Quality",
            options=["Fastest (Low Quality)", "Balanced", "High Quality"],
            value="Fastest (Low Quality)",
            help="Higher quality takes longer but produces better results"
        )

        # Convert to CPU preset values
        preset_mapping = {
            "Fastest (Low Quality)": "ultrafast", 
            "Balanced": "veryfast",
            "High Quality": "medium"
        }
        cpu_preset = preset_mapping[video_quality]
        
        # Set this before the configuration is created, for better readability
        # Move this up above the config creation
        auto_download = False

        # CPU thread settings
        cpu_count = multiprocessing.cpu_count()
        # Use fewer threads to prevent memory issues with integrated GPU
        cpu_count = max(1, min(8, cpu_count // 2))  # Use half available cores (1-8)
        threads = st.number_input("Threads", value=cpu_count, step=1, min_value=1, max_value=16)

        # Update the config creation to ensure voice_provider is correctly set:
        config = ReelsMakerConfig(
            job_id="".join(str(uuid4()).split("-")),
            video_type="narrator",
            prompt=prompt or sentence,
            cwd=cwd,
            background_audio_url=background_audio_url,
            max_videos=max_videos,
            video_gen_config=VideoGeneratorConfig(
                bg_color=str(bg_color),
                fontsize=int(fontsize),
                stroke_color=str(stroke_color),
                stroke_width=int(stroke_width),
                subtitles_position=str(subtitles_position),
                text_color=str(text_color),
                threads=int(threads),
                cpu_preset=cpu_preset,
                aspect_ratio=aspect_ratio_value
            ),
            synth_config=SynthConfig(
                voice=str(voice),
                # Ensure lowercase and priority order for voice provider
                voice_provider=(voice_provider.lower() if voice_provider else None) or 
                               os.environ.get("VOICE_PROVIDER", "").lower() or 
                               "tiktok",  # Default to TikTok since ElevenLabs is out of credits
            ),
        )

        # Add validation for uploaded audio
        if uploaded_audio:
            try:
                # Validate audio file size
                if uploaded_audio.size > 20 * 1024 * 1024:  # Limit to 20MB
                    st.warning("Audio file is very large, which may cause processing issues")
                
                # Save the audio file
                audio_path = await download_to_path(
                    dest=os.path.join(config.cwd, "background.mp3"), 
                    buff=uploaded_audio
                )
                
                config.video_gen_config.background_music_path = audio_path
                
            except Exception as audio_error:
                st.warning(f"Error processing audio file: {audio_error}. Using default audio instead.")
                config.video_gen_config.background_music_path = None

        if uploaded_videos:
            config.video_paths = [
                await download_to_path(dest=os.path.join(config.cwd, p.name), buff=p)
                for p in uploaded_videos
            ]

        print(f"starting reels maker: {config.model_dump_json()}")
        st.write(
            "This process is CPU-intensive and will take a considerable time to complete"
        )

        # Create a prominent Generate button
        generate_button_container = st.container()
        generate_clicked = generate_button_container.button("🚀 Generate Video", 
                                                 type="primary", 
                                                 key="generate_video_button",
                                                 use_container_width=True)

        # Only proceed with generation if the button is clicked

        # Fixed cancel button implementation
        # Set this right after adding to the queue timestamps, before showing the button
        if generate_clicked:
            # Clean up any stale jobs and other existing code...
            
            # Add timestamp to the current job     
            now = time.time()       
            job_timestamps[config.job_id] = now
            
            # Reset timer when generate is clicked
            st.session_state["start_time"] = time.time()
            st.session_state["timer_running"] = True
            st.session_state["cancel_requested"] = False
            
            # IMPORTANT: Set is_generating to true BEFORE showing the cancel button
            st.session_state["is_generating"] = True

            # Create placeholders for UI elements
            elapsed_placeholder = st.empty()
            cancel_placeholder = st.empty()
            
            # Replace the conditional cancel button with unconditional version
            # Remove the is_generating check since we already set it above
            if cancel_placeholder.button("Cancel Generation", key="cancel_gen"):
                st.session_state["cancel_requested"] = True
                st.warning("Cancellation requested. Please wait for the current operation to complete...")





            with st.spinner("Generating reels, this will take ~5mins or less..."):
                try:
                    # Timer update logic
                    if "timer_running" in st.session_state and st.session_state["timer_running"]:
                        st.empty().markdown(f"<div id='timer-refresh'>{time.time()}</div>", unsafe_allow_html=True)
                        current_time = time.time()
                        elapsed = current_time - st.session_state.get("start_time", current_time)
                        elapsed_placeholder.markdown(f"⏱️ **Elapsed time:** {format_elapsed_time(int(elapsed))}")
                    
                    # Add to queue and process
                    queue_id = config.job_id
                    queue[queue_id] = config
                    
                    # Create and run reels maker
                    reels_maker = ReelsMaker(config)
                    output = await reels_maker.start(st_state=st.session_state)
                    
                    # Reset generation state
                    st.session_state["timer_running"] = False
                    st.session_state["is_generating"] = False
                    st.session_state["last_generated_id"] = queue_id
                    
                    # Show success and display video
                    st.success("Video generated successfully!")
                    
                    if output is not None and hasattr(output, 'video_file_path'):
                        video_path = output.video_file_path
                        st.session_state["last_video_path"] = video_path
                        
                        # Display video
                        st.video(video_path)
                        
                        # Create download button
                        if os.path.exists(video_path):
                            with open(video_path, "rb") as file:
                                video_bytes = file.read()
                                st.session_state["last_video_bytes"] = video_bytes
                            
                            st.download_button(
                                "Download Reels", 
                                video_bytes, 
                                file_name=f"reels_{queue_id}.mp4",
                                mime="video/mp4",
                                key=f"download_button_{queue_id}"
                            )
                except Exception as e:
                    st.session_state["is_generating"] = False
                    st.session_state["timer_running"] = False
                    st.error(f"Error: {str(e)}")
                    logger.exception(f"Generation failed: {e}")





        if os.path.exists(cwd):
            try:
                # Check if reels_maker exists before using it
                if 'reels_maker' in locals() and hasattr(reels_maker, 'cleanup_temp_files'):
                    reels_maker.cleanup_temp_files()
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up temporary files: {cleanup_error}")

# # Add this to display diagnostics in the UI
# if st.sidebar.button("Run System Diagnostics"):
#     with st.spinner("Running diagnostics..."):
#         # Create temporary instance of ReelsMaker to run diagnostics
#         temp_config = ReelsMakerConfig(job_id="diagnostics", video_type="test")
#         diag_maker = ReelsMaker(temp_config)
#         diagnostics = asyncio.run(diag_maker.run_diagnostics())
        
#         # Display results
#         st.sidebar.json(diagnostics)


if __name__ == "__main__":
    asyncio.run(main())
