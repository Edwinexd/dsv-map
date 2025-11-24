#!/usr/bin/env python3
"""
Scrape unit information from Daisy profile pages using authenticated session
"""
import json
import requests
from bs4 import BeautifulSoup
import time
import os
import asyncio
import aiohttp


async def fetch_employee_units(session_obj, emp, index, total, employee_units, all_units):
    """Fetch units for one employee"""
    person_id = emp['person_id']
    name = emp['name']

    try:
        url = f"https://daisy.dsv.su.se/anstalld/anstalldinfo.jspa?personID={person_id}"
        async with session_obj.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                text = await response.text()
                soup = BeautifulSoup(text, 'html.parser')

                # Find the Units row
                for td in soup.find_all('td', class_='text'):
                    if 'Units:' in td.text or 'Enhet' in td.text:
                        # Next sibling should have the units
                        units_td = td.find_next_sibling('td')
                        if units_td:
                            units_text = units_td.get_text(strip=True)
                            # Split by comma
                            units = [u.strip() for u in units_text.split(',')]
                            employee_units[person_id] = units
                            all_units.update(units)
                            break

                if (index + 1) % 20 == 0:
                    print(f"Progress: {index+1}/{total}")

    except Exception as e:
        print(f"Error for {name}: {e}")


async def fetch_all_units(employees, session_id):
    """Fetch all employee units concurrently"""
    employee_units = {}
    all_units = set()

    connector = aiohttp.TCPConnector(limit=20)
    cookies = {'JSESSIONID': session_id}
    async with aiohttp.ClientSession(
        cookies=cookies,
        connector=connector
    ) as session_obj:
        tasks = [
            fetch_employee_units(session_obj, emp, i, len(employees), employee_units, all_units)
            for i, emp in enumerate(employees)
        ]
        await asyncio.gather(*tasks)

    return employee_units, all_units


def main():
    # Load authentication cookies
    cookie_cache_path = os.path.join(os.path.dirname(__file__), '.cookie_cache.json')
    try:
        with open(cookie_cache_path, 'r') as f:
            cache = json.load(f)
            # The format is: {"daisy_staff": {"cookie": "...", "timestamp": "..."}}
            session_id = cache.get('daisy_staff', {}).get('cookie')
            if not session_id:
                raise ValueError("No session cookie in cache")
    except Exception as e:
        print(f"Error loading authentication: {e}")
        print("Please run get_all_dsv_employees.py first to create authenticated session")
        exit(1)

    # Load all employees
    employees_path = os.path.join(os.path.dirname(__file__), 'all_dsv_employees_complete.json')
    with open(employees_path, 'r', encoding='utf-8') as f:
        employees = json.load(f)

    print(f"Scraping units for {len(employees)} employees using authenticated session (concurrently)...")

    employee_units, all_units = asyncio.run(fetch_all_units(employees, session_id))

    print(f"\nFound {len(all_units)} unique units:")
    for unit in sorted(all_units):
        count = sum(1 for units in employee_units.values() if unit in units)
        print(f"  {unit}: {count} employees")

    # Save results
    result = {
        'employee_units': employee_units,
        'all_units': sorted(all_units)
    }

    output_path = os.path.join(os.path.dirname(__file__), 'employee_units.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved to employee_units.json")


if __name__ == "__main__":
    main()
