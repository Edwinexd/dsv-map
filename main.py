#!/usr/bin/env python3
"""
Main script to generate DSV staff maps
This script:
1. Scrapes employee data from Daisy (including units)
2. Downloads profile pictures
3. Fixes employee names
4. Fetches positions from DSV Clickmap
5. Generates unified interactive HTML maps
6. Generates TV-optimized PNG images

Usage: python3 main.py
"""

import asyncio
import json
import os
import shutil

import clickmap_positions
import create_tv_16x9_with_qr
import download_all_dsv_pictures
import fix_all_dsv_names

# Import the other scripts
import get_all_dsv_employees

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)


def run_step(description, func):
    """Run a function and handle errors"""
    print(f"\n{'=' * 60}")
    print(f"{description}")
    print(f"{'=' * 60}")
    func()
    print(f"✅ {description} completed")


def ensure_dir(path):
    """Ensure directory exists"""
    os.makedirs(path, exist_ok=True)


# Ensure output directories exist
ensure_dir("output/html")
ensure_dir("output/tv")
ensure_dir("profile_pictures")

print("=" * 60)
print("DSV Staff Map Generator")
print("=" * 60)

# Step 1: Scrape all DSV employees
run_step(
    "Step 1/5: Scraping all DSV employees from Daisy",
    lambda: asyncio.run(get_all_dsv_employees.main()),
)

# Step 2: Download profile pictures
run_step(
    "Step 2/5: Downloading profile pictures", lambda: asyncio.run(download_all_dsv_pictures.main())
)

# Step 3: Fix names
run_step("Step 3/5: Fixing employee names", fix_all_dsv_names.main)

# Step 4: Generate unified HTML map
print(f"\n{'=' * 60}")
print("Step 4/5: Generating unified interactive HTML map")
print(f"{'=' * 60}")

# Load data
with open("all_dsv_employees_complete.json", encoding="utf-8") as f:
    all_employees = json.load(f)

# Extract units from employee data (units are already provided by dsv-wrapper)
employee_units_map = {}
all_units_set = set()
for emp in all_employees:
    person_id = emp["person_id"]
    units = emp.get("units", [])
    if units:
        employee_units_map[person_id] = units
        all_units_set.update(units)
all_units = sorted(all_units_set)

# Fetch positions from Clickmap (by person name)
print("Fetching positions from DSV Clickmap...")
clickmap_by_person = clickmap_positions.fetch_clickmap_positions_by_person()
print(f"  Found {len(clickmap_by_person)} occupied positions in Clickmap")

# Location overrides (user-submitted room changes)
location_overrides = {}
try:
    with open("data/location_overrides.json") as f:
        data = json.load(f)
        location_overrides = {k: v for k, v in data.items() if not k.startswith("_")}
except FileNotFoundError:
    pass

# Assign coordinates from Clickmap (by person name)
employee_coords = {}

for emp in all_employees:
    person_id = emp["person_id"]
    name = emp["name"]

    # Look up position in Clickmap by person name (with fuzzy matching)
    matched = False
    for clickmap_name, (x, y, place_name) in clickmap_by_person.items():
        if clickmap_positions.names_match(name, clickmap_name):
            emp["room"] = place_name  # Update room from clickmap
            employee_coords[person_id] = (x, y, "clickmap", None)
            matched = True
            break

# Apply location overrides (these take precedence)
clickmap_pos = clickmap_positions.fetch_clickmap_positions()
for emp in all_employees:
    person_id = emp["person_id"]
    if person_id in location_overrides:
        override_room = location_overrides[person_id]
        emp["room"] = override_room
        if override_room in clickmap_pos:
            x, y = clickmap_pos[override_room]
            employee_coords[person_id] = (x, y, "clickmap", None)
            print(f"Applied location override for {emp['name']} (ID: {person_id}): {override_room}")

print(f"Positioned {len(employee_coords)} employees")

# Add coordinates to employee records for use by create_tv
for emp in all_employees:
    person_id = emp["person_id"]
    if person_id in employee_coords:
        x, y, method, zone = employee_coords[person_id]
        emp["x"] = x
        emp["y"] = y

# Create unified HTML
html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DSV Staff Map - Interactive</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1800px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #002F5F;
            text-align: center;
            margin-bottom: 10px;
        }
        .controls {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .control-group {
            flex: 1;
            min-width: 200px;
        }
        .control-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            color: #002F5F;
        }
        select, input[type="text"] {
            width: 100%;
            padding: 8px;
            border: 2px solid #002F5F;
            border-radius: 5px;
            font-size: 14px;
        }
        .stats {
            display: flex;
            gap: 20px;
            margin: 20px 0;
            padding: 15px;
            background: #f0f7ff;
            border-radius: 8px;
            justify-content: center;
            flex-wrap: wrap;
        }
        .stat {
            text-align: center;
        }
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #002F5F;
        }
        .stat-label {
            font-size: 12px;
            color: #666;
            margin-top: 3px;
        }
        .map-wrapper {
            width: 100%;
            overflow: auto;
            max-height: 90vh;
            border: 2px solid #ccc;
            border-radius: 5px;
            background: #f9f9f9;
        }
        .map-container {
            position: relative;
            display: inline-block;
            min-width: 100%;
        }
        #floorplan {
            display: block;
            width: 100%;
            height: auto;
        }
        .staff-marker {
            position: absolute;
            width: 40px;
            height: 40px;
            margin-left: -20px;
            margin-top: -20px;
            cursor: pointer;
            transition: all 0.2s;
            z-index: 10;
        }
        .staff-marker:hover {
            transform: scale(1.5);
            z-index: 100;
        }
        .staff-marker img {
            width: 100%;
            height: 100%;
            border-radius: 50%;
            border: 3px solid #002F5F;
            object-fit: cover;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }
        .staff-marker:hover img {
            border-color: #FF6B35;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        }
        .staff-marker.hidden {
            display: none;
        }
        .staff-marker.highlighted img {
            border-color: #FF6B35;
            border-width: 4px;
            box-shadow: 0 0 20px rgba(255, 107, 53, 0.8);
        }
        .staff-marker.clickmap img {
            border-style: solid;
        }
        .tooltip {
            position: fixed;
            background: white;
            padding: 12px 16px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            font-size: 14px;
            white-space: nowrap;
            pointer-events: none;
            z-index: 10000;
            display: none;
            border: 2px solid #002F5F;
        }
        .tooltip-name {
            font-weight: bold;
            color: #002F5F;
            margin-bottom: 4px;
        }
        .tooltip-room {
            color: #666;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>DSV Staff Location Map</h1>

        <div class="controls">
            <div class="control-group">
                <label for="unitFilter">Filter by Unit:</label>
                <select id="unitFilter">
                    <option value="all">All DSV Staff</option>"""

# Add all units to dropdown
for unit in all_units:
    count = sum(1 for pid, units in employee_units_map.items() if unit in units)
    html += f"""
                    <option value="{unit}">{unit} ({count})</option>"""

html += """
                </select>
            </div>
            <div class="control-group">
                <label for="searchInput">Search by Name:</label>
                <input type="text" id="searchInput" placeholder="Type name to search...">
            </div>
        </div>

        <div class="stats">
            <div class="stat">
                <div class="stat-value" id="visibleCount">0</div>
                <div class="stat-label">Visible</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="totalCount">0</div>
                <div class="stat-label">Total Placed</div>
            </div>
        </div>

        <div class="map-wrapper">
            <div class="map-container" id="mapContainer">
                <img id="floorplan" src="floor_plan.png" alt="DSV Floor 3 Map">
"""

# Add staff markers with data attributes
img_width = 3056
img_height = 3056

for emp in all_employees:
    person_id = emp["person_id"]
    if person_id in employee_coords:
        x, y, method, zone = employee_coords[person_id]
        name = emp["name"]
        room = emp.get("room", "Unknown")
        pic_filename = f"{person_id}.jpg"

        # Get units for this person
        person_units = employee_units_map.get(person_id, [])
        units_str = ",".join(person_units) if person_units else ""

        x_percent = (x / img_width) * 100
        y_percent = (y / img_height) * 100

        method_text = "Clickmap position"

        html += f"""
                <div class="staff-marker {method}"
                     style="left: {x_percent}%; top: {y_percent}%;"
                     data-name="{name}"
                     data-room="{room}"
                     data-units="{units_str}"
                     data-accuracy="{method_text}">
                    <img src="profile_pictures/{pic_filename}" alt="{name}">
                </div>
"""

html += """
            </div>
        </div>
    </div>

    <div id="tooltip" class="tooltip">
        <div class="tooltip-name"></div>
        <div class="tooltip-room"></div>
    </div>

    <script>
        const markers = document.querySelectorAll('.staff-marker');
        const tooltip = document.getElementById('tooltip');
        const unitFilter = document.getElementById('unitFilter');
        const searchInput = document.getElementById('searchInput');
        const visibleCount = document.getElementById('visibleCount');
        const totalCount = document.getElementById('totalCount');

        // Tooltip handlers
        markers.forEach(marker => {
            marker.addEventListener('mouseenter', (e) => {
                tooltip.querySelector('.tooltip-name').textContent = marker.dataset.name;
                const roomText = `Room: ${marker.dataset.room} (${marker.dataset.accuracy})`;
                tooltip.querySelector('.tooltip-room').textContent = roomText;
                tooltip.style.display = 'block';
            });

            marker.addEventListener('mousemove', (e) => {
                tooltip.style.left = (e.clientX + 15) + 'px';
                tooltip.style.top = (e.clientY + 15) + 'px';
            });

            marker.addEventListener('mouseleave', () => {
                tooltip.style.display = 'none';
            });
        });

        // Filter and search logic
        function updateDisplay() {
            const filterValue = unitFilter.value;
            const searchValue = searchInput.value.toLowerCase();
            let visible = 0;
            let total = markers.length;

            markers.forEach(marker => {
                const units = marker.dataset.units.split(',');
                const name = marker.dataset.name.toLowerCase();

                // Check unit filter
                let matchesFilter = filterValue === 'all' || units.includes(filterValue);

                // Check search
                let matchesSearch = searchValue === '' || name.includes(searchValue);

                // Show/hide marker
                if (matchesFilter && matchesSearch) {
                    marker.classList.remove('hidden');
                    if (searchValue !== '' && matchesSearch) {
                        marker.classList.add('highlighted');
                    } else {
                        marker.classList.remove('highlighted');
                    }
                    visible++;
                } else {
                    marker.classList.add('hidden');
                    marker.classList.remove('highlighted');
                }
            });

            visibleCount.textContent = visible;
            totalCount.textContent = total;
        }

        // Event listeners
        unitFilter.addEventListener('change', updateDisplay);
        searchInput.addEventListener('input', updateDisplay);

        // Initial update
        updateDisplay();
    </script>
</body>
</html>
"""

# Save unified map
output_html = "output/html/staff_map_unified.html"
with open(output_html, "w", encoding="utf-8") as f:
    f.write(html)

print(f"✅ Unified interactive map created: {output_html}")
print("   Features: unit filter, search, tooltips")
print(f"   Total employees: {len(all_employees)}")
print(f"   Positioned: {len(employee_coords)}")
print(f"   Units: {len(all_units)}")

# Copy required assets to output directory
print("\nCopying assets to output directory...")

# Copy floor plan
shutil.copy2("assets/floor_plan.png", "output/html/floor_plan.png")

# Copy profile pictures
output_pics_dir = "output/html/profile_pictures"
os.makedirs(output_pics_dir, exist_ok=True)
if os.path.exists("profile_pictures"):
    for pic_file in os.listdir("profile_pictures"):
        if pic_file.endswith((".jpg", ".png")):
            shutil.copy2(
                os.path.join("profile_pictures", pic_file), os.path.join(output_pics_dir, pic_file)
            )
print("✅ Copied assets to output/html/")

# Step 5: Generate TV images per unit (16:9 format with QR code)
print(f"\n{'=' * 60}")
print("Step 5/5: Generating 16:9 TV images with QR codes per unit")
print(f"{'=' * 60}")

tv_files = []

# Generate TV image for all employees
print(f"\n[All DSV] Generating 16:9 TV image for all {len(all_employees)} employees...")
try:
    create_tv_16x9_with_qr.main(
        "all_dsv_employees_complete.json",
        "output/tv/all_dsv_staff_map_tv.png",
        title="All DSV Staff",
    )
    tv_files.append("output/tv/all_dsv_staff_map_tv.png")
    print("✅ Generated: output/tv/all_dsv_staff_map_tv.png")
except (OSError, ValueError) as e:
    print(f"❌ Failed to generate: {e}")

# Generate TV image for each unit
for unit in all_units:
    # Filter employees by unit
    unit_employees = [
        emp
        for emp in all_employees
        if emp["person_id"] in employee_units_map and unit in employee_units_map[emp["person_id"]]
    ]

    if not unit_employees:
        print(f"⚠️  Skipping {unit}: no employees found")
        continue

    # Create temporary JSON for this unit
    unit_json = f"temp_unit_{unit.replace(' ', '_').replace('/', '_')}.json"
    with open(unit_json, "w", encoding="utf-8") as f:
        json.dump(unit_employees, f, ensure_ascii=False, indent=2)

    # Generate TV image for this unit
    unit_output = f"output/tv/{unit.replace(' ', '_').replace('/', '_')}_map_tv.png"
    print(f"\n[{unit}] Generating 16:9 TV image for {len(unit_employees)} employees...")

    try:
        create_tv_16x9_with_qr.main(unit_json, unit_output, title=unit)
        tv_files.append(unit_output)
        print(f"✅ Generated: {unit_output}")
    except (OSError, ValueError) as e:
        print(f"❌ Failed to generate: {unit_output}: {e}")

    # Clean up temporary file
    os.remove(unit_json)

print("\n✅ Step 5/5: Generating 16:9 TV images with QR codes per unit completed")

print("\n" + "=" * 60)
print("🎉 ALL DONE!")
print("=" * 60)
print("Generated files:")
print("  - output/html/staff_map_unified.html (interactive map)")
print(f"\nTV Images ({len(tv_files)}):")
for tv_file in tv_files:
    print(f"  - {tv_file}")
print("=" * 60)
