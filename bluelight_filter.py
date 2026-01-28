#!/usr/bin/env python3
"""
Blue-light filter for night/morning hours.

This module provides functionality to:
- Get sunrise/sunset times for Stockholm
- Determine if current time is during "night" hours
- Apply a warm blue-light filter to images
"""

from datetime import UTC, datetime

from astral import LocationInfo
from astral.sun import sun
from PIL import Image

# Stockholm location info
STOCKHOLM = LocationInfo("Stockholm", "Sweden", "Europe/Stockholm", 59.3293, 18.0686)


def get_sun_times(date=None):
    """
    Get sunrise and sunset times for Stockholm.

    Args:
        date: Optional date object. Defaults to today.

    Returns:
        dict with 'sunrise' and 'sunset' as timezone-aware datetime objects
    """
    if date is None:
        date = datetime.now(UTC).date()

    s = sun(STOCKHOLM.observer, date=date, tzinfo=STOCKHOLM.timezone)
    return {
        "sunrise": s["sunrise"],
        "sunset": s["sunset"],
        "dawn": s["dawn"],  # Civil dawn (sun 6° below horizon)
        "dusk": s["dusk"],  # Civil dusk (sun 6° below horizon)
    }


def is_night_time(now=None):
    """
    Check if the current time is during night hours (before dawn or after dusk).

    Uses civil twilight (sun 6° below horizon) as the threshold.

    Args:
        now: Optional datetime. Defaults to current time.

    Returns:
        bool: True if it's night time, False otherwise
    """
    if now is None:
        now = datetime.now(STOCKHOLM.tzinfo)
    elif now.tzinfo is None:
        # Assume Stockholm timezone if no timezone provided
        now = now.replace(tzinfo=STOCKHOLM.tzinfo)

    sun_times = get_sun_times(now.date())

    # Night time is before dawn or after dusk
    return now < sun_times["dawn"] or now > sun_times["dusk"]


def apply_bluelight_filter(image, intensity=0.3):
    """
    Apply a blue-light filter (warm/orange tint) to an image.

    This reduces blue light and adds warmth, similar to night mode on devices.

    Args:
        image: PIL Image (RGB or RGBA)
        intensity: Filter strength from 0.0 (none) to 1.0 (maximum). Default 0.3.

    Returns:
        PIL Image with the filter applied
    """
    if intensity <= 0:
        return image

    intensity = min(intensity, 1.0)

    # Convert to RGBA if needed
    original_mode = image.mode
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    # Split into channels
    r, g, b, a = image.split()

    # Blue-light filter adjustments:
    # - Reduce blue channel
    # - Slightly reduce green
    # - Slightly boost red (warmth)

    # Calculate adjustment factors based on intensity
    blue_reduction = int(60 * intensity)  # Max 60 points reduction
    green_reduction = int(20 * intensity)  # Max 20 points reduction
    red_boost = int(15 * intensity)  # Max 15 points boost

    # Apply adjustments using point operations
    r = r.point(lambda x: min(255, x + red_boost))
    g = g.point(lambda x: max(0, x - green_reduction))
    b = b.point(lambda x: max(0, x - blue_reduction))

    # Merge channels back
    result = Image.merge("RGBA", (r, g, b, a))

    # Convert back to original mode if needed
    if original_mode == "RGB":
        result = result.convert("RGB")

    return result


def maybe_apply_bluelight_filter(image, intensity=0.3, force=None):
    """
    Apply blue-light filter based on time or force setting.

    Args:
        image: PIL Image (RGB or RGBA)
        intensity: Filter strength from 0.0 to 1.0. Default 0.3.
        force: If True, always apply filter. If False, never apply. If None, check time.

    Returns:
        PIL Image (filtered if night time or forced, unchanged otherwise)
    """
    should_apply = force if force is not None else is_night_time()

    if should_apply:
        if force is None:
            print("Night time detected in Stockholm - applying blue-light filter")
        return apply_bluelight_filter(image, intensity)
    return image


if __name__ == "__main__":
    # Debug: print current sun times and night status
    sun_times = get_sun_times()
    now = datetime.now(STOCKHOLM.tzinfo)

    print(f"Current time in Stockholm: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Dawn:    {sun_times['dawn'].strftime('%H:%M:%S')}")
    print(f"Sunrise: {sun_times['sunrise'].strftime('%H:%M:%S')}")
    print(f"Sunset:  {sun_times['sunset'].strftime('%H:%M:%S')}")
    print(f"Dusk:    {sun_times['dusk'].strftime('%H:%M:%S')}")
    print(f"Is night time: {is_night_time()}")
