"""Generic cache utilities for subburn."""

import functools
import hashlib
import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, TypeVar, cast

from pydantic import BaseModel, ValidationError
from xdg_base_dirs import xdg_cache_home


class Serializable(Protocol):
    """Protocol for objects that can be serialized."""

    __dict__: dict[str, Any]


class HasToDict(Protocol):
    """Protocol for objects that have a to_dict method."""

    def to_dict(self) -> dict[str, Any]: ...


# Create cache directory path
CACHE_DIR = xdg_cache_home() / "subburn"

# Type variables for the decorator
T = TypeVar("T")
R = TypeVar("R")


def ensure_cache_dir() -> Path:
    """Ensure the cache directory exists and return its path."""
    cache_dir = CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def compute_content_hash(content: str) -> str:
    """Compute a hash of the content."""
    return hashlib.sha256(content.encode()).hexdigest()


def serialize_value(value: Any) -> Any:
    """Serialize a value to a form that can be reliably hashed."""
    # Handle None
    if value is None:
        return None

    # Handle basic types
    if isinstance(value, str | int | float | bool):
        return value

    # Handle lists and tuples
    if isinstance(value, list | tuple):
        return [serialize_value(item) for item in value]

    # Handle dictionaries
    if isinstance(value, dict):
        return {k: serialize_value(v) for k, v in sorted(value.items())}

    # Handle pydantic models
    if isinstance(value, BaseModel):
        return value.model_dump()

    # Handle objects with to_dict method
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()

    # Handle objects with __dict__ attribute
    if hasattr(value, "__dict__"):
        return serialize_value(value.__dict__)

    # Handle any other object by converting to string
    return str(value)


def compute_cache_key(**kwargs: Any) -> str:
    """Compute a cache key based on parameters.

    Args:
        **kwargs: Parameters to include in the hash

    Returns:
        A hash string to use as the cache key
    """
    # Serialize all parameters
    serialized_params = {k: serialize_value(v) for k, v in kwargs.items()}

    # Convert to a deterministic JSON string
    param_str = json.dumps(serialized_params, sort_keys=True)

    # Hash the string
    return compute_content_hash(param_str)


def get_cache_path(cache_type: str, cache_key: str) -> Path:
    """Get the path to a cache file.

    Args:
        cache_type: Type of cache (e.g., "translation")
        cache_key: Cache key

    Returns:
        Path to the cache file
    """
    cache_dir = ensure_cache_dir()
    return cache_dir / f"{cache_type}_{cache_key}.json"


def save_to_cache(cache_type: str, cache_key: str, data: dict[str, Any]) -> None:
    """Save data to cache file.

    Args:
        cache_type: Type of cache (e.g., "translation")
        cache_key: Cache key
        data: Data to cache
    """
    cache_path = get_cache_path(cache_type, cache_key)

    # Write to cache file
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_from_cache(cache_type: str, cache_key: str) -> dict[str, Any] | None:
    """Load data from cache file.

    Args:
        cache_type: Type of cache (e.g., "translation")
        cache_key: Cache key

    Returns:
        Cached data, or None if no cache exists or error occurs
    """
    cache_path = get_cache_path(cache_type, cache_key)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, encoding="utf-8") as f:
            cache_data = json.load(f)

        return cache_data
    except (json.JSONDecodeError, OSError):
        # If there's an error reading the cache, ignore it
        return None


def cached(
    cache_type: str,
    cache_schema: type[BaseModel] | None = None,
    key_generator: Callable[..., dict[str, Any]] | None = None,
    result_processor: Callable[[Any, dict[str, Any]], Any] | None = None,
    cache_processor: Callable[[Any], dict[str, Any]] | None = None,
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """Decorator for caching function results.

    Args:
        cache_type: Type of cache (e.g., "translation")
        cache_schema: Optional pydantic model to validate cache data
        key_generator: Optional function to generate additional key parameters
        result_processor: Optional function to process the result with cache data
        cache_processor: Optional function to process the result before caching

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> R:
            # Get the parameters
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            # Check if caching is disabled via parameter
            if "cached" in bound.arguments and bound.arguments["cached"] is False:
                # Call the original function without caching
                return func(*args, **kwargs)

            # Build cache key parameters from all function arguments
            cache_key_params = {**bound.arguments}

            # Remove 'cached' flag from cache key parameters if present
            cache_key_params.pop("cached", None)

            # Add generated key params if a generator function is provided
            if key_generator:
                generated_params = key_generator(**bound.arguments)
                cache_key_params.update(generated_params)

            # Compute cache key from all parameters
            cache_key = compute_cache_key(**cache_key_params)

            # Try to load from cache
            cache_data = load_from_cache(cache_type, cache_key)

            # Check if we have valid cache data
            if cache_data is not None:
                # Validate the cache data if a cache schema is provided
                if cache_schema is not None:
                    try:
                        # Validate cache data against the schema
                        validated_data = cache_schema(**cache_data)
                        # Convert back to dict
                        cache_data = validated_data.model_dump()
                    except ValidationError:
                        # If validation fails, ignore the cache and call the original function
                        cache_data = None

                if cache_data is not None:
                    # Process the result with cache data if needed
                    if result_processor:
                        # Get the original return value by calling the function
                        result = func(*args, **kwargs)
                        # Process the result with cache data
                        return result_processor(result, cache_data)
                    else:
                        # Return the cache data as the result
                        return cast(R, cache_data)

            # If no cache or invalid cache, call the original function
            result = func(*args, **kwargs)

            # Process and cache the result if needed
            if cache_processor:
                cache_data = cache_processor(result)
                save_to_cache(cache_type, cache_key, cache_data)

            return result

        return wrapper

    return decorator
