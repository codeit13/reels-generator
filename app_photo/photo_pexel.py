from loguru import logger
import os
import requests
import json
import time
from typing import List, Dict, Optional, Tuple, Any
from app.utils.metrics_logger import MetricsLogger

# Add this at the module level to cache keywords
_negative_keywords_cache = None

# Initialize the logger at the module level
metrics_logger = MetricsLogger(enabled=True)
metrics_logger.initialize()  # Make sure this is called

def get_negative_keywords():
    """Load negative keywords from JSON file with caching."""
    global _negative_keywords_cache
    
    # Return cached keywords if available
    if (_negative_keywords_cache is not None):
        return _negative_keywords_cache
    
    try:
        import json
        import os
        
        # Path to the negative keywords file (adjust path as necessary)
        file_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            "data", 
            "negative_keywords.json"
        )
        
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                _negative_keywords_cache = json.load(f)
                logger.info(f"Loaded {len(_negative_keywords_cache)} negative keywords")
                return _negative_keywords_cache
    except Exception as e:
        logger.error(f"Failed to load negative keywords: {e}")
    
    # Fallback to default keywords if something goes wrong
    _negative_keywords_cache = [
        "argument", "fight", "prison", "jail", "depression", 
        "darkness", "occult", "violence", "conflict", "suffering"
    ]
    return _negative_keywords_cache

def filter_negative_content(items, query=None, metrics_logger=None):
    """Filter out content that contains negative keywords in description, tags, or URL."""
    negative_keywords = get_negative_keywords()
    
    if not negative_keywords:
        logger.warning("No negative keywords available for filtering")
        return items, [], []
        
    filtered_items = []
    rejected_items = []  # Store rejected items for logging
    rejected_keywords = set()  # Track which keywords caused rejection
    
    for item in items:
        is_rejected = False
        description = item.get("alt", "").lower() if item.get("alt") else ""
        photographer = item.get("photographer", "").lower() if item.get("photographer") else ""
        
        # Check for negative keywords in description or photographer name
        for keyword in negative_keywords:
            if keyword.lower() in description or keyword.lower() in photographer:
                rejected_items.append(item)
                rejected_keywords.add(keyword)
                is_rejected = True
                break
                
        if not is_rejected:
            filtered_items.append(item)
    
    # Log the rejected keywords if metrics_logger is provided
    if metrics_logger and rejected_keywords:
        metrics_logger.log_rejected_keywords(list(rejected_keywords), query)
    
    logger.info(f"Content filtering: {len(items)} photos -> {len(filtered_items)} photos remained after filtering")
    
    return filtered_items, rejected_items, list(rejected_keywords)

async def search_for_stock_photos(
    limit: int = 5, 
    query: str = "nature",
    orientation: str = None,
    endpoint_type: str = "search",  # New parameter to select endpoint type
    metrics_logger=None,
    photo_match_logger=None) -> list[Dict]:
    """
    Search for stock photos on Pexels with orientation and content filtering.
    
    Args:
        limit: Maximum number of photos to return
        query: Search query string
        orientation: Photo orientation (landscape, portrait, square)
        endpoint_type: Type of endpoint to use (search, curated, popular, id)
        metrics_logger: Optional metrics logger
        photo_match_logger: Optional logger for photo matches
        
    Returns:
        List of photo information dictionaries
    """
    # Use the metrics logger if provided, otherwise use module-level
    _metrics_logger = metrics_logger if metrics_logger is not None else globals().get('metrics_logger')
    
    # Log the search query being used
    if _metrics_logger:
        _metrics_logger.log_search_query(query)
    
    # Get the API key
    PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
    if not PEXELS_API_KEY:
        logger.error("Pexels API key not found in environment variables")
        return []
    
    headers = {"Authorization": PEXELS_API_KEY}
    
    # Determine which endpoint to use
    if endpoint_type == "search":
        qurl = os.environ.get("PEXELS_PHOTO_API_URL", "https://api.pexels.com/v1/search")
        if not qurl.endswith("search"):
            qurl = "https://api.pexels.com/v1/search"
        
        params = {
            "query": query,
            "per_page": limit * 2,  # Request more than needed to account for filtering
        }
        
        # Add orientation parameter if specified
        if orientation:
            params["orientation"] = orientation
    
    elif endpoint_type == "curated":
        qurl = os.environ.get("PEXELS_PHOTO_API_URL_CURATED", "https://api.pexels.com/v1/curated")
        params = {
            "per_page": limit * 2
        }
        
    elif endpoint_type == "popular":
        qurl = "https://api.pexels.com/v1/popular"
        params = {
            "per_page": limit * 2
        }
        
    elif endpoint_type == "id" and query.isdigit():
        # Direct photo by ID lookup
        qurl = f"https://api.pexels.com/v1/photos/{query}"
        params = {}
    else:
        # Default to search if unrecognized endpoint type
        logger.warning(f"Unrecognized endpoint type '{endpoint_type}', falling back to search")
        qurl = os.environ.get("PEXELS_PHOTO_API_URL", "https://api.pexels.com/v1/search")
        params = {
            "query": query,
            "per_page": limit * 2
        }
    
    # Start timing photo search
    if _metrics_logger:
        _metrics_logger.start_timer("photo_search")
    
    # Request photos
    try:
        r = requests.get(qurl, headers=headers, params=params)
        response = r.json()
    except Exception as e:
        logger.error(f"Error fetching photos from Pexels: {e}")
        return []
    
    # Process the response based on endpoint type
    if endpoint_type == "id":
        # Single photo response structure is different
        if "id" in response:
            photos = [response]  # Wrap the single photo in a list
        else:
            logger.warning(f"No photo found with ID: {query}")
            return []
    else:
        # For search, curated, and popular endpoints
        if not response.get("photos"):
            logger.warning(f"No photos found for query: {query} using endpoint: {endpoint_type}")
            return []
        photos = response.get("photos", [])
    
    # Stop timing photo search
    if _metrics_logger:
        _metrics_logger.stop_timer("photo_search")
    
    # Filter out negative content
    filtered_photos, rejected_photos, rejected_keywords = filter_negative_content(
        photos, query, _metrics_logger
    )
    
    # Log photo matches if logger provided
    if photo_match_logger:
        for photo in filtered_photos[:limit]:
            photo_match_logger.log_match(
                query=query,
                photo_id=photo.get("id", "unknown"),
                photographer=photo.get("photographer", "unknown"),
                width=photo.get("width", 0),
                height=photo.get("height", 0),
            )
    
    # Return limited number of filtered photos
    return filtered_photos[:limit]

def get_orientation(width, height):
    """Determine orientation based on image dimensions."""
    ratio = width / height
    
    if ratio > 1.1:  # Wider than tall
        return "landscape"
    elif ratio < 0.9:  # Taller than wide
        return "portrait"
    else:  # Approximately square
        return "square"

async def inspect_photo_metadata(query="nature", orientation="landscape"):
    """
    Utility function to inspect metadata of photos from Pexels API.
    Useful for development and debugging.
    """
    photos = await search_for_stock_photos(
        limit=3,
        query=query,
        orientation=orientation
    )
    
    if not photos:
        logger.info(f"No photos found for query '{query}'")
        return
    
    logger.info(f"Found {len(photos)} photos for query '{query}'")
    for i, photo in enumerate(photos):
        logger.info(f"Photo {i+1}:")
        logger.info(f"  ID: {photo.get('id')}")
        logger.info(f"  Photographer: {photo.get('photographer')}")
        logger.info(f"  Width x Height: {photo.get('width')} x {photo.get('height')}")
        logger.info(f"  URL: {photo.get('url')}")
        logger.info(f"  Photo sizes available:")
        for size_name, size_data in photo.get('src', {}).items():
            logger.info(f"    {size_name}: {size_data}")
        logger.info("---")