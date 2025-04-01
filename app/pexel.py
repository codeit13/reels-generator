import os
from loguru import logger
import requests


async def search_for_stock_videos(
    limit: int = 5, 
    min_dur: int = 10, 
    query: str = "nature",
    orientation: str = None) -> list[str]:
    """
    Search for stock videos on Pexels with orientation filtering.
    
    Args:
        orientation: "portrait", "landscape", or "square"
    """
    # Get API key
    PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
    
    if not PEXELS_API_KEY:
        logger.error("PEXELS_API_KEY not found in environment variables")
        return []
    
    headers = {"Authorization": PEXELS_API_KEY}
    qurl = f"https://api.pexels.com/videos/search"
    
    # Add orientation to query parameters
    params = {
        "query": query,
        "per_page": limit * 2,  # Request more to ensure we have enough after filtering
        "min_duration": min_dur
    }
    
    # Add orientation parameter if specified
    if orientation:
        params["orientation"] = orientation
        logger.info(f"Searching for {orientation} videos matching '{query}'")
    
    r = requests.get(qurl, headers=headers, params=params)
    response = r.json()
    
    if not response.get("videos"):
        logger.warning(f"No videos found for query '{query}' with orientation '{orientation}'")
        return []
    
    # Additional filtering to ensure correct aspect ratio
    video_urls = []
    
    try:
        for video in response["videos"]:
            if video["duration"] < min_dur:
                continue
                
            # Get the highest quality video URL
            raw_urls = video["video_files"]
            best_video = None
            max_resolution = 0
            
            for v in raw_urls:
                if ".com/video-files" not in v["link"]:
                    continue
                    
                # Get dimensions and verify orientation
                width, height = v["width"], v["height"]
                video_orientation = get_orientation(width, height)
                
                # Skip if orientation doesn't match requested orientation
                if orientation and video_orientation != orientation:
                    continue
                    
                resolution = width * height
                if resolution > max_resolution:
                    max_resolution = resolution
                    best_video = v["link"]
            
            if best_video:
                video_urls.append(best_video)
                
            # Break if we have enough videos
            if len(video_urls) >= limit:
                break
                
    except Exception as e:
        logger.error(f"Error processing videos: {e}")
    
    return video_urls

def get_orientation(width, height):
    """Determine video orientation based on dimensions"""
    ratio = width / height
    if ratio > 1.2:  # Wider than tall
        return "landscape"
    elif ratio < 0.8:  # Taller than wide
        return "portrait"
    else:
        return "square"  # Close to square
