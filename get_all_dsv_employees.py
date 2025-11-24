#!/usr/bin/env python3
"""Get ALL DSV employees with rooms from Daisy - Using dsv-wrapper"""
import asyncio
import json
import logging

from dotenv import load_dotenv
from dsv_wrapper import AsyncDaisyClient

logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

load_dotenv()


async def main():
    print("=" * 60)
    print("Fetching ALL DSV employees...")
    print("=" * 60)

    async with AsyncDaisyClient() as daisy:
        all_staff = await daisy.get_all_staff()  # Defaults to DSV

        staff_data = []
        for staff in all_staff:
            staff_dict = {
                "name": staff.name,
                "person_id": staff.person_id,
                "profile_url": staff.profile_url,
                "profile_pic_url": staff.profile_pic_url,
                "email": staff.email,
                "room": staff.room,
                "location": staff.location,
                "units": staff.units,
                "swedish_title": staff.swedish_title,
                "english_title": staff.english_title,
                "phone": staff.phone,
                "row_data": [staff.name, staff.email or "", staff.room or ""],
            }
            staff_data.append(staff_dict)

        output_file = "all_dsv_employees_complete.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(staff_data, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*60}")
        print(f"Final: {len(staff_data)} DSV employees")
        print(f"With rooms: {sum(1 for s in staff_data if s.get('room'))}")
        print(f"With emails: {sum(1 for s in staff_data if s.get('email'))}")
        print(f"{'='*60}")
        print(f"\nSaved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
