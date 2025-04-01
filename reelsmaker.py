import asyncio
import multiprocessing
import os
import typing
from uuid import uuid4

from loguru import logger
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile
from app.reels_maker import ReelsMaker, ReelsMakerConfig
from app.synth_gen import SynthConfig
from app.video_gen import VideoGeneratorConfig


if "queue" not in st.session_state:
    st.session_state["queue"] = {}

queue: dict[str, ReelsMakerConfig] = st.session_state["queue"]


async def download_to_path(dest: str, buff: UploadedFile) -> str:
    with open(dest, "wb") as f:
        f.write(buff.getbuffer())
    return dest


async def main():
    st.title("AI Reels Story Maker")
    st.write("Create Engaging Faceless Videos for Social Media in Seconds")
    st.write(
        "Our tools make it easy to create captivating faceless videos that boost engagement and reach on social media in seconds."
    )
    st.divider()

    sentence_tab, prompt_tab = st.tabs(
        ["Enter your motivational quote", "Enter Prompt"]
    )

    with sentence_tab:
        sentence = st.text_area(
            label="Enter your quote",
            placeholder="Nothing is impossible. The word itself says 'I'm possible!, Champions keep playing until they get it right, You are never too old to set another goal or to dream a new dream.",
            height=100,
        )

    with prompt_tab:
        prompt = st.text_area(
            label="Enter your prompt",
            placeholder="A motivation quote about life & pleasure",
            height=100,
        )

    st.write("Choose background videos")
    auto_video_tab, upload_video_tab = st.tabs(["Auto Add video", "Upload Videos"])

    with auto_video_tab:
        st.write(
            "We'll automatically download background videos related to your prompt, usefull when you don't have a background video"
        )

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

    voice = st.selectbox("Choose a voice", ["en_male_narration", "en_us_001"])
    voice_provider = st.selectbox("Select voice provider", ["tiktok", "elevenlabs"])

    col1, col2, col3 = st.columns(3)

    # Video Gen config
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
        stroke_width = st.number_input("Border", value=1, step=1, min_value=1)

    with col5:
        fontsize = st.number_input("Font size", value=80, step=1, min_value=1)

    with col6:
        subtitles_position = st.selectbox("Subtitles position", ["center,center"])

    # For video quality settings
    st.divider()
    st.subheader("Video Processing Options")

# Add after other video settings but before the nvenc_preset selection
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



    # Add NVENC preset selection
    nvenc_preset = st.select_slider(
        "Video Quality",
        options=["Fastest (Low Quality)", "Balanced", "Highest Quality"],
        value="Balanced",
        help="Higher quality takes longer but produces better results"
    )

    # Convert to actual preset values
    preset_mapping = {
        "Fastest (Low Quality)": "p1", 
        "Balanced": "p4",
        "Highest Quality": "p7"
    }
    nvenc_preset = preset_mapping[nvenc_preset]

    # text_color = st.color_picker("Text color", value="#ffffff")
    cpu_count = multiprocessing.cpu_count()
    if cpu_count > 1:
        cpu_count = cpu_count - 1

    threads = st.number_input("Threads", value=cpu_count, step=1, min_value=1)

    submitted = st.button("Generate Reels", use_container_width=True, type="primary")

    if submitted:
        queue_id = str(uuid4())

        cwd = os.path.join(os.getcwd(), "tmp", queue_id)
        os.makedirs(cwd, exist_ok=True)

        # create config
        config = ReelsMakerConfig(
            job_id="".join(str(uuid4()).split("-")),
            video_type="narrator",
            prompt=prompt or sentence,
            cwd=cwd,
            background_audio_url=background_audio_url,
            video_gen_config=VideoGeneratorConfig(
                bg_color=str(bg_color),
                fontsize=int(fontsize),
                stroke_color=str(stroke_color),
                stroke_width=int(stroke_width),
                subtitles_position=str(subtitles_position),
                text_color=str(text_color),
                threads=int(threads),
                nvenc_preset=nvenc_preset,
                aspect_ratio=aspect_ratio_value  # Add this line
                # watermark_path="images/watermark.png"
            ),
            synth_config=SynthConfig(
                voice=str(voice),
                voice_provider=os.environ.get("VOICE_PROVIDER") or voice_provider or "tiktok",
            )
        )

        # read uploaded file and save in a path
        if uploaded_audio:
            config.video_gen_config.background_music_path = await download_to_path(
                dest=os.path.join(config.cwd, "background.mp3"), buff=uploaded_audio
            )

        if uploaded_videos:
            config.video_paths = [
                await download_to_path(dest=os.path.join(config.cwd, p.name), buff=p)
                for p in uploaded_videos
            ]

        print(f"starting reels maker: {config.model_dump_json()}")
        st.write(
            "This process is CPU-intensive and will take a considerable time to complete"
        )
        with st.spinner("Generating reels, this will take ~5mins or less..."):
            try:
                if len(queue.items()) > 1:
                    raise Exception("queue is full - someone else is generating reels")
                
                logger.debug("Added to queue")
                queue[queue_id] = config
                
                reels_maker = ReelsMaker(config)
                output = await reels_maker.start()
                st.balloons()
                
                # Add a null check before trying to display the video
                if output is not None and hasattr(output, 'video_file_path'):
                    st.video(output.video_file_path, autoplay=True)
                    
                    # Read the video file once
                    with open(output.video_file_path, "rb") as file:
                        video_bytes = file.read()
                    
                    # Use the bytes for download without affecting the video player
                    st.download_button(
                        "Download Reels", 
                        video_bytes, 
                        file_name="reels.mp4",
                        mime="video/mp4"
                    )
                else:
                    st.error("Video generation failed. Check logs for details.")
                    # Log the actual configuration for debugging
                    logger.error(f"Video generation failed with config: {config}")
            except Exception as e:
                # More specific error message patterns
                error_msg = str(e)
                if "ffmpeg" in error_msg.lower():
                    st.error(f"Video processing error: {e}. Please check logs for details.")
                elif "api key" in error_msg.lower():
                    st.error("API key error. Please check your environment variables.")
                else:
                    st.error(f"Error generating video: {e}")


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
