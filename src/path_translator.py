#!/usr/bin/env python3
"""
Path Translator for Checkfiles Container

This script provides utility functions to translate paths between host and container
filesystems when running checkfiles in a Docker container.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def translate_host_path_to_container(host_path: str) -> Optional[str]:
    """
    Translate a host path to a container path.
    
    Args:
        host_path: Absolute path on the host system
        
    Returns:
        Corresponding path in the container filesystem, or None if translation is not possible
    """
    # Get the host home directory from environment (set in docker-compose.yml)
    host_home = os.environ.get('HOST_HOME')
    
    if not host_home:
        logger.warning("HOST_HOME environment variable not set, cannot translate host paths")
        return None
    
    # Check if the path starts with the host home directory
    if host_path.startswith(host_home):
        # Direct mapping through volume mount
        return host_path
    
    # Check if the path is within the project directory structure
    project_root = "/app"
    
    # Common paths that might be mapped in the container
    path_mappings = [
        # Format: (host_path_pattern, container_prefix)
        (r"/src/", f"{project_root}/src/"),
        (r"/test_data/", f"{project_root}/test_data/"),
        (r"/logs/", f"{project_root}/logs/"),
        # Add more mappings as needed
    ]
    
    for pattern, prefix in path_mappings:
        if pattern in host_path:
            # Extract the part after the pattern
            parts = host_path.split(pattern)
            if len(parts) > 1:
                return prefix + pattern.join(parts[1:])
    
    logger.warning(f"Could not translate host path: {host_path}")
    return host_path  # Return the original path as a fallback

def is_s3_uri(path: str) -> bool:
    """
    Check if a path is an S3 URI.
    
    Args:
        path: Path to check
        
    Returns:
        True if path is an S3 URI, False otherwise
    """
    return path.startswith("s3://")

def resolve_path(path: str) -> str:
    """
    Resolve a path that might be a host path, container path, or S3 URI.
    
    Args:
        path: Path to resolve (host path, container path, or S3 URI)
        
    Returns:
        Resolved path that can be used within the container
    """
    # If it's an S3 URI, no translation needed
    if is_s3_uri(path):
        return path
        
    # If it's a relative path, assume it's relative to the current directory
    if not os.path.isabs(path):
        return os.path.abspath(path)
        
    # If it's an absolute path that might be from the host system
    if os.path.isabs(path) and not os.path.exists(path):
        translated_path = translate_host_path_to_container(path)
        if translated_path and os.path.exists(translated_path):
            logger.info(f"Translated host path '{path}' to container path '{translated_path}'")
            return translated_path
            
    # Return the original path as a fallback
    return path 