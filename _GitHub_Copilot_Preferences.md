# My Copilot Preferences

## Code Recommendations
- Always start code blocks with the filepath comment and Show file navigation instructions when multiple files need changes
- Use clear headings indicating which file to modify
- DO NOT CHANGE any code that is not in the scope of the task.

## Format Preferences
- Use PEP 8 style for Python
- Include descriptive comments for complex logic
- Keep line lengths under 88 characters

## challenges
Objective:
To evolve my current application into a more robust video generation engine.
Context:
The app currently supports:
- Filtering negative keywords.
- Data flow through Kokoro and Pexels APIs.
The ultimate goal is to expand functionality to:
- Video-to-video generation: Including synchronized voiceovers and captions AND
- Image-to-video generation: Similarly with synchronized voiceovers and captions.
Challenges Faced:
- Spent 20+ hours trying to integrate features but underestimated the complexity.
- Reverted to a previous version from my GitHub repo due to stalled progress.
New Approach:
- Shift focus to leverage Pexels API for creating photo-based video workflows, running in parallel to existing workflows like Reel_Maker, Video_Gen, Story_Teller, Pexiel, and Synth_Gen for video-to-video generation.
- Segregate workflows (photo-to-video vs. video-to-video) to gain a clearer understanding of how the app functions and can be transformed.  later, I will want the interface to have a selectbox "video_type": video, photo, hybrid.
Requirements:
- Implement a parallel workflow for photo-to-video conversion while maintaining existing video workflows.
- Integrate synchronized voiceovers and captions for the photo-to-video pipeline.
- Ensure scalability and flexibility for future feature additions.
- I need to know how to synchronize the audio and captions.  I understand pysrt and moviepy are already imported
Request:
Provide support and guidance to structure this parallel workflow effectively and resolve technical challenges for integrating Pexels API into the app. Identify key improvements needed for app transformation.
Create all files necessary for parallel workflow.  I don't want to modify the video gen process in place.  there should be no recommendations to modify existing code to integrate photos to video... We will consider merging them at some time in the future.
