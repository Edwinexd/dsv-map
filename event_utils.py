#!/usr/bin/env python3
"""
Event utilities for loading and processing seasonal events.

This module handles:
- Loading active events based on current date
- Dynamically loading profile processors from event folders
- Processing profile pictures through active event processors
"""

import importlib.util
import json
import os
from datetime import date

from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS_DIR = os.path.join(SCRIPT_DIR, "assets", "events")

# Cache for loaded processors
_processor_cache = {}
_active_events_cache = None


def _is_event_active(config):
    """Check if an event is active based on its date range."""
    today = date.today()
    current = (today.month, today.day)

    start = (config.get("start_month"), config.get("start_day"))
    end = (config.get("end_month"), config.get("end_day"))

    if None in start or None in end:
        return False

    # Handle date ranges that don't wrap around year
    if start <= end:
        return start <= current <= end
    # Handle year-wrapping ranges (e.g., Dec 15 - Jan 5)
    return current >= start or current <= end


def get_active_events():
    """
    Get all currently active events.

    Returns:
        list of tuples: [(event_name, event_path, config), ...]
    """
    global _active_events_cache
    if _active_events_cache is not None:
        return _active_events_cache

    active_events = []

    if not os.path.isdir(EVENTS_DIR):
        _active_events_cache = active_events
        return active_events

    for event_name in os.listdir(EVENTS_DIR):
        event_path = os.path.join(EVENTS_DIR, event_name)
        config_path = os.path.join(event_path, "config.json")

        if not os.path.isfile(config_path):
            continue

        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        if _is_event_active(config):
            active_events.append((event_name, event_path, config))

    _active_events_cache = active_events
    return active_events


def _load_processor(event_path, processor_file):
    """Dynamically load a processor module from an event folder."""
    processor_path = os.path.join(event_path, processor_file)

    if not os.path.isfile(processor_path):
        print(f"Warning: Processor not found at {processor_path}")
        return None

    # Use cache if already loaded
    if processor_path in _processor_cache:
        return _processor_cache[processor_path]

    # Dynamically load the module
    spec = importlib.util.spec_from_file_location("event_processor", processor_path)
    if spec is None or spec.loader is None:
        print(f"Warning: Could not load processor spec from {processor_path}")
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Verify it has the required interface
    if not hasattr(module, "process"):
        print(f"Warning: Processor at {processor_path} missing 'process' function")
        return None

    _processor_cache[processor_path] = module
    return module


def get_profile_processor():
    """
    Get the profile processor from active events (if any).

    Returns:
        tuple: (processor_module, config) or (None, None) if no active processor
    """
    active_events = get_active_events()

    for _event_name, event_path, config in active_events:
        processor_file = config.get("profile_processor")
        if processor_file:
            processor = _load_processor(event_path, processor_file)
            if processor:
                processor_config = config.get("profile_processor_config", {})
                return processor, processor_config

    return None, None


def process_profile_picture(pic_path, target_size=None):
    """
    Process a profile picture through active event processors.

    Args:
        pic_path: Path to the profile picture
        target_size: Optional tuple (width, height) to resize the result

    Returns:
        PIL Image (RGBA) or None if loading failed
    """
    # Load the image
    try:
        img = Image.open(pic_path).convert("RGBA")
    except OSError as e:
        print(f"Warning: Could not load {pic_path}: {e}")
        return None

    # Get active processor
    processor, config = get_profile_processor()

    if processor:
        img = processor.process(img, config)

    # Resize if requested
    if target_size:
        img = img.resize(target_size, Image.Resampling.LANCZOS)

    return img


def has_active_profile_processor():
    """Check if there's an active event with a profile processor."""
    processor, _ = get_profile_processor()
    return processor is not None


def get_tv_overlay_params(profile_pic_path, canvas_position, canvas_pic_size):
    """
    Get overlay parameters for TV rendering (e.g., Santa hats).

    Args:
        profile_pic_path: path to the original profile picture
        canvas_position: tuple (x, y) center position on canvas
        canvas_pic_size: tuple (width, height) of profile pic as displayed

    Returns:
        dict with overlay info, or None if no active overlay
    """
    processor, config = get_profile_processor()
    if processor is None:
        return None

    # Check if processor has overlay support
    if not hasattr(processor, "get_hat_overlay_params"):
        return None

    return processor.get_hat_overlay_params(
        profile_pic_path, canvas_position, canvas_pic_size, config
    )


def clear_cache():
    """Clear all caches. Useful for testing."""
    global _processor_cache, _active_events_cache
    _processor_cache = {}
    _active_events_cache = None
