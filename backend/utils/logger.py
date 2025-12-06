"""Logging utilities."""
import logging
import sys
import os
from typing import Optional


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Get a configured logger instance."""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        
        # Use DEBUG level if DEBUG env var is set, otherwise INFO
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        default_level = logging.DEBUG if log_level == "DEBUG" else logging.INFO
        
        # Enhanced formatter with more details
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    # Set level from parameter or environment
    if level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        level = logging.DEBUG if log_level == "DEBUG" else logging.INFO
    
    logger.setLevel(level)
    return logger

