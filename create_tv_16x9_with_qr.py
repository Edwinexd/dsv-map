#!/usr/bin/env python3
"""
Create TV-optimized 16:9 version with QR code and info panel
Usage: python3 create_tv_16x9_with_qr.py <employee_json> <output_png> [--url <url_for_qr>]
"""
import json
import math
import argparse
from PIL import Image, ImageDraw, ImageFont
import os

# Parse arguments
parser = argparse.ArgumentParser(description='Create 16:9 TV map with QR code')
parser.add_argument('employee_json', help='Path to employee JSON file')
parser.add_argument('output_png', help='Output PNG file path')
parser.add_argument('--url', default='https://dsv.su.se', help='URL for QR code')
parser.add_argument('--title', default=None, help='Title for the image')
args = parser.parse_args()

employee_file = args.employee_json
output_file = args.output_png
qr_url = args.url

# Load employee data
with open(employee_file, "r", encoding="utf-8") as f:
    employees = json.load(f)

# Get script directory for loading resource files
script_dir = os.path.dirname(os.path.abspath(__file__))

# Load OCR-detected room positions
room_positions_file = os.path.join(script_dir, "data", "room_positions_easyocr.json")
with open(room_positions_file, "r", encoding="utf-8") as f:
    ocr_rooms = json.load(f)

# Zone coordinates
zone_centers_file = os.path.join(script_dir, "data", "zone_centers.json")
with open(zone_centers_file, "r", encoding="utf-8") as f:
    zone_data = json.load(f)
    zone_centers = {int(k): tuple(v) for k, v in zone_data.items() if not k.startswith("_")}

# Location overrides (user-submitted room changes)
location_overrides = {}
try:
    location_overrides_file = os.path.join(script_dir, "data", "location_overrides.json")
    with open(location_overrides_file, "r") as f:
        data = json.load(f)
        location_overrides = {k: v for k, v in data.items() if not k.startswith("_")}
except FileNotFoundError:
    pass

def get_zone_from_special_room(room):
    if not room or not isinstance(room, str):
        return None
    if ":" in room:
        try:
            zone_num = int(room.split(":")[0])
            return zone_num if 1 <= zone_num <= 8 else None
        except:
            return None
    return None

def interpolate_room_position(room_number, known_rooms):
    if not room_number or not isinstance(room_number, str):
        return None
    if ':' in room_number:
        return None
    try:
        room_num = int(room_number)
    except:
        return None

    prefix = room_number[:2]
    same_prefix_rooms = {}

    for known_room, (x, y) in known_rooms.items():
        if known_room.startswith(prefix) and len(known_room) == 5:
            try:
                same_prefix_rooms[int(known_room)] = (x, y)
            except:
                pass

    if len(same_prefix_rooms) < 2:
        return None

    sorted_rooms = sorted(same_prefix_rooms.keys())
    lower = None
    upper = None

    for known in sorted_rooms:
        if known < room_num:
            lower = known
        elif known > room_num and upper is None:
            upper = known
            break

    if lower and upper:
        x1, y1 = same_prefix_rooms[lower]
        x2, y2 = same_prefix_rooms[upper]
        ratio = (room_num - lower) / (upper - lower)
        x = x1 + (x2 - x1) * ratio
        y = y1 + (y2 - y1) * ratio
        return (x, y, 'interpolated')

    return None

# Assign coordinates
employee_coords = {}
stats = {'ocr': 0, 'interpolated': 0, 'zone': 0, 'no_position': 0}
employees_by_zone = {}

print(f"Processing {len(employees)} employees...")

# Apply location overrides to employee data
for emp in employees:
    person_id = emp['person_id']
    if person_id in location_overrides:
        emp['room'] = location_overrides[person_id]
        print(f"Applied location override for {emp['name']} (ID: {person_id}): {location_overrides[person_id]}")

for emp in employees:
    room = emp.get('room')
    person_id = emp['person_id']
    name = emp['name']

    if not room or room == "None":
        stats['no_position'] += 1
        continue

    zone = get_zone_from_special_room(room)
    if zone:
        if zone not in employees_by_zone:
            employees_by_zone[zone] = []
        employees_by_zone[zone].append((emp, room))
        continue

    if room in ocr_rooms:
        x, y = ocr_rooms[room]
        employee_coords[person_id] = (x, y, 'ocr', None)
        stats['ocr'] += 1
        continue

    result = interpolate_room_position(room, ocr_rooms)
    if result:
        x, y, method = result
        employee_coords[person_id] = (x, y, method, None)
        stats['interpolated'] += 1
        continue

    stats['no_position'] += 1

# Place zone-based employees
for zone, emps_and_rooms in employees_by_zone.items():
    center_x, center_y = zone_centers[zone]
    num_emps = len(emps_and_rooms)
    radius = 150

    for i, (emp, room) in enumerate(emps_and_rooms):
        angle = (2 * math.pi * i) / num_emps if num_emps > 1 else 0
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        employee_coords[emp['person_id']] = (x, y, 'zone', zone)
        stats['zone'] += 1

print(f"Placed {stats['ocr'] + stats['interpolated'] + stats['zone']}/{len(employees)} employees")

# Spread out overlapping employees
print("\nSpreading out overlapping employees...")
MIN_DISTANCE = 150
MAX_ITERATIONS = 100
SPREAD_FACTOR = 0.3

def get_distance(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def spread_overlapping_employees():
    coords_list = [(pid, x, y, method, zone) for pid, (x, y, method, zone) in employee_coords.items()]

    for iteration in range(MAX_ITERATIONS):
        moved = False

        for i, (pid1, x1, y1, method1, zone1) in enumerate(coords_list):
            force_x = 0
            force_y = 0

            for j, (pid2, x2, y2, method2, zone2) in enumerate(coords_list):
                if i == j:
                    continue

                dist = get_distance((x1, y1), (x2, y2))

                if dist < MIN_DISTANCE and dist > 0:
                    dx = x1 - x2
                    dy = y1 - y2
                    overlap = MIN_DISTANCE - dist
                    force_magnitude = overlap / MIN_DISTANCE
                    force_x += (dx / dist) * force_magnitude
                    force_y += (dy / dist) * force_magnitude

            if abs(force_x) > 0.01 or abs(force_y) > 0.01:
                new_x = x1 + force_x * SPREAD_FACTOR * MIN_DISTANCE
                new_y = y1 + force_y * SPREAD_FACTOR * MIN_DISTANCE
                coords_list[i] = (pid1, new_x, new_y, method1, zone1)
                employee_coords[pid1] = (new_x, new_y, method1, zone1)
                moved = True

        if not moved:
            print(f"  Converged after {iteration + 1} iterations")
            break

    if moved:
        print(f"  Completed {MAX_ITERATIONS} iterations")

spread_overlapping_employees()
print(f"✓ Spread out overlapping employees")

# Load floor plan
print("Loading floor plan...")
floor_plan_path = os.path.join(script_dir, 'assets', 'floor_plan.png')
floor_plan_original = Image.open(floor_plan_path).convert('RGBA')
img_width, img_height = floor_plan_original.size

# Calculate 16:9 dimensions
# Target aspect ratio 16:9
# We'll make the main map area fit nicely and add a side panel
TARGET_WIDTH = 3840  # 4K width (or 1920 for Full HD)
TARGET_HEIGHT = 2160  # 4K height (or 1080 for Full HD)
SIDE_PANEL_WIDTH = 800  # Width of the info panel on the right

# Calculate map area dimensions (left side of the image)
MAP_AREA_WIDTH = TARGET_WIDTH - SIDE_PANEL_WIDTH
MAP_AREA_HEIGHT = TARGET_HEIGHT

# Scale floor plan to fit in the map area while maintaining aspect ratio
scale = min(MAP_AREA_WIDTH / img_width, MAP_AREA_HEIGHT / img_height) * 0.85
new_map_width = int(img_width * scale)
new_map_height = int(img_height * scale)

# Center the map in the map area
map_offset_x = (MAP_AREA_WIDTH - new_map_width) // 2
map_offset_y = (MAP_AREA_HEIGHT - new_map_height) // 2

# Create the final 16:9 canvas
canvas = Image.new('RGB', (TARGET_WIDTH, TARGET_HEIGHT), (255, 255, 255))

# Resize and paste floor plan
floor_plan_resized = floor_plan_original.resize((new_map_width, new_map_height), Image.Resampling.LANCZOS)
canvas.paste(floor_plan_resized, (map_offset_x, map_offset_y), floor_plan_resized)

draw = ImageDraw.Draw(canvas)

# Load fonts - try multiple common font paths for cross-platform compatibility
font_paths = [
    "/System/Library/Fonts/Helvetica.ttc",  # macOS
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux (Debian/Ubuntu)
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",  # Linux (other)
    "C:\\Windows\\Fonts\\arial.ttf",  # Windows
]

def load_font(size):
    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, size)
        except:
            continue
    # Fallback to default
    print(f"Warning: Could not load any fonts, using default (size will be small)")
    return ImageFont.load_default()

font_title = load_font(80)
font_info = load_font(50)
font_name = load_font(40)
font_room = load_font(32)
font_stats = load_font(45)

# Draw side panel background
panel_x = MAP_AREA_WIDTH
draw.rectangle([panel_x, 0, TARGET_WIDTH, TARGET_HEIGHT], fill=(0, 47, 95))

# Add title to side panel
title = args.title if args.title else "DSV Staff Map"
title_bbox = draw.textbbox((0, 0), title, font=font_title)
title_width = title_bbox[2] - title_bbox[0]
title_x = panel_x + (SIDE_PANEL_WIDTH - title_width) // 2
draw.text((title_x, 80), title, fill=(255, 255, 255), font=font_title)

# Load and paste location update QR code (main QR code)
print("Loading location update QR code...")
try:
    qr_path = os.path.join(script_dir, 'assets', 'qr_fix_location.png')
    qr_img = Image.open(qr_path).convert('RGBA')
    qr_size = 500
    qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
    qr_x = panel_x + (SIDE_PANEL_WIDTH - qr_size) // 2
    qr_y = 250
    canvas.paste(qr_img, (qr_x, qr_y), qr_img)

    # Add instructions below QR code
    instruction_y = qr_y + qr_size + 30
    instruction_lines = [
        "Missing or in the",
        "wrong place?",
        "Scan to update!"
    ]
    for i, line in enumerate(instruction_lines):
        line_bbox = draw.textbbox((0, 0), line, font=font_info)
        line_width = line_bbox[2] - line_bbox[0]
        line_x = panel_x + (SIDE_PANEL_WIDTH - line_width) // 2
        draw.text((line_x, instruction_y + i * 60), line, fill=(255, 255, 255), font=font_info)

except Exception as e:
    print(f"Warning: Could not load qr_fix_location.png: {e}")

# Add statistics (smaller font, single line)
stats_y = qr_y + qr_size + 230
total_placed = stats['ocr'] + stats['interpolated'] + stats['zone']
missing_location = len(employees) - total_placed

stats_text = f"({total_placed} out of {len(employees)} displayed)"
stats_bbox = draw.textbbox((0, 0), stats_text, font=font_name)
stats_width = stats_bbox[2] - stats_bbox[0]
stats_x = panel_x + (SIDE_PANEL_WIDTH - stats_width) // 2
draw.text((stats_x, stats_y), stats_text, fill=(255, 255, 255), font=font_name)

# Add repository QR code and SU logo at the bottom
print("Loading repository QR code and SU logo...")
try:
    # Load SU logo
    logo_path = os.path.join(script_dir, 'assets', 'SU_logotyp_Landscape_Invert_1000px.png')
    logo_img = Image.open(logo_path).convert('RGBA')
    logo_width = 700
    aspect_ratio = logo_img.height / logo_img.width
    logo_height = int(logo_width * aspect_ratio)
    logo_img = logo_img.resize((logo_width, logo_height), Image.Resampling.LANCZOS)

    logo_x = panel_x + (SIDE_PANEL_WIDTH - logo_width) // 2
    logo_y = TARGET_HEIGHT - logo_height - 100
    canvas.paste(logo_img, (logo_x, logo_y), logo_img)

    # Load repository QR code (same height as logo, positioned above it)
    try:
        repo_qr_path = os.path.join(script_dir, 'assets', 'repo_qr.png')
        repo_qr_img = Image.open(repo_qr_path).convert('RGBA')
        repo_qr_height = logo_height
        qr_aspect_ratio = repo_qr_img.width / repo_qr_img.height
        repo_qr_width = int(repo_qr_height * qr_aspect_ratio)
        repo_qr_img = repo_qr_img.resize((repo_qr_width, repo_qr_height), Image.Resampling.LANCZOS)

        # Position QR above logo with some padding
        repo_qr_y = logo_y - repo_qr_height - 60
        repo_qr_x = panel_x + 50  # Left align with some padding

        canvas.paste(repo_qr_img, (repo_qr_x, repo_qr_y), repo_qr_img)

        # Add GitHub repo text to the right of QR code (three lines)
        repo_lines = [
            "Github:",
            "@Edwinexd/",
            "dsv-map"
        ]
        repo_text_x = repo_qr_x + repo_qr_width + 20
        # Start position to center all three lines vertically with QR
        line_height = 55
        total_text_height = len(repo_lines) * line_height
        repo_text_y = repo_qr_y + (repo_qr_height - total_text_height) // 2

        for i, line in enumerate(repo_lines):
            draw.text((repo_text_x, repo_text_y + i * line_height), line, fill=(255, 255, 255), font=font_info)

    except Exception as e:
        print(f"Warning: Could not load repo_qr.png: {e}")

except Exception as e:
    print(f"Warning: Could not load SU_logotyp_Landscape_Invert_1000px.png: {e}")

# Calculate label positions
print("Calculating label positions...")
label_data = []
occupied_rects = []

def rectangles_overlap(r1, r2, margin=10):
    return not (r1[2] + margin < r2[0] or
                r1[0] - margin > r2[2] or
                r1[3] + margin < r2[1] or
                r1[1] - margin > r2[3])

def count_nearby(x, y, coords, radius=300):
    count = 0
    for pid, (px, py, _, _) in coords.items():
        dist = math.sqrt((px - x)**2 + (py - y)**2)
        if dist < radius and dist > 0:
            count += 1
    return count

angle_preferences = [315, 45, 270, 225, 0, 135, 90, 180]

# Reserve space for all profile pictures
for emp in employees:
    person_id = emp['person_id']
    if person_id in employee_coords:
        x, y, method, zone = employee_coords[person_id]
        # Transform coordinates to canvas space
        x_canvas = map_offset_x + int(x * scale)
        y_canvas = map_offset_y + int(y * scale)
        pic_rect = (x_canvas - 48, y_canvas - 48, x_canvas + 48, y_canvas + 48)
        occupied_rects.append(pic_rect)

print(f"Reserved space for {len(occupied_rects)} profile pictures")

# Sort employees by density
employees_with_density = []
for emp in employees:
    person_id = emp['person_id']
    if person_id in employee_coords:
        x, y, method, zone = employee_coords[person_id]
        density = count_nearby(x, y, employee_coords)
        employees_with_density.append((density, emp))

employees_with_density.sort(reverse=True, key=lambda x: x[0])

# Place labels
for density, emp in employees_with_density:
    person_id = emp['person_id']
    if person_id not in employee_coords:
        continue

    x, y, method, zone = employee_coords[person_id]
    x_canvas = map_offset_x + int(x * scale)
    y_canvas = map_offset_y + int(y * scale)

    name = emp['name']
    room = emp.get('room', '')

    name_bbox = draw.textbbox((0, 0), name, font=font_name)
    room_bbox = draw.textbbox((0, 0), room, font=font_room)
    name_width = name_bbox[2] - name_bbox[0]
    name_height = name_bbox[3] - name_bbox[1]
    room_width = room_bbox[2] - room_bbox[0]
    room_height = room_bbox[3] - room_bbox[1]

    # Calculate actual bounding box size matching the rendering
    padding_box = 15
    # Width is the max of both boxes plus padding on both sides
    label_width = max(name_width, room_width) + (padding_box * 2)
    # Height is name box height + gap + room box height, each box has padding
    label_height = (padding_box + name_height + padding_box) + 10 + (padding_box + room_height + padding_box)

    # Total dimensions including outer padding for collision detection
    total_label_width = label_width + (padding_box * 2)
    total_label_height = label_height + (padding_box * 2)

    if density >= 5:
        distance = 300
        distances_to_try = [300, 400, 500, 600, 700, 800]
    elif density >= 3:
        distance = 250
        distances_to_try = [250, 350, 450, 550, 650]
    else:
        distance = 180
        distances_to_try = [180, 250, 320, 400, 500]

    placed = False
    for dist in distances_to_try:
        for angle_deg in angle_preferences:
            angle_rad = math.radians(angle_deg)
            label_x = x_canvas + dist * math.cos(angle_rad)
            label_y = y_canvas + dist * math.sin(angle_rad)

            # Keep labels in the map area only (accounting for padding)
            if (label_x - padding_box < 50 or label_x + label_width + padding_box > MAP_AREA_WIDTH - 50 or
                label_y - padding_box < 50 or label_y + label_height + padding_box > TARGET_HEIGHT - 50):
                continue

            # label_rect matches the actual stored rectangles (with outer padding)
            label_rect = (label_x - padding_box, label_y - padding_box,
                         label_x + label_width + padding_box, label_y + label_height + padding_box)

            # Use moderate margins for label-to-label collision to prevent text overlap
            collision_margin = 40 if density >= 5 else (30 if density >= 3 else 20)
            collision = False
            for occupied in occupied_rects:
                if rectangles_overlap(label_rect, occupied, margin=collision_margin):
                    collision = True
                    break

            if not collision:
                label_data.append((person_id, x_canvas, y_canvas, label_x, label_y, method, name, room))
                # Store both the name and room boxes separately for more accurate collision detection
                name_box_rect = (label_x - padding_box, label_y - padding_box,
                                label_x + name_width + padding_box, label_y + name_height + padding_box)
                room_y_pos = label_y + name_height + padding_box + 10
                room_box_rect = (label_x - padding_box, room_y_pos - padding_box,
                                label_x + room_width + padding_box, room_y_pos + room_height + padding_box)
                occupied_rects.append(name_box_rect)
                occupied_rects.append(room_box_rect)
                placed = True
                break

        if placed:
            break

    if not placed:
        # Fallback: try intermediate and larger distances with all angles
        for dist in [600, 700, 800, 900, 1000]:
            for angle_deg in angle_preferences:
                angle_rad = math.radians(angle_deg)
                label_x = x_canvas + dist * math.cos(angle_rad)
                label_y = y_canvas + dist * math.sin(angle_rad)

                if (label_x - padding_box < 50 or label_x + label_width + padding_box > MAP_AREA_WIDTH - 50 or
                    label_y - padding_box < 50 or label_y + label_height + padding_box > TARGET_HEIGHT - 50):
                    continue

                label_rect = (label_x - padding_box, label_y - padding_box,
                             label_x + label_width + padding_box, label_y + label_height + padding_box)

                # Use smaller margin for fallback
                collision = False
                for occupied in occupied_rects:
                    if rectangles_overlap(label_rect, occupied, margin=20):
                        collision = True
                        break

                if not collision:
                    label_data.append((person_id, x_canvas, y_canvas, label_x, label_y, method, name, room))
                    name_box_rect = (label_x - padding_box, label_y - padding_box,
                                    label_x + name_width + padding_box, label_y + name_height + padding_box)
                    room_y_pos = label_y + name_height + padding_box + 10
                    room_box_rect = (label_x - padding_box, room_y_pos - padding_box,
                                    label_x + room_width + padding_box, room_y_pos + room_height + padding_box)
                    occupied_rects.append(name_box_rect)
                    occupied_rects.append(room_box_rect)
                    placed = True
                    break
            if placed:
                break

        # Ultimate fallback if still not placed
        if not placed:
            print(f"⚠️  Could not place label for {name} at any distance")
            # Force placement at default angle with very large distance
            angle_rad = math.radians(315)
            label_x = x_canvas + 1000 * math.cos(angle_rad)
            label_y = y_canvas + 1000 * math.sin(angle_rad)
            label_data.append((person_id, x_canvas, y_canvas, label_x, label_y, method, name, room))

print(f"Calculated {len(label_data)} label positions")

# Draw lines
for person_id, x, y, label_x, label_y, method, name, room in label_data:
    dx = label_x - x
    dy = label_y - y
    distance_actual = math.sqrt(dx*dx + dy*dy)
    if distance_actual > 0:
        edge_x = x + (dx / distance_actual) * 48
        edge_y = y + (dy / distance_actual) * 48
        draw.line([(edge_x, edge_y), (label_x, label_y)], fill=(0, 47, 95, 200), width=6)

# Draw profile pictures
for person_id, x, y, label_x, label_y, method, name, room in label_data:
    pic_path = f'profile_pictures/{person_id}.jpg'
    if os.path.exists(pic_path):
        try:
            profile_pic = Image.open(pic_path).convert('RGBA')
            profile_pic = profile_pic.resize((90, 90), Image.Resampling.LANCZOS)

            mask = Image.new('L', (90, 90), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, 90, 90), fill=255)

            border_size = 96
            border_img = Image.new('RGBA', (border_size, border_size), (0, 0, 0, 0))
            border_draw = ImageDraw.Draw(border_img)
            border_color = (0, 47, 95, 255)
            border_draw.ellipse((0, 0, border_size-1, border_size-1), fill=border_color)

            border_img.paste(profile_pic, (3, 3), mask)

            paste_x = int(x - border_size//2)
            paste_y = int(y - border_size//2)
            canvas.paste(border_img, (paste_x, paste_y), border_img)
        except Exception as e:
            print(f"Error loading profile for {person_id}: {e}")

# Draw labels
for person_id, x, y, label_x, label_y, method, name, room in label_data:
    name_bbox = draw.textbbox((0, 0), name, font=font_name)
    name_width = name_bbox[2] - name_bbox[0]
    name_height = name_bbox[3] - name_bbox[1]

    padding_box = 15
    name_box = [
        label_x - padding_box,
        label_y - padding_box,
        label_x + name_width + padding_box,
        label_y + name_height + padding_box
    ]
    draw.rounded_rectangle(name_box, radius=10, fill=(0, 47, 95, 240))
    draw.text((label_x, label_y), name, fill=(255, 255, 255, 255), font=font_name)

    room_bbox = draw.textbbox((0, 0), room, font=font_room)
    room_width = room_bbox[2] - room_bbox[0]
    room_height = room_bbox[3] - room_bbox[1]
    room_y = label_y + name_height + padding_box + 10

    room_box = [
        label_x - padding_box,
        room_y - padding_box,
        label_x + room_width + padding_box,
        room_y + room_height + padding_box
    ]
    draw.rounded_rectangle(room_box, radius=8, fill=(255, 107, 53, 240))
    draw.text((label_x, room_y), room, fill=(255, 255, 255, 255), font=font_room)

# Save
canvas.save(output_file, 'PNG')
print(f"✅ 16:9 TV map with QR code saved: {output_file}")
print(f"   Dimensions: {TARGET_WIDTH}x{TARGET_HEIGHT} (16:9)")

print(f"\nStats:")
print(f"  Total employees: {len(employees)}")
print(f"  Placed on map: {stats['ocr'] + stats['interpolated'] + stats['zone']}")
