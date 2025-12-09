#!/usr/bin/env python3
"""Upload slide to ACT Lab and manage show - Using dsv-wrapper"""

import logging
import time
from pathlib import Path

from dotenv import load_dotenv
from dsv_wrapper import ACTLabClient

logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

load_dotenv()

SHOW_ID = 1
FILE_PATH = Path("output/tv/ACT_map_tv.png")
SLIDE_NAME = "ACT Lab Map"
DELETE_DELAY_SECONDS = 5

logger.info("=" * 60)
logger.info("ACT Lab Digital Signage Manager")
logger.info("=" * 60)

with ACTLabClient() as actlab:
    logger.info(f"\nUploading: {FILE_PATH}")

    if not FILE_PATH.exists():
        logger.error(f"File not found: {FILE_PATH}")
        exit(1)

    # Get existing slides in the show with auto_delete enabled
    existing_slides = actlab.get_slides()
    old_slide_ids = [
        slide.id for slide in existing_slides if slide.show_id == SHOW_ID and slide.auto_delete
    ]

    if old_slide_ids:
        logger.info(f"Found {len(old_slide_ids)} existing slide(s) to replace")

    result = actlab.upload_slide(file_path=FILE_PATH, slide_name=SLIDE_NAME)

    if result.success:
        logger.info(f"✅ Upload successful! Slide ID: {result.slide_id}")

        actlab.add_slide_to_show(result.slide_id, show_id=SHOW_ID, auto_delete=True)
        logger.info("✅ Slide added to show")

        # Manually delete old slides after a delay
        if old_slide_ids:
            logger.info(f"Waiting {DELETE_DELAY_SECONDS}s before deleting old slides...")
            time.sleep(DELETE_DELAY_SECONDS)

            for old_id in old_slide_ids:
                actlab.delete_slide(old_id)
                logger.info(f"✅ Deleted old slide: {old_id}")

        logger.info("\n" + "=" * 60)
        logger.info("✅ Complete!")
        logger.info("=" * 60)
    else:
        logger.error(f"❌ Upload failed: {result.message}")
        exit(1)
