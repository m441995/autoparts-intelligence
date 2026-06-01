"""
AutoParts Intelligence Platform
src/utils/logger.py

Production-grade structured logging via loguru.
"""
from __future__ import annotations

import sys
from loguru import logger
from src.utils.config import config

# Remove default handler
logger.remove()

# Console handler with color
logger.add(
    sys.stdout,
    level=config.log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
           "<level>{message}</level>",
    colorize=True,
)

# File handler — rotating daily, keep 30 days
logger.add(
    config.paths.logs / "autoparts_{time:YYYY-MM-DD}.log",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    rotation="00:00",
    retention="30 days",
    compression="zip",
    enqueue=True,   # Thread-safe async writing
)

__all__ = ["logger"]
