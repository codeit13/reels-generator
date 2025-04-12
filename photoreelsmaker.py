import os
import asyncio
import sys
import time
import base64
import tempfile
import streamlit as st
from loguru import logger
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from streamlit.components.v1 import html  # Add this import

sys.path.append('/app')  # Add the root directory to path
from app.photo_reels_maker import PhotoReelsMaker, PhotoReelsMakerConfig
from app.synth_gen import VoiceProvider
from app.base import StartResponse
from app.kokoro_service import kokoro_client
from app.utils.metrics_logger import MetricsLogger

# Add this function after import statements and before UI setup
def create_timer():
    """Create a JavaScript timer that updates every second without page refreshes"""
    timer_html = """
        <div id="timer_display" style="font-size: 1.2rem; font-weight: bold; margin: 10px 0; color: white; background-color: rgba(0,0,0,0.5); padding: 5px 10px; border-radius: 5px; display: inline-block;">⏱️ Elapsed time: 0m 0s</div>
     
    <script>
        // Timer variables
        var startTime = new Date().getTime();
        var timerInterval;
        
        // Format time function
        function formatTime(seconds) {
            var minutes = Math.floor(seconds / 60);
            var secs = seconds % 60;
            return minutes + "m " + secs + "s";
        }
        
        // Update the timer display
        function updateTimer() {
            var currentTime = new Date().getTime();
            var elapsedSeconds = Math.floor((currentTime - startTime) / 1000);
            document.getElementById("timer_display").innerHTML = "⏱️ Elapsed time: " + formatTime(elapsedSeconds);
            
            // Also check for success message on each update (backup method)
            checkForSuccess();
        }
        
        // Function to check for success message
        function checkForSuccess() {
            const successElements = document.querySelectorAll('.element-container');
            for (let element of successElements) {
                if (element.innerText && element.innerText.includes("Video generated successfully")) {
                    console.log("Success message found, stopping timer");
                    clearInterval(timerInterval);
                    return;
                }
            }
        }
        
        // Start the timer
        timerInterval = setInterval(updateTimer, 1000);
        
        // Watch for completion message with enhanced targeting
        const observer = new MutationObserver((mutations) => {
            for (let mutation of mutations) {
                if (mutation.type === 'childList' && mutation.addedNodes.length) {
                    for (let node of mutation.addedNodes) {
                        if (node.nodeType === Node.ELEMENT_NODE) {
                            // Check the node itself
                            if (node.innerText && node.innerText.includes("Video generated successfully")) {
                                console.log("Timer stopped: video generation complete (direct match)");
                                clearInterval(timerInterval);
                                return;
                            }
                            
                            // Also check any child elements with class 'stAlert'
                            const alerts = node.querySelectorAll('.stAlert');
                            for (let alert of alerts) {
                                if (alert.innerText && alert.innerText.includes("Video generated successfully")) {
                                    console.log("Timer stopped: video generation complete (alert match)");
                                    clearInterval(timerInterval);
                                    return;
                                }
                            }
                        }
                    }
                }
            }
        });
        
        // Start observing the entire document body with all possible options
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            characterData: true
        });
        
        // Initial check in case the message is already there
        checkForSuccess();
    </script>
    """
    return html(timer_html, height=50)

# Set up logging
logger.add("logs/photoreelsmaker.log", rotation="100 MB", level="INFO")

st.set_page_config(
    page_title="Photo Reels Maker",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="expanded",
)

CACHE_DIR = os.path.join(".", "tmp", "st_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Initialize session state variables
if "cancel_requested" not in st.session_state:
    st.session_state.cancel_requested = False
if "generation_started" not in st.session_state:
    st.session_state.generation_started = False
if "results_ready" not in st.session_state:
    st.session_state.results_ready = False
if "video_path" not in st.session_state:
    st.session_state.video_path = None
if "script" not in st.session_state:
    st.session_state.script = ""
if "log_messages" not in st.session_state:
    st.session_state.log_messages = []
# Add these timer-specific session variables
if "timer_running" not in st.session_state:
    st.session_state.timer_running = False
if "start_time" not in st.session_state:
    st.session_state.start_time = 0

# Sidebar navigation
st.sidebar.title("Photo Reels Maker")
st.sidebar.markdown("Create videos from stock photos")
nav_option = st.sidebar.radio(
    "Navigation", 
    ["Create Video", "Settings", "About"],
    index=0
)

# Sidebar for settings
with st.sidebar.expander("Voice Settings", expanded=True):
    voice_provider = st.selectbox(
        "Voice Provider", 
        ["kokoro"], 
        index=0,
        help="Select the voice provider"
    )
    
    # Get available voices based on provider
    if voice_provider == "kokoro":
        try:
            voices_data = kokoro_client.get_voices()
            voices = [voice["id"] for voice in voices_data]
            voice_names = [voice["name"] for voice in voices_data]
            voice_options = dict(zip(voices, voice_names))
            
            selected_voice = st.selectbox(
                "Voice", 
                options=list(voice_options.keys()),
                format_func=lambda x: f"{x} ({voice_options.get(x, '')})",
                index=0 if voices else 0,
                help="Select the voice to use"
            )
        except Exception as e:
            logger.error(f"Failed to get voices from Kokoro: {e}")
            st.warning("⚠️ Could not load voices from Kokoro. Using default.")
            selected_voice = "af_heart"
    else:
        selected_voice = "af_heart"  # Default fallback
    
    speech_rate = st.slider(
        "Speech Rate", 
        min_value=0.5, 
        max_value=2.0, 
        value=1.0, 
        step=0.1,
        help="Adjust the speed of speech"
    )

with st.sidebar.expander("Video Settings", expanded=True):
    aspect_ratio = st.selectbox(
        "Aspect Ratio",
        ["16:9", "9:16", "1:1"],
        index=0,
        help="Select the video aspect ratio"
    )
    
    animation_style = st.selectbox(
        "Animation Style",
        ["kenburns", "pan", "static"],
        index=0,
        help="Select the animation style for photos"
    )
    
    transition_style = st.selectbox(
        "Transition Style",
        ["fade", "dissolve", "none"],
        index=0,
        help="Select the transition style between photos"
    )
    
    max_photos = st.slider(
        "Maximum Photos",
        min_value=1,
        max_value=20,
        value=5,
        step=1,
        help="Maximum number of photos to include"
    )

with st.sidebar.expander("Photo Settings", expanded=True):
    photo_endpoint = st.selectbox(
        "Photo Source",
        ["Search", "Curated", "Popular"],
        index=0,
        help="Source for photos: Search (by query), Curated (editor's choice), or Popular"
    )
    
    # Convert the user-friendly name to the API parameter
    endpoint_type = photo_endpoint.lower()

# Create a cancel button functionality
def request_cancel():
    st.session_state.cancel_requested = True
    st.warning("🛑 Cancellation requested. Please wait...")

# Helper function to display video
def display_video(video_path):
    if not os.path.exists(video_path):
        st.error(f"Video file not found: {video_path}")
        return
    
    # Get video file format
    video_format = video_path.split('.')[-1].lower()
    
    # Read video file
    with open(video_path, 'rb') as video_file:
        video_bytes = video_file.read()
    
    # Display video
    st.video(video_bytes)
    
    # Provide download button
    col1, col2 = st.columns([3, 1])
    with col1:
        st.download_button(
            label="Download Video",
            data=video_bytes,
            file_name=f"photo_reel_{os.path.basename(video_path)}",
            mime=f"video/{video_format}"
        )
    with col2:
        video_size = os.path.getsize(video_path) / (1024 * 1024)  # Convert to MB
        st.info(f"Size: {video_size:.2f} MB")

# Main interface based on navigation
if nav_option == "Create Video":
    st.title("Photo Reels Maker")
    st.markdown("Turn your ideas into engaging videos using stock photos and AI narration.")

    # Creation form
    with st.form(key="generation_form"):
        prompt = st.text_area(
            "Enter your prompt",
            key="prompt", 
            height=100,
            help="Describe what you'd like to create a video about",
            placeholder="Enter a description of the video you want to create, e.g., 'A beautiful journey through the mountains of Switzerland'"
        )
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            use_script = st.checkbox("Use custom script", value=False)
        
        custom_script = ""
        if use_script:
            custom_script = st.text_area(
                "Custom Script", 
                key="custom_script", 
                height=200,
                help="Enter your custom script for the video",
                placeholder="Enter your script here. Each sentence will be paired with a photo."
            )
        
        with col2:
            background_music = st.checkbox("Add background music", value=False)
        
        background_audio_url = ""
        if background_music:
            background_audio_url = st.text_input(
                "Background Music URL", 
                key="bg_music_url",
                help="Enter URL to background music MP3",
                placeholder="https://example.com/music.mp3"
            )
        
        submit_button = st.form_submit_button(
            label="Generate Video", 
            use_container_width=True,
            type="primary"
        )
        
        if submit_button:
            if not prompt.strip() and not custom_script.strip():
                st.error("⚠️ Please enter a prompt or a custom script.")
            else:
                st.session_state.generation_started = True
                st.session_state.cancel_requested = False
                st.session_state.results_ready = False
                st.session_state.video_path = None
                st.session_state.log_messages = []
                st.session_state.script = custom_script if use_script else ""
                # Add timer reset
                st.session_state.start_time = time.time()
                st.session_state.timer_running = True
    
    # Generate the video if requested
    if st.session_state.generation_started and not st.session_state.results_ready:
        # Create placeholder for status and progress
        status_container = st.empty()
        progress_bar = st.progress(0, "Preparing to generate video...")
        log_container = st.container()
        cancel_btn_col1, _ = st.columns([1, 3])
        with cancel_btn_col1:
            if st.button("Cancel Generation", type="secondary"):
                request_cancel()
                
        # Add the timer component here
        create_timer()  # This will display and start the timer

        # Run the video generation process
        try:
            # Update the progress bar
            progress_bar.progress(10, "Setting up configuration...")

            # Create configuration
            config = PhotoReelsMakerConfig(
                job_id=f"photo_{int(time.time())}",  # Add this line to generate a unique job ID
                prompt=prompt,
                script=st.session_state.script,
                voice=selected_voice,
                voice_provider=VoiceProvider.KOKORO if voice_provider == "kokoro" else VoiceProvider.KOKORO,
                speech_rate=speech_rate,
                aspect_ratio=aspect_ratio,
                max_photos=max_photos,
                photo_duration=5.0,
                animation_style=animation_style,
                transition_style=transition_style,
                background_audio_url=background_audio_url if background_music else None,
                photo_endpoint_type=endpoint_type,
            )
            
            # Update progress
            progress_bar.progress(20, "Creating photo reels maker...")
            
            # Set up a custom logger handler to capture logs
            class StreamlitLogHandler:
                def __init__(self):
                    self.logs = []
                
                def write(self, message):
                    if message.strip():
                        self.logs.append(message)
                        st.session_state.log_messages = self.logs[-10:]  # Keep last 10 messages
                        with log_container:
                            for msg in st.session_state.log_messages:
                                st.text(msg)
                
                def flush(self):
                    pass
            
            log_handler = StreamlitLogHandler()
            logger.add(log_handler, format="{time:HH:mm:ss} | {message}", level="INFO")
            
            # Create the reels maker
            maker = PhotoReelsMaker(config)
            
            progress_bar.progress(30, "Starting video generation...")
            
            # Run the generation process
            async def run_generation():
                # First generate the script if not provided
                if not st.session_state.script:
                    script = await maker.generate_script(config.prompt)
                    st.session_state.script = script
                else:
                    script = st.session_state.script
                
                # Then extract search terms from the script
                search_terms = await maker.generate_search_terms(script)
                
                # Determine orientation based on aspect ratio
                orientation = "landscape"  # Default
                if config.aspect_ratio == "9:16":
                    orientation = "portrait"
                elif config.aspect_ratio == "1:1":
                    orientation = "square"
                
                # Now you can download photos
                photo_data = await maker.download_photos(search_terms, orientation, config.photo_endpoint_type)
                
                # Generate the video
                response = await maker.start(st_state=st.session_state)
                
                # Rest of your code handling the response
                if response.status == "success":
                    st.session_state.video_path = response.video_file_path
                    st.session_state.results_ready = True
                    # Stop timer when complete
                    st.session_state.timer_running = False
                    progress_bar.progress(100, "Video generation complete!")
                elif response.status == "cancelled":
                    progress_bar.empty()
                    status_container.warning("⚠️ Generation was cancelled.")
                    st.session_state.generation_started = False
                else:
                    progress_bar.empty()
                    status_container.error(f"❌ Generation failed: {response.status}")
                    st.session_state.generation_started = False
                
                return response
            
            # Run the async function in the main thread
            response = asyncio.run(run_generation())
            
        except Exception as e:
            logger.error(f"Error during generation: {e}")
            progress_bar.empty()
            status_container.error(f"❌ An error occurred: {str(e)}")
            st.session_state.generation_started = False
    
    # Display the results if ready
    if st.session_state.results_ready and st.session_state.video_path:
        st.success("✅ Video generation complete!")
        display_video(st.session_state.video_path)
        create_timer()  # Add the timer display

elif nav_option == "Settings":
    st.title("Settings")
    
    # General settings
    st.header("General Settings")
    
    # Path settings
    with st.expander("Path Settings", expanded=True):
        output_dir = st.text_input(
            "Output Directory",
            value=os.environ.get("PHOTO_OUTPUT_DIR", "/app/outputs/photos"),
            help="Directory where generated videos will be saved"
        )
    
    # API settings
    with st.expander("API Settings", expanded=False):
        st.subheader("Pexels API")
        pexels_key = st.text_input(
            "Pexels API Key",
            value="********" if os.environ.get("PEXELS_API_KEY") else "",
            type="password",
            help="API key for Pexels stock photo service"
        )
        
        st.subheader("Kokoro TTS Service")
        kokoro_url = st.text_input(
            "Kokoro Service URL",
            value=os.environ.get("KOKORO_SERVICE_URL", "http://kokoro_service:8880"),
            help="URL for Kokoro TTS service"
        )

    st.info("⚠️ Settings changes will only take effect after restarting the application.")

elif nav_option == "About":
    st.title("About Photo Reels Maker")
    
    st.markdown("""
    ## Overview
    
    Photo Reels Maker creates engaging videos from stock photos with AI-generated narration.
    
    ### How it works:
    
    1. **Input**: You provide a prompt or a custom script
    2. **Photos**: We search Pexels for high-quality stock photos matching your content
    3. **Animation**: Photos are animated with Ken Burns and other effects
    4. **Narration**: AI-generated voiceover narrates your content
    5. **Subtitles**: Automatically generated subtitles are added
    6. **Output**: A complete video ready for sharing
    
    ### Features:
    
    * Multiple animation styles (Ken Burns, Pan, Static)
    * Transition effects between photos
    * AI voice narration with Kokoro TTS
    * Custom script support
    * Background music integration
    * Multiple aspect ratios (16:9, 9:16, 1:1)
    
    ### Credits:
    
    * Photos provided by [Pexels](https://www.pexels.com/)
    * Voice synthesis by Kokoro TTS service
    """)

# Add footer
st.markdown("---")
st.markdown("© 2025 Photo Reels Maker | Powered by Pexels & Kokoro TTS")