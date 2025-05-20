"""Tests for cache module."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from subburn.cache import (
    CACHE_DIR,
    cached,
    compute_cache_key,
    compute_content_hash,
    ensure_cache_dir,
    get_cache_path,
    load_from_cache,
    save_to_cache,
    serialize_value,
)


class TestCacheUtils:
    """Test cache utility functions."""

    def test_compute_content_hash(self) -> None:
        """Test hash computation from string content."""
        # Same content should produce same hash
        assert compute_content_hash("test content") == compute_content_hash("test content")
        # Different content should produce different hash
        assert compute_content_hash("test content") != compute_content_hash("other content")
        # Empty content should have consistent hash
        assert compute_content_hash("") == compute_content_hash("")

    def test_serialize_value(self) -> None:
        """Test serialization of various value types."""
        # Basic types
        assert serialize_value(None) is None
        assert serialize_value(123) == 123
        assert serialize_value("test") == "test"
        assert serialize_value(True) is True
        
        # Lists and tuples
        assert serialize_value([1, 2, 3]) == [1, 2, 3]
        assert serialize_value((1, 2, 3)) == [1, 2, 3]  # Tuple converted to list
        
        # Dictionaries
        assert serialize_value({"a": 1, "b": 2}) == {"a": 1, "b": 2}
        
        # Nested structures
        assert serialize_value({"a": [1, 2], "b": {"c": 3}}) == {"a": [1, 2], "b": {"c": 3}}
        
        # Pydantic model
        class TestModel(BaseModel):
            field1: str
            field2: int
        
        model = TestModel(field1="test", field2=42)
        assert serialize_value(model) == {"field1": "test", "field2": 42}
        
        # Object with __dict__
        class TestClass:
            def __init__(self) -> None:
                self.attr1 = "value1"
                self.attr2 = 123
        
        obj = TestClass()
        assert serialize_value(obj) == {"attr1": "value1", "attr2": 123}

    def test_compute_cache_key(self) -> None:
        """Test cache key computation."""
        # Same parameters should produce same key
        key1 = compute_cache_key(param1="value1", param2=123)
        key2 = compute_cache_key(param1="value1", param2=123)
        assert key1 == key2
        
        # Different parameters should produce different keys
        key3 = compute_cache_key(param1="value2", param2=123)
        assert key1 != key3
        
        # Order shouldn't matter
        key4 = compute_cache_key(param2=123, param1="value1")
        assert key1 == key4
        
        # Complex parameters
        key5 = compute_cache_key(list_param=[1, 2, 3], dict_param={"a": 1})
        key6 = compute_cache_key(list_param=[1, 2, 3], dict_param={"a": 1})
        assert key5 == key6

    @patch("subburn.cache.ensure_cache_dir")
    def test_get_cache_path(self, mock_ensure_cache_dir) -> None:
        """Test cache path generation."""
        mock_ensure_cache_dir.return_value = Path("/tmp/cache")
        
        # Check that paths are correctly constructed
        path = get_cache_path("test_type", "test_key")
        assert path == Path("/tmp/cache/test_type_test_key.json")
        
        # Check that ensure_cache_dir is called
        mock_ensure_cache_dir.assert_called_once()

    @patch("pathlib.Path.mkdir")
    def test_ensure_cache_dir(self, mock_mkdir) -> None:
        """Test cache directory creation."""
        ensure_cache_dir()
        
        # Check that mkdir was called with correct parameters
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_save_and_load_from_cache(self) -> None:
        """Test saving to and loading from cache."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Patch the cache directory to use the temporary directory
            with patch("subburn.cache.CACHE_DIR", Path(temp_dir)):
                # Ensure the cache directory exists
                ensure_cache_dir()
                
                # Test data
                cache_type = "test_type"
                cache_key = "test_key"
                test_data = {"field1": "value1", "field2": 123}
                
                # Save to cache
                save_to_cache(cache_type, cache_key, test_data)
                
                # Check that the file was created
                cache_path = get_cache_path(cache_type, cache_key)
                assert cache_path.exists()
                
                # Verify file contents
                with open(cache_path, encoding="utf-8") as f:
                    saved_data = json.load(f)
                assert saved_data == test_data
                
                # Load from cache
                loaded_data = load_from_cache(cache_type, cache_key)
                assert loaded_data == test_data
                
                # Test loading non-existent cache
                non_existent = load_from_cache(cache_type, "non_existent_key")
                assert non_existent is None


class TestCachedDecorator:
    """Test the @cached decorator."""
    
    @patch("subburn.cache.load_from_cache")
    @patch("subburn.cache.save_to_cache")
    def test_cached_decorator_with_simple_function(self, mock_save, mock_load) -> None:
        """Test @cached decorator with a simple function."""
        # Set up the mock to return None (cache miss)
        mock_load.return_value = None
        
        # Define a simple function to cache
        @cached(cache_type="test")
        def sample_function(a: int, b: int) -> int:
            """Sample function that adds two numbers."""
            return a + b
        
        # Call the function
        result = sample_function(2, 3)
        
        # Verify the function was called and returned the correct result
        assert result == 5
        
        # Check that cache was not saved (no cache_processor provided)
        mock_save.assert_not_called()
        
        # Call with the same parameters again
        sample_function(2, 3)
        
        # Verify load_from_cache was called both times
        assert mock_load.call_count == 2
    
    @patch("subburn.cache.load_from_cache")
    @patch("subburn.cache.save_to_cache")
    def test_cached_decorator_with_cache_processor(self, mock_save, mock_load) -> None:
        """Test @cached decorator with cache processor."""
        # Set up the mock to return None (cache miss)
        mock_load.return_value = None
        
        # Define a cache processor
        def cache_processor(result: int) -> dict:
            return {"result": result}
        
        # Define a function with cache processor
        @cached(cache_type="test", cache_processor=cache_processor)
        def sample_function(a: int, b: int) -> int:
            """Sample function that adds two numbers."""
            return a + b
        
        # Call the function
        result = sample_function(2, 3)
        
        # Verify the function returned the correct result
        assert result == 5
        
        # Check that the result was processed and cached
        mock_save.assert_called_once()
        call_args = mock_save.call_args
        assert call_args[0][0] == "test"  # cache_type
        assert call_args[0][2] == {"result": 5}  # processed data
    
    @patch("subburn.cache.load_from_cache")
    def test_cached_decorator_with_cache_hit(self, mock_load) -> None:
        """Test @cached decorator with cache hit."""
        # Sample function to test
        @cached(cache_type="test")
        def sample_function(a: int, b: int) -> int:
            """Sample function."""
            return a + b
        
        # First call - set up mock to return None (cache miss)
        mock_load.return_value = None
        result1 = sample_function(2, 3)
        assert result1 == 5  # Returns actual function result
        
        # Now set up a cache hit
        mock_load.return_value = {"result": 42}
        result2 = sample_function(2, 3)
        
        # Verify the returned result matches the cache
        assert result2 == {"result": 42}
        
        # Verify load_from_cache was called twice
        assert mock_load.call_count == 2
    
    @patch("subburn.cache.load_from_cache")
    @patch("subburn.cache.save_to_cache")
    def test_cached_decorator_with_disabled_cache(self, mock_save, mock_load) -> None:
        """Test disabling the cache with cached=False parameter."""
        # Define a function that can be called with caching disabled
        @cached(cache_type="test")
        def sample_function(a: int, b: int, cached: bool = True) -> int:
            """Sample function with cache disable option."""
            return a + b
        
        # Call the function with caching disabled
        result = sample_function(2, 3, cached=False)
        
        # Verify the function returned the correct result
        assert result == 5
        
        # Check that cache was not accessed or saved
        mock_load.assert_not_called()
        mock_save.assert_not_called()
    
    @patch("subburn.cache.load_from_cache")
    def test_cached_decorator_with_validation(self, mock_load) -> None:
        """Test @cached decorator with schema validation."""
        # Define a schema
        class ResultSchema(BaseModel):
            result: int
        
        # Set up the mock to return invalid data
        mock_load.return_value = {"wrong_field": "invalid"}
        
        call_count = [0]
        
        # Define a function with schema validation
        @cached(cache_type="test", cache_schema=ResultSchema)
        def sample_function(a: int, b: int) -> int:
            """Sample function with schema validation."""
            call_count[0] += 1
            return a + b
        
        # Call the function - should execute the function due to validation failure
        result = sample_function(2, 3)
        
        # Verify the function returned the correct result
        assert result == 5
        assert call_count[0] == 1
        
        # Now set up the mock to return valid data
        mock_load.return_value = {"result": 42}
        
        # Call again - should return the cached value
        result = sample_function(2, 3)
        assert result == {"result": 42}  # Returns the full cache data
        assert call_count[0] == 1  # Function not called again
    
    @patch("subburn.cache.load_from_cache")
    def test_cached_decorator_with_key_generator(self, mock_load) -> None:
        """Test @cached decorator with key generator."""
        # Set up the mock to return a cache hit
        mock_load.return_value = {"result": 42}
        
        # Define a key generator
        def key_generator(**kwargs) -> dict:
            return {"extra_key": "value"}
        
        # Define a function with key generator
        @cached(
            cache_type="test",
            key_generator=key_generator,
        )
        def sample_function(a: int, b: int) -> int:
            """Sample function with key generator."""
            return a + b
        
        # Call the function
        result = sample_function(2, 3)
        
        # Verify the cache was loaded with the right key
        mock_load.assert_called_once()
        
        # Verify the result matches the cache
        assert result == {"result": 42}