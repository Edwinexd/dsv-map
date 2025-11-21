#!/usr/bin/env python3
"""
Get ALL DSV employees with rooms from Daisy
"""
import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from login import daisy_staff_login
import json
import re
import time
import asyncio
import aiohttp

# Load credentials from project root
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env')
load_dotenv(env_path)

su_username = os.environ.get("SU_USERNAME")
su_password = os.environ.get("SU_PASSWORD")

print("Logging into Daisy (staff)...")
jsessionid = daisy_staff_login(su_username, su_password, use_cache=True)
cookies = {"JSESSIONID": jsessionid}
print(f"Successfully logged in!")

print("\n" + "="*60)
print("Searching for ALL DSV employees...")
print("="*60)

# Search for all employees at DSV (institution ID = 4)
form_data = {
    "efternamn": "",
    "fornamn": "",
    "epost": "",
    "anvandarnamn": "",
    "svenskTitel": "",
    "engelskTitel": "",
    "personalkategori": "",
    "institutionID": "4",  # DSV institution
    "anstalldTyp": "ALL",
    "enhetID": "",  # All units (not just ACT)
    "action:sokanstalld": "Sök"
}

response = requests.post(
    "https://daisy.dsv.su.se/sok/visaanstalld.jspa",
    cookies=cookies,
    data=form_data,
    timeout=30
)

print(f"Search status: {response.status_code}")

if response.status_code == 200:
    soup = BeautifulSoup(response.text, "html.parser")

    # Save search results to output directory
    os.makedirs("output", exist_ok=True)
    with open("output/all_dsv_employees_results.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("Saved search results to: output/all_dsv_employees_results.html")

    # Look for results table
    tables = soup.find_all("table", class_="randig")
    print(f"\nFound {len(tables)} result table(s)")

    all_staff = []

    if tables:
        for table in tables:
            rows = table.find_all("tr")
            print(f"Table has {len(rows)} rows")

            # Process data rows (skip header)
            for row in rows[1:]:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    # Look for profile link
                    profile_link = row.find("a", href=lambda x: x and "personID" in x)
                    if profile_link:
                        person_id_match = re.search(r'personID=(\d+)', profile_link.get('href', ''))
                        if person_id_match:
                            person_id = person_id_match.group(1)
                            name = profile_link.get_text().strip()

                            # Extract other data from row
                            row_data = [col.get_text().strip() for col in cols]

                            staff_info = {
                                "name": name,
                                "person_id": person_id,
                                "profile_url": f"https://daisy.dsv.su.se{profile_link.get('href')}",
                                "row_data": row_data
                            }

                            all_staff.append(staff_info)

    print(f"\n{'='*60}")
    print(f"Found {len(all_staff)} DSV employees")
    print(f"{'='*60}")

    # Now fetch each employee's profile to get picture and location
    print("\nFetching detailed information for each employee (concurrently)...")

    async def fetch_employee_details(session, staff, index, total):
        """Fetch detailed information for one employee"""
        try:
            async with session.get(staff['profile_url'], timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    text = await response.text()
                    soup = BeautifulSoup(text, "html.parser")

                    # Extract profile picture
                    img_tag = soup.find("img", src=lambda x: x and "daisy.Jpg" in x)
                    if img_tag:
                        pic_src = img_tag.get("src", "")
                        if pic_src.startswith("/"):
                            pic_src = f"https://daisy.dsv.su.se{pic_src}"
                        staff['profile_pic_url'] = pic_src
                    else:
                        staff['profile_pic_url'] = None

                    # Extract email
                    email_link = soup.find("a", href=lambda x: x and "mailto:" in x)
                    if email_link:
                        email = email_link.get("href", "").replace("mailto:", "")
                        staff['email'] = email
                    else:
                        staff['email'] = None

                    # Extract room/location from tables
                    staff['room'] = None
                    staff['location'] = None

                    tables = soup.find_all("table")
                    for table in tables:
                        rows = table.find_all("tr")
                        for row in rows:
                            cells = row.find_all("td")
                            if len(cells) >= 2:
                                label = cells[0].get_text().strip().lower()
                                value = cells[1].get_text().strip()

                                if "rum" in label or "room" in label:
                                    staff['room'] = value
                                elif "lokal" in label or "plats" in label or "arbetsplats" in label:
                                    staff['location'] = value

                    if (index + 1) % 10 == 0:
                        room_info = f" (Room: {staff['room']})" if staff['room'] else ""
                        print(f"[{index+1}/{total}] {staff['name']}{room_info}")

        except Exception as e:
            print(f"  Error fetching {staff['name']}: {e}")

    async def fetch_all_employees():
        """Fetch all employee details concurrently"""
        connector = aiohttp.TCPConnector(limit=20)  # Max 20 concurrent connections
        async with aiohttp.ClientSession(
            cookies=cookies,
            connector=connector
        ) as session:
            tasks = [
                fetch_employee_details(session, staff, i, len(all_staff))
                for i, staff in enumerate(all_staff)
            ]
            await asyncio.gather(*tasks)

    # Run the async fetching
    asyncio.run(fetch_all_employees())

    # Save final results
    output_file = os.path.join(script_dir, "all_dsv_employees_complete.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_staff, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"Final: {len(all_staff)} DSV employees")
    print(f"With rooms: {sum(1 for s in all_staff if s.get('room'))}")
    print(f"{'='*60}")

    print(f"\nSaved results to: all_dsv_employees_complete.json")

else:
    print(f"Error: HTTP {response.status_code}")
