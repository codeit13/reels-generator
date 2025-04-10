"""CSV Logger that writes to single consolidated files."""
import os
import csv
import datetime
import threading
from pathlib import Path
from typing import List, Dict, Any

class ConsolidatedCSVLogger:
    """Logger that appends all entries to single consolidated CSV files."""
    
    def __init__(self, log_dir: str = "tmp/logs"):
        """Initialize the logger with the log directory."""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.matches_file = self.log_dir / "video_matches_consolidated.csv"
        self.metrics_file = self.log_dir / "video_metrics_consolidated.csv"
        
        # File locks to prevent concurrent writes
        self.matches_lock = threading.Lock()
        self.metrics_lock = threading.Lock()
        
        # Initialize files with headers if they don't exist
        self._init_file(self.matches_file, ["timestamp", "sentence", "search_query", 
                                           "video_url", "voice_provider", "voice_name"])
        self._init_file(self.metrics_file, ["timestamp", "job_id", "step", "duration",
                                          "total_duration", "voice_provider", "voice_name"])
    
    def _init_file(self, file_path: Path, headers: List[str]):
        """Initialize a CSV file with headers if it doesn't exist."""
        if not file_path.exists():
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
    
    def log_match(self, sentence: str, search_query: str, video_url: str, 
                 voice_provider: str, voice_name: str):
        """Log a video match entry."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with self.matches_lock:
            with open(self.matches_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, sentence, search_query, video_url,
                               voice_provider, voice_name])
    
    def log_metric(self, job_id: str, step: str, duration: float,
                 total_duration: float, voice_provider: str, voice_name: str):
        """Log a performance metric entry."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with self.metrics_lock:
            with open(self.metrics_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, job_id, step, duration,
                               total_duration, voice_provider, voice_name])

# Create a singleton instance
csv_logger = ConsolidatedCSVLogger()