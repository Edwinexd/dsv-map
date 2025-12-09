#!/usr/bin/env python3
"""Upload slide to ACT Lab and manage show - Using dsv-wrapper"""

import logging
import os
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv
from dsv_wrapper import ACTLabClient
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

load_dotenv()

SHOW_ID = 1
FILE_PATH = Path("output/tv/ACT_map_tv.png")
SLIDE_NAME = "ACT Lab Map"
DELETE_DELAY_SECONDS = 5
MAX_UPLOAD_SIZE_MB = 1.9  # ACT Lab server limit is ~2MB

logger.info("=" * 60)
logger.info("ACT Lab Digital Signage Manager")
logger.info("=" * 60)

with ACTLabClient() as actlab:
    logger.info(f"\nUploading: {FILE_PATH}")

    if not FILE_PATH.exists():
        logger.error(f"File not found: {FILE_PATH}")
        exit(1)

    # Check file size and convert to JPEG if needed (server has ~2MB limit)
    upload_path = FILE_PATH
    temp_file = None
    file_size_mb = FILE_PATH.stat().st_size / 1024 / 1024

    if file_size_mb > MAX_UPLOAD_SIZE_MB:
        logger.info(f"File size {file_size_mb:.2f}MB exceeds {MAX_UPLOAD_SIZE_MB}MB limit")
        logger.info("Converting to JPEG for upload...")

        img = Image.open(FILE_PATH)
        temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)

        # Progressively lower quality until under limit
        for quality in [95, 90, 85, 80, 75, 70, 65, 60]:
            img.save(temp_file.name, format="JPEG", quality=quality)
            new_size_mb = Path(temp_file.name).stat().st_size / 1024 / 1024
            if new_size_mb <= MAX_UPLOAD_SIZE_MB:
                logger.info(f"Converted to JPEG (quality={quality}): {new_size_mb:.2f}MB")
                break
        else:
            logger.warning(f"Could not compress below {MAX_UPLOAD_SIZE_MB}MB, using quality=60")

        upload_path = Path(temp_file.name)

    # Get existing slides in the show with auto_delete enabled
    existing_slides = actlab.get_slides()
    old_slide_ids = [
        slide.id for slide in existing_slides if slide.show_id == SHOW_ID and slide.auto_delete
    ]

    if old_slide_ids:
        logger.info(f"Found {len(old_slide_ids)} existing slide(s) to replace")

    result = actlab.upload_slide(file_path=upload_path, slide_name=SLIDE_NAME)

    if result.success:
        logger.info(f"✅ Upload successful! Slide ID: {result.slide_id}")

        actlab.add_slide_to_show(result.slide_id, show_id=SHOW_ID, auto_delete=True)
        logger.info("✅ Slide added to show")

        # Manually delete old slides after a delay
        if old_slide_ids:
            logger.info(f"Waiting {DELETE_DELAY_SECONDS}s before deleting old slides...")
            time.sleep(DELETE_DELAY_SECONDS)

            for old_id in old_slide_ids:
                actlab.remove_slide_from_show(old_id, show_id=SHOW_ID)
                logger.info(f"✅ Removed slide {old_id} from show")
                actlab.delete_slide(old_id)
                logger.info(f"✅ Deleted old slide: {old_id}")

        logger.info("\n" + "=" * 60)
        logger.info("✅ Complete!")
        logger.info("=" * 60)
    else:
        logger.error(f"❌ Upload failed: {result.message}")
        if temp_file:
            os.unlink(temp_file.name)
        exit(1)

    # Clean up temp file
    if temp_file:
        os.unlink(temp_file.name)
