#!/usr/bin/env python3
"""Upload slide to ACT Lab and manage show - Using dsv-wrapper"""
import logging
from pathlib import Path

from dotenv import load_dotenv
from dsv_wrapper import ACTLabClient

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

SHOW_ID = "1"
KEEP_LATEST = 1
FILE_PATH = Path("output/tv/ACT_map_tv.png")
SLIDE_NAME = "ACT Lab Map"

logger.info("=" * 60)
logger.info("ACT Lab Digital Signage Manager")
logger.info("=" * 60)

with ACTLabClient() as actlab:
    logger.info(f"\nUploading: {FILE_PATH}")

    if not FILE_PATH.exists():
        logger.error(f"File not found: {FILE_PATH}")
        exit(1)

    result = actlab.upload_slide(file_path=FILE_PATH, slide_name=SLIDE_NAME)

    if result.success:
        logger.info(f"✅ Upload successful! Slide ID: {result.slide_id}")

        actlab.add_slide_to_show(result.slide_id, show_id=SHOW_ID, auto_delete=True)
        logger.info("✅ Slide added to show")

        removed = actlab.cleanup_old_slides(show_id=SHOW_ID, keep_latest=KEEP_LATEST)
        logger.info(f"✅ Removed {removed} old slides")

        logger.info("\n" + "=" * 60)
        logger.info("✅ Complete!")
        logger.info("=" * 60)
    else:
        logger.error(f"❌ Upload failed: {result.message}")
        exit(1)
