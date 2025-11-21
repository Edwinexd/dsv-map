#!/usr/bin/env python3
"""
Fix names in all_dsv_employees_complete.json from row_data
"""
import os
import json

# Load employee data
script_dir = os.path.dirname(os.path.abspath(__file__))
employee_file = os.path.join(script_dir, "all_dsv_employees_complete.json")
with open(employee_file, "r", encoding="utf-8") as f:
    employees = json.load(f)

print(f"Fixing names for {len(employees)} employees...")

fixed = 0
for emp in employees:
    if not emp.get("name") or emp["name"] == "":
        if emp.get("row_data") and len(emp["row_data"]) >= 4:
            lastname = emp["row_data"][2]
            firstname = emp["row_data"][3]
            emp["name"] = f"{firstname} {lastname}"
            fixed += 1

print(f"Fixed {fixed} names")

# Save back
with open(employee_file, "w", encoding="utf-8") as f:
    json.dump(employees, f, indent=2, ensure_ascii=False)

print("Saved updated data")
