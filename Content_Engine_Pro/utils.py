"""
utils.py — Utility functions for Content Engine Pro.

Provides logging setup, timing decorators, and helper functions
for consistent error handling throughout the application.
"""

import logging
import time
from functools import wraps
from typing import Any, Callable


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging for the application.

    Sets up a consistent logging format with timestamps, levels,
    and module names.

    Args:
        level: Logging level (default: logging.INFO).
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def log_api_call(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to log API call duration and basic stats.

    Wraps any function to log:
    - Function name
    - Execution duration
    - Success/failure status

    Args:
        func: The function to wrap.

    Returns:
        Wrapped function with logging.
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger = logging.getLogger(func.__module__)
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(
                "%s completed in %.2f seconds",
                func.__name__, duration,
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "%s failed after %.2f seconds: %s",
                func.__name__, duration, e,
            )
            raise
    return wrapper


def safe_execute(
    func: Callable[..., Any],
    default_return: Any = None,
    error_message: str = "Operation failed",
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Safely execute a function with error handling.

    Catches all exceptions and returns a default value instead of crashing.

    Args:
        func: Function to execute.
        default_return: Value to return on failure.
        error_message: Custom error message for logging.
        *args: Positional arguments for func.
        **kwargs: Keyword arguments for func.

    Returns:
        Function result or default_return on failure.
    """
    logger = logging.getLogger(func.__module__)
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error("%s: %s", error_message, e)
        return default_return


def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text to a maximum length with ellipsis.

    Args:
        text: Text to truncate.
        max_length: Maximum character length.

    Returns:
        Truncated text string.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."