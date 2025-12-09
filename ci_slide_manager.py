#!/usr/bin/env python3
"""CI Slide Manager - Handle build-in-progress indicator for ACT Lab display.

Usage:
    python ci_slide_manager.py start   - Remove old slide from show, upload CI progress image
    python ci_slide_manager.py success - Upload new slide, remove CI progress, delete old slide
    python ci_slide_manager.py failure - Remove CI progress, restore old slide to show
"""

import argparse
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from dsv_wrapper import ACTLabClient
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

load_dotenv()

SCRIPT_DIR = Path(__file__).parent
SHOW_ID = 1
CI_PROGRESS_IMAGE = SCRIPT_DIR / "assets" / "ci-build-in-progress.png"
NEW_MAP_IMAGE = SCRIPT_DIR / "output" / "tv" / "ACT_map_tv.png"
STATE_FILE = SCRIPT_DIR / "output" / ".ci_slide_state.json"
SLIDE_NAME = "ACT Lab Map"
CI_SLIDE_NAME = "CI Build In Progress"
MAX_UPLOAD_SIZE_MB = 1.9


def save_state(old_slide_id: int | None, ci_slide_id: int | None) -> None:
    """Save slide IDs to state file for later cleanup."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {"old_slide_id": old_slide_id, "ci_slide_id": ci_slide_id}
    STATE_FILE.write_text(json.dumps(state))
    logger.info(f"Saved state: {state}")


def load_state() -> tuple[int | None, int | None]:
    """Load slide IDs from state file."""
    if not STATE_FILE.exists():
        logger.warning("No state file found")
        return None, None
    state = json.loads(STATE_FILE.read_text())
    logger.info(f"Loaded state: {state}")
    return state.get("old_slide_id"), state.get("ci_slide_id")


def cleanup_state() -> None:
    """Remove state file."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()
        logger.info("Cleaned up state file")


def upload_image(actlab: ACTLabClient, image_path: Path, slide_name: str) -> int | None:
    """Upload an image, converting to JPEG if needed for size limits."""
    if not image_path.exists():
        logger.error(f"File not found: {image_path}")
        return None

    upload_path = image_path
    temp_file = None
    file_size_mb = image_path.stat().st_size / 1024 / 1024

    if file_size_mb > MAX_UPLOAD_SIZE_MB:
        logger.info(f"File size {file_size_mb:.2f}MB exceeds limit, converting to JPEG...")
        img = Image.open(image_path)
        temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)

        for quality in [95, 90, 85, 80, 75, 70, 65, 60]:
            img.save(temp_file.name, format="JPEG", quality=quality)
            new_size_mb = Path(temp_file.name).stat().st_size / 1024 / 1024
            if new_size_mb <= MAX_UPLOAD_SIZE_MB:
                logger.info(f"Converted to JPEG (quality={quality}): {new_size_mb:.2f}MB")
                break

        upload_path = Path(temp_file.name)

    result = actlab.upload_slide(file_path=upload_path, slide_name=slide_name)

    if temp_file:
        os.unlink(temp_file.name)

    if result.success:
        logger.info(f"Uploaded {slide_name}: ID {result.slide_id}")
        return result.slide_id
    else:
        logger.error(f"Upload failed: {result.message}")
        return None


def cmd_start(actlab: ACTLabClient) -> int:
    """Start CI build: disable auto-delete on old slide, upload progress indicator."""
    logger.info("=" * 60)
    logger.info("CI Build Start - Setting up progress indicator")
    logger.info("=" * 60)

    # Find existing slides with auto_delete in the show
    existing_slides = actlab.get_slides()
    old_slides = [s for s in existing_slides if s.show_id == SHOW_ID and s.auto_delete]

    old_slide_id = None
    if old_slides:
        old_slide_id = old_slides[0].id
        logger.info(f"Found existing slide {old_slide_id}, disabling auto-delete...")
        actlab._configure_slide(old_slide_id, SHOW_ID, auto_delete=False)
        logger.info(f"Disabled auto-delete on slide {old_slide_id}")
        # Remove from show temporarily (but don't delete)
        actlab.remove_slide_from_show(old_slide_id, show_id=SHOW_ID)
        logger.info(f"Temporarily removed slide {old_slide_id} from show")

    # Upload CI progress image
    ci_slide_id = upload_image(actlab, CI_PROGRESS_IMAGE, CI_SLIDE_NAME)
    if ci_slide_id is None:
        logger.error("Failed to upload CI progress image")
        return 1

    actlab.add_slide_to_show(ci_slide_id, show_id=SHOW_ID, auto_delete=True)
    logger.info(f"Added CI progress slide {ci_slide_id} to show")

    save_state(old_slide_id, ci_slide_id)

    logger.info("=" * 60)
    logger.info("CI progress indicator active")
    logger.info("=" * 60)
    return 0


def cmd_success(actlab: ACTLabClient) -> int:
    """Build succeeded: upload new slide, remove CI progress, delete old slide."""
    logger.info("=" * 60)
    logger.info("CI Build Success - Uploading new map")
    logger.info("=" * 60)

    old_slide_id, ci_slide_id = load_state()

    # Upload new map
    new_slide_id = upload_image(actlab, NEW_MAP_IMAGE, SLIDE_NAME)
    if new_slide_id is None:
        logger.error("Failed to upload new map")
        return 1

    actlab.add_slide_to_show(new_slide_id, show_id=SHOW_ID, auto_delete=True)
    logger.info(f"Added new map slide {new_slide_id} to show")

    # Remove CI progress slide
    if ci_slide_id:
        actlab.remove_slide_from_show(ci_slide_id, show_id=SHOW_ID)
        actlab.delete_slide(ci_slide_id)
        logger.info(f"Removed CI progress slide {ci_slide_id}")

    # Delete old slide (already removed from show in start)
    if old_slide_id:
        actlab.delete_slide(old_slide_id)
        logger.info(f"Deleted old slide {old_slide_id}")

    cleanup_state()

    logger.info("=" * 60)
    logger.info("New map uploaded successfully!")
    logger.info("=" * 60)
    return 0


def cmd_failure(actlab: ACTLabClient) -> int:
    """Build failed: remove CI progress slide, old slide remains as fallback."""
    logger.info("=" * 60)
    logger.info("CI Build Failed - Falling back to previous slide")
    logger.info("=" * 60)

    old_slide_id, ci_slide_id = load_state()

    # Remove CI progress slide
    if ci_slide_id:
        actlab.remove_slide_from_show(ci_slide_id, show_id=SHOW_ID)
        actlab.delete_slide(ci_slide_id)
        logger.info(f"Removed CI progress slide {ci_slide_id}")

    # Add old slide back to show and re-enable auto-delete
    if old_slide_id:
        actlab.add_slide_to_show(old_slide_id, show_id=SHOW_ID, auto_delete=True)
        logger.info(f"Restored fallback slide {old_slide_id} to show")

    cleanup_state()

    logger.info("=" * 60)
    logger.info("Fallback complete - old slide still active")
    logger.info("=" * 60)
    # Return 0 here - the actual build failure is handled by the workflow
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CI Slide Manager for ACT Lab display")
    parser.add_argument(
        "command",
        choices=["start", "success", "failure"],
        help="Command to execute",
    )
    args = parser.parse_args()

    with ACTLabClient() as actlab:
        if args.command == "start":
            return cmd_start(actlab)
        elif args.command == "success":
            return cmd_success(actlab)
        elif args.command == "failure":
            return cmd_failure(actlab)

    return 1


if __name__ == "__main__":
    sys.exit(main())
