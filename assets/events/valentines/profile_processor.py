#!/usr/bin/env python3
"""
Generic overlay profile processor for seasonal events.

Uses OpenCV Haar Cascade for face detection to position overlays
(hats, ears, crowns, etc.) on employee profile pictures. This processor
is loaded by the event system when the event is active.

Required interface:
- process(image: PIL.Image, config: dict) -> PIL.Image
"""

import os

import cv2
import numpy as np
from PIL import Image

# Directory where this processor lives
PROCESSOR_DIR = os.path.dirname(os.path.abspath(__file__))

# OpenCV's bundled Haar cascade for frontal face detection
HAAR_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

# Module-level cache for overlay image
_overlay_cache = None


def _get_overlay_image(config):
    """Load and cache the overlay PNG image."""
    global _overlay_cache
    if _overlay_cache is not None:
        return _overlay_cache

    overlay_file = config.get("file", "overlay.png")
    overlay_path = os.path.join(PROCESSOR_DIR, overlay_file)

    if not os.path.exists(overlay_path):
        print(f"Warning: Overlay image not found at {overlay_path}")
        return None

    _overlay_cache = Image.open(overlay_path).convert("RGBA")
    return _overlay_cache


def _detect_face(image_array, config):
    """
    Detect the largest face in an image using Haar Cascade.

    Args:
        image_array: numpy array (BGR format from OpenCV)
        config: dict with detection parameters

    Returns:
        tuple (x, y, width, height) of the largest detected face, or None
    """
    if not os.path.exists(HAAR_CASCADE_PATH):
        print(f"Warning: Haar cascade not found at {HAAR_CASCADE_PATH}")
        return None

    face_cascade = cv2.CascadeClassifier(HAAR_CASCADE_PATH)
    gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)

    min_neighbors = config.get("min_neighbors", 5)
    scale_factor = config.get("detection_scale", 1.1)

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=scale_factor,
        minNeighbors=min_neighbors,
        minSize=(30, 30),
    )

    if len(faces) == 0:
        return None

    # Return the largest face (by area)
    largest_face = max(faces, key=lambda f: f[2] * f[3])
    return tuple(largest_face)


def _add_overlay(profile_image, overlay, face_rect, config):
    """
    Overlay decoration on a profile image (for HTML use).

    Args:
        profile_image: PIL Image (RGBA)
        overlay: PIL Image (RGBA) of overlay decoration
        face_rect: tuple (x, y, width, height) of detected face
        config: dict with positioning parameters

    Returns:
        PIL Image with overlay
    """
    scale_factor = config.get("scale_factor", 1.3)
    vertical_offset = config.get("vertical_offset", 0.0)
    horizontal_offset = config.get("horizontal_offset", 0.0)

    face_x, face_y, face_w, face_h = face_rect

    # Scale overlay to match face width
    overlay_width = int(face_w * scale_factor)
    overlay_height = int(overlay.height * (overlay_width / overlay.width))

    overlay_resized = overlay.resize((overlay_width, overlay_height), Image.Resampling.LANCZOS)

    # Position overlay above the face
    overlay_x = int(face_x + (face_w - overlay_width) / 2 + face_w * horizontal_offset)
    overlay_y = int(face_y - overlay_height + face_h * vertical_offset)

    # Clip to image bounds for HTML (overlay will be cropped if extends above)
    overlay_x = max(0, min(overlay_x, profile_image.width - overlay_width))
    overlay_y = max(0, overlay_y)

    result = profile_image.copy()
    result.paste(overlay_resized, (overlay_x, overlay_y), overlay_resized)

    return result


def get_hat_overlay_params(profile_pic_path, canvas_position, canvas_pic_size, config):
    """
    Calculate parameters for drawing an overlay on a canvas.

    Uses face detection on the original profile picture to determine
    overlay size and position.

    Args:
        profile_pic_path: path to the original profile picture
        canvas_position: tuple (x, y) center position of profile pic on canvas
        canvas_pic_size: tuple (width, height) of profile pic as displayed on canvas
        config: dict with overlay configuration

    Returns:
        dict with hat_image, hat_x, hat_y for drawing on canvas, or None
    """
    overlay = _get_overlay_image(config)
    if overlay is None:
        return None

    # Load and detect face in original image
    try:
        img = Image.open(profile_pic_path).convert("RGBA")
    except OSError:
        return None

    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGBA2BGR)
    face_rect = _detect_face(img_cv, config)

    if face_rect is None:
        return None

    face_x, face_y, face_w, face_h = face_rect
    orig_w, orig_h = img.size
    canvas_w, canvas_h = canvas_pic_size
    center_x, center_y = canvas_position

    # Scale factor from original image to canvas
    scale_x = canvas_w / orig_w
    scale_y = canvas_h / orig_h

    # Scale face dimensions to canvas coordinates
    canvas_face_w = face_w * scale_x
    canvas_face_h = face_h * scale_y
    canvas_face_x = face_x * scale_x
    canvas_face_y = face_y * scale_y

    # Overlay size based on detected face width
    overlay_scale = config.get("scale_factor", 1.0)
    vertical_offset = config.get("vertical_offset", 0.0)
    horizontal_offset = config.get("horizontal_offset", 0.0)

    overlay_width = int(canvas_face_w * overlay_scale)
    overlay_height = int(overlay.height * (overlay_width / overlay.width))

    overlay_resized = overlay.resize((overlay_width, overlay_height), Image.Resampling.LANCZOS)

    # Position overlay above the detected face
    # Canvas position is center of profile pic, so adjust for that
    pic_left = center_x - canvas_w // 2
    pic_top = center_y - canvas_h // 2

    # Overlay centered on face, positioned above
    face_center_x = pic_left + canvas_face_x + canvas_face_w // 2
    overlay_x = int(face_center_x - overlay_width // 2 + canvas_face_w * horizontal_offset)
    overlay_y = int(pic_top + canvas_face_y - overlay_height + canvas_face_h * vertical_offset)

    return {
        "image": overlay_resized,
        "x": overlay_x,
        "y": overlay_y,
    }


def process(image, config):
    """
    Process a profile picture, adding overlay if face detected.

    This is the main entry point called by the event system.

    Args:
        image: PIL Image (will be converted to RGBA)
        config: dict with overlay configuration from event config.json

    Returns:
        PIL Image (RGBA) with or without overlay
    """
    # Ensure RGBA mode
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    # Check if enabled
    if not config.get("enabled", True):
        return image

    # Load overlay
    overlay = _get_overlay_image(config)
    if overlay is None:
        return image

    # Convert to OpenCV format for face detection
    img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGBA2BGR)

    # Detect face
    face_rect = _detect_face(img_cv, config)
    if face_rect is None:
        # No face detected, return original
        return image

    # Add overlay
    return _add_overlay(image, overlay, face_rect, config)


def clear_cache():
    """Clear module-level caches. Useful for testing."""
    global _overlay_cache
    _overlay_cache = None
