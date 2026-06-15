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
from astral.sun import dawn, dusk, elevation, sunrise, sunset
from PIL import Image

# Stockholm location info
STOCKHOLM = LocationInfo("Stockholm", "Sweden", "Europe/Stockholm", 59.3293, 18.0686)

# Civil twilight threshold: sun this many degrees below the horizon counts as night
CIVIL_TWILIGHT_DEPRESSION = 6.0


def get_sun_times(date=None):
    """
    Get sunrise and sunset times for Stockholm.

    Args:
        date: Optional date object. Defaults to today.

    Returns:
        dict with 'sunrise'/'sunset' and 'dawn'/'dusk' as timezone-aware
        datetime objects. dawn/dusk are None during white nights / polar day
        when the sun never reaches civil twilight depression.
    """
    if date is None:
        date = datetime.now(UTC).date()

    def safe(func):
        # astral raises ValueError when the sun never reaches the required angle
        # (e.g. Stockholm white nights have no civil dawn/dusk).
        try:
            return func(STOCKHOLM.observer, date=date, tzinfo=STOCKHOLM.timezone)
        except ValueError:
            return None

    return {
        "sunrise": safe(sunrise),
        "sunset": safe(sunset),
        "dawn": safe(dawn),  # Civil dawn (sun 6° below horizon)
        "dusk": safe(dusk),  # Civil dusk (sun 6° below horizon)
    }


def is_night_time(now=None):
    """
    Check if the current time is during night hours.

    Night is defined as the sun being more than 6° below the horizon (civil
    twilight). This uses the sun's elevation directly rather than dawn/dusk
    events, so it works year-round including Stockholm's white nights, when the
    sun never reaches civil twilight depression and astral's dawn()/dusk()
    raise "Unable to find a dawn time on the date specified".

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

    return elevation(STOCKHOLM.observer, now) < -CIVIL_TWILIGHT_DEPRESSION


def apply_bluelight_filter(image, intensity=0.6):
    """
    Apply a blue-light filter (warm/orange tint) to an image.

    This reduces blue light and adds warmth, similar to night mode on devices.

    Args:
        image: PIL Image (RGB or RGBA)
        intensity: Filter strength from 0.0 (none) to 1.0 (maximum). Default 0.6.

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

    # Blue-light filter adjustments for warm yellow/orange tint:
    # - Strongly reduce blue channel
    # - Moderately reduce green
    # - Boost red (warmth)

    # Calculate adjustment factors based on intensity
    blue_reduction = int(120 * intensity)  # Max 120 points reduction
    green_reduction = int(40 * intensity)  # Max 40 points reduction
    red_boost = int(35 * intensity)  # Max 35 points boost

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


def maybe_apply_bluelight_filter(image, intensity=0.6, force=None):
    """
    Apply blue-light filter based on time or force setting.

    Args:
        image: PIL Image (RGB or RGBA)
        intensity: Filter strength from 0.0 to 1.0. Default 0.6.
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

    def fmt(value):
        return value.strftime("%H:%M:%S") if value is not None else "n/a (white night)"

    print(f"Current time in Stockholm: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Dawn:    {fmt(sun_times['dawn'])}")
    print(f"Sunrise: {fmt(sun_times['sunrise'])}")
    print(f"Sunset:  {fmt(sun_times['sunset'])}")
    print(f"Dusk:    {fmt(sun_times['dusk'])}")
    print(f"Sun elevation now: {elevation(STOCKHOLM.observer, now):.2f}°")
    print(f"Is night time: {is_night_time()}")
