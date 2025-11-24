#!/usr/bin/env python3
"""
Download profile pictures for all DSV employees - Using dsv-wrapper
"""
import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from dsv_wrapper import AsyncDaisyClient


async def main():
    # Load credentials from project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, '.env')
    load_dotenv(env_path)

    # Load employee data
    employee_file = os.path.join(script_dir, "all_dsv_employees_complete.json")
    with open(employee_file, "r", encoding="utf-8") as f:
        employees = json.load(f)

    print(f"\nProcessing {len(employees)} DSV employees...")

    # Create directory
    pics_dir = Path(script_dir) / "profile_pictures"
    pics_dir.mkdir(exist_ok=True)

    successful = 0
    failed = []
    no_url = []

    async with AsyncDaisyClient() as daisy:
        for i, emp in enumerate(employees, 1):
            # Fix name from row_data if needed
            if emp.get("row_data") and len(emp["row_data"]) >= 4:
                lastname = emp["row_data"][2]
                firstname = emp["row_data"][3]
                emp["name"] = f"{firstname} {lastname}"

            name = emp.get('name', 'Unknown')
            person_id = emp['person_id']
            pic_url = emp.get('profile_pic_url')

            if not pic_url:
                no_url.append(name)
                continue

            pic_filename = f"{person_id}.jpg"
            pic_path = pics_dir / pic_filename

            # Skip if already exists
            if pic_path.exists():
                successful += 1
                if i % 50 == 0:
                    print(f"[{i}/{len(employees)}] Skipping existing: {name}")
                continue

            if i % 10 == 0:
                print(f"[{i}/{len(employees)}] Downloading: {name}")

            # Use the wrapper's download method
            content = await daisy.download_profile_picture(pic_url)

            with open(pic_path, "wb") as f:
                f.write(content)

            file_size = pic_path.stat().st_size
            if file_size > 1000:
                successful += 1
            else:
                failed.append((name, f"File too small: {file_size} bytes"))

    print("\n" + "="*60)
    print("Summary:")
    print("="*60)
    print(f"✅ Successfully downloaded: {successful}/{len(employees)}")
    print(f"❌ Failed: {len(failed)}")
    print(f"⚠️  No URL: {len(no_url)}")
    print(f"\nImages saved to: {pics_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
