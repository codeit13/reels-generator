"""CSV Logger that writes to single consolidated files."""
import os
import csv
import datetime
import threading
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

class ConsolidatedCSVLogger:
    """Logger that appends all entries to single consolidated CSV files."""

    def __init__(self, log_dir: str = "tmp/logs"):
        """Initialize the logger with the log directory."""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initializing ConsolidatedCSVLogger in directory: {self.log_dir}")

        self.matches_file = self.log_dir / "video_matches_consolidated.csv"
        self.metrics_file = self.log_dir / "video_metrics_consolidated.csv"
        self.sentence_queries_file = self.log_dir / "sentence_queries_consolidated.csv"

        # File locks to prevent concurrent writes
        self.matches_lock = threading.Lock()
        self.metrics_lock = threading.Lock()
        self.sentence_queries_lock = threading.Lock()

        # Initialize files with headers if they don't exist
        self._init_file(self.matches_file, ["timestamp", "sentence", "search_query",
                                           "video_url", "voice_provider", "voice_name"])
        self._init_file(self.metrics_file, ["timestamp", "job_id", "step", "duration",
                                          "total_duration", "voice_provider", "voice_name"])
        self._init_file(self.sentence_queries_file, ["timestamp", "job_id", "sentence", "query"])
        logger.info("Consolidated CSV files initialized.")

    def _init_file(self, file_path: Path, headers: List[str]):
        """Initialize a CSV file with headers if it doesn't exist."""
        if not file_path.exists() or file_path.stat().st_size == 0:
            try:
                with open(file_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                logger.info(f"Initialized CSV file with headers: {file_path}")
            except IOError as e:
                logger.error(f"Failed to initialize CSV file {file_path}: {e}")

    def log_match(self, sentence: str, search_query: str, video_url: str,
                 voice_provider: str, voice_name: str):
        """Log a video match entry."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.matches_lock:
            try:
                with open(self.matches_file, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([timestamp, sentence, search_query, video_url,
                                   voice_provider, voice_name])
                logger.trace(f"Logged match to {self.matches_file}")
            except IOError as e:
                logger.error(f"Error writing match to CSV {self.matches_file}: {e}")

    def log_metric(self, job_id: str, step: str, duration: float,
                 total_duration: float, voice_provider: str, voice_name: str):
        """Log a performance metric entry."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.metrics_lock:
            try:
                with open(self.metrics_file, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([timestamp, job_id, step, duration,
                                   total_duration, voice_provider, voice_name])
                logger.trace(f"Logged metric to {self.metrics_file}")
            except IOError as e:
                logger.error(f"Error writing metric to CSV {self.metrics_file}: {e}")

    def log_sentence_query(self, job_id: str, sentence: str, query: str):
        """Log a sentence and its generated Pexels query."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.sentence_queries_lock:
            try:
                with open(self.sentence_queries_file, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([timestamp, job_id, sentence, query])
                logger.trace(f"Logged sentence query to {self.sentence_queries_file}")
            except IOError as e:
                logger.error(f"Error writing sentence query to CSV {self.sentence_queries_file}: {e}")

# Create a singleton instance
csv_logger = ConsolidatedCSVLogger()