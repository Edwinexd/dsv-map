#!/usr/bin/env python3
"""
Create TV-optimized version with simple but smart label placement
Usage: python3 create_tv_simple_smart.py <employee_json> <output_png>
"""
import sys
import json
import math
from PIL import Image, ImageDraw, ImageFont
import os

if len(sys.argv) != 3:
    print("Usage: python3 create_tv_simple_smart.py <employee_json> <output_png>")
    sys.exit(1)

employee_file = sys.argv[1]
output_file = sys.argv[2]

# Load employee data
with open(employee_file, "r", encoding="utf-8") as f:
    employees = json.load(f)

# Get script directory for loading resource files
script_dir = os.path.dirname(os.path.abspath(__file__))

# Load OCR-detected room positions
room_positions_file = os.path.join(script_dir, "room_positions_easyocr.json")
with open(room_positions_file, "r", encoding="utf-8") as f:
    ocr_rooms = json.load(f)

# Zone coordinates
zone_centers = {
    1: (1521, 1064),
    2: (1720, 1269),
    3: (2203, 551),
    4: (1687, 2218),
    5: (1683, 2522),
    6: (2633, 2519),
    7: (1951, 1570),
    8: (2401, 1821),
}

# Manual positions
manual_positions = {}
try:
    manual_positions_file = os.path.join(script_dir, "manual_positions.json")
    with open(manual_positions_file, "r") as f:
        manual_positions = json.load(f)
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

for emp in employees:
    room = emp.get('room')
    person_id = emp['person_id']
    name = emp['name']

    if person_id in manual_positions:
        x, y = manual_positions[person_id]
        employee_coords[person_id] = (x, y, 'manual', None)
        stats['ocr'] += 1
        continue

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

# Spread out overlapping employees using force-directed approach
print("\nSpreading out overlapping employees...")
MIN_DISTANCE = 150  # Minimum distance between profile pictures (border size is 128)
MAX_ITERATIONS = 100
SPREAD_FACTOR = 0.3  # How much to move apart (0.0 to 1.0)

def get_distance(p1, p2):
    """Calculate distance between two points"""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def spread_overlapping_employees():
    """Move overlapping employees apart"""
    coords_list = [(pid, x, y, method, zone) for pid, (x, y, method, zone) in employee_coords.items()]

    for iteration in range(MAX_ITERATIONS):
        moved = False

        for i, (pid1, x1, y1, method1, zone1) in enumerate(coords_list):
            # Calculate repulsion forces from nearby employees
            force_x = 0
            force_y = 0

            for j, (pid2, x2, y2, method2, zone2) in enumerate(coords_list):
                if i == j:
                    continue

                dist = get_distance((x1, y1), (x2, y2))

                # If too close, apply repulsion force
                if dist < MIN_DISTANCE and dist > 0:
                    # Calculate repulsion direction (away from other person)
                    dx = x1 - x2
                    dy = y1 - y2

                    # Normalize and scale by how much overlap
                    overlap = MIN_DISTANCE - dist
                    force_magnitude = overlap / MIN_DISTANCE

                    force_x += (dx / dist) * force_magnitude
                    force_y += (dy / dist) * force_magnitude

            # Apply forces if any
            if abs(force_x) > 0.01 or abs(force_y) > 0.01:
                # Move by a fraction of the force
                new_x = x1 + force_x * SPREAD_FACTOR * MIN_DISTANCE
                new_y = y1 + force_y * SPREAD_FACTOR * MIN_DISTANCE

                # Update in both the list and the dict
                coords_list[i] = (pid1, new_x, new_y, method1, zone1)
                employee_coords[pid1] = (new_x, new_y, method1, zone1)
                moved = True

        # Stop if no more movement
        if not moved:
            print(f"  Converged after {iteration + 1} iterations")
            break

    if moved:
        print(f"  Completed {MAX_ITERATIONS} iterations")

spread_overlapping_employees()
print(f"✓ Spread out overlapping employees")

# Load floor plan and expand
print("Loading floor plan...")
floor_plan_original = Image.open('floor_plan.png').convert('RGBA')
img_width, img_height = floor_plan_original.size

# Expand canvas - minimal padding
padding = 250
new_width = img_width + (padding * 2)
new_height = img_height + (padding * 2)

floor_plan = Image.new('RGBA', (new_width, new_height), (255, 255, 255, 255))
floor_plan.paste(floor_plan_original, (padding, padding))

draw = ImageDraw.Draw(floor_plan)

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

font_name = load_font(50)
font_room = load_font(38)

# Simple collision detection
def rectangles_overlap(r1, r2, margin=10):
    return not (r1[2] + margin < r2[0] or
                r1[0] - margin > r2[2] or
                r1[3] + margin < r2[1] or
                r1[1] - margin > r2[3])

# Detect clusters - find how many people are nearby
def count_nearby(x, y, coords, radius=300):
    count = 0
    for pid, (px, py, _, _) in coords.items():
        dist = math.sqrt((px - x)**2 + (py - y)**2)
        if dist < radius and dist > 0:
            count += 1
    return count

# Calculate label positions with simple angle-based placement
print("Calculating label positions...")
label_data = []
occupied_rects = []

# Preferred angles to try (in degrees) - start with down-right, then try others
angle_preferences = [315, 45, 270, 225, 0, 135, 90, 180]  # Down-right first

# FIRST: Add ALL profile pictures to occupied space so labels can't go over them
for emp in employees:
    person_id = emp['person_id']
    if person_id in employee_coords:
        x, y, method, zone = employee_coords[person_id]
        x += padding
        y += padding
        pic_rect = (x - 64, y - 64, x + 64, y + 64)
        occupied_rects.append(pic_rect)

print(f"Reserved space for {len(occupied_rects)} profile pictures")

# Sort employees by cluster density (most crowded first gets priority)
employees_with_density = []
for emp in employees:
    person_id = emp['person_id']
    if person_id in employee_coords:
        x, y, method, zone = employee_coords[person_id]
        density = count_nearby(x, y, employee_coords)
        employees_with_density.append((density, emp))

employees_with_density.sort(reverse=True, key=lambda x: x[0])

for density, emp in employees_with_density:
    person_id = emp['person_id']
    if person_id not in employee_coords:
        continue

    x, y, method, zone = employee_coords[person_id]
    x += padding  # Adjust for canvas padding
    y += padding

    name = emp['name']
    room = emp.get('room', '')

    # Calculate label size
    name_bbox = draw.textbbox((0, 0), name, font=font_name)
    room_bbox = draw.textbbox((0, 0), room, font=font_room)
    label_width = max(name_bbox[2] - name_bbox[0], room_bbox[2] - room_bbox[0]) + 40
    label_height = (name_bbox[3] - name_bbox[1]) + (room_bbox[3] - room_bbox[1]) + 50

    # Detect if in a cluster and use larger distance
    if density >= 5:  # Dense cluster
        distance = 400
        distances_to_try = [400, 500, 600, 700, 800]
    elif density >= 3:  # Medium cluster
        distance = 300
        distances_to_try = [300, 400, 500, 600]
    else:  # Sparse area
        distance = 200
        distances_to_try = [200, 280, 350]

    # Try each angle and distance until we find one that doesn't collide
    placed = False
    for dist in distances_to_try:
        for angle_deg in angle_preferences:
            angle_rad = math.radians(angle_deg)
            label_x = x + dist * math.cos(angle_rad)
            label_y = y + dist * math.sin(angle_rad)

            # Check bounds
            if (label_x < 50 or label_x + label_width > new_width - 50 or
                label_y < 50 or label_y + label_height > new_height - 50):
                continue

            label_rect = (label_x, label_y, label_x + label_width, label_y + label_height)

            # Check collisions with larger margin for clusters
            collision_margin = 60 if density >= 5 else (50 if density >= 3 else 30)
            collision = False
            for occupied in occupied_rects:
                if rectangles_overlap(label_rect, occupied, margin=collision_margin):
                    collision = True
                    break

            if not collision:
                label_data.append((person_id, x, y, label_x, label_y, method, name, room))
                occupied_rects.append(label_rect)
                placed = True
                break

        if placed:
            break

    if not placed:
        # Fallback: just place it at the first angle anyway
        angle_rad = math.radians(315)  # Down-right
        label_x = x + distance * math.cos(angle_rad)
        label_y = y + distance * math.sin(angle_rad)
        label_data.append((person_id, x, y, label_x, label_y, method, name, room))

print(f"Calculated {len(label_data)} label positions")

# FIRST PASS: Draw lines
for person_id, x, y, label_x, label_y, method, name, room in label_data:
    dx = label_x - x
    dy = label_y - y
    distance_actual = math.sqrt(dx*dx + dy*dy)
    if distance_actual > 0:
        edge_x = x + (dx / distance_actual) * 64
        edge_y = y + (dy / distance_actual) * 64
        draw.line([(edge_x, edge_y), (label_x, label_y)], fill=(120, 120, 120, 150), width=8)

# SECOND PASS: Draw profile pictures
for person_id, x, y, label_x, label_y, method, name, room in label_data:
    pic_path = f'profile_pictures/{person_id}.jpg'
    if os.path.exists(pic_path):
        try:
            profile_pic = Image.open(pic_path).convert('RGBA')
            profile_pic = profile_pic.resize((120, 120), Image.Resampling.LANCZOS)

            mask = Image.new('L', (120, 120), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, 120, 120), fill=255)

            border_size = 128
            border_img = Image.new('RGBA', (border_size, border_size), (0, 0, 0, 0))
            border_draw = ImageDraw.Draw(border_img)
            border_color = (0, 47, 95, 255)
            if method == 'manual':
                border_color = (255, 107, 53, 255)
            border_draw.ellipse((0, 0, border_size-1, border_size-1), fill=border_color)

            border_img.paste(profile_pic, (4, 4), mask)

            paste_x = int(x - border_size//2)
            paste_y = int(y - border_size//2)
            floor_plan.paste(border_img, (paste_x, paste_y), border_img)
        except Exception as e:
            print(f"Error loading profile for {person_id}: {e}")

# THIRD PASS: Draw labels
for person_id, x, y, label_x, label_y, method, name, room in label_data:
    name_bbox = draw.textbbox((0, 0), name, font=font_name)
    name_width = name_bbox[2] - name_bbox[0]
    name_height = name_bbox[3] - name_bbox[1]

    padding_box = 20
    name_box = [
        label_x - padding_box,
        label_y - padding_box,
        label_x + name_width + padding_box,
        label_y + name_height + padding_box
    ]
    draw.rounded_rectangle(name_box, radius=12, fill=(0, 47, 95, 240))
    draw.text((label_x, label_y), name, fill=(255, 255, 255, 255), font=font_name)

    room_bbox = draw.textbbox((0, 0), room, font=font_room)
    room_width = room_bbox[2] - room_bbox[0]
    room_height = room_bbox[3] - room_bbox[1]
    room_y = label_y + name_height + padding_box + 15

    room_box = [
        label_x - padding_box,
        room_y - padding_box,
        label_x + room_width + padding_box,
        room_y + room_height + padding_box
    ]
    draw.rounded_rectangle(room_box, radius=10, fill=(255, 107, 53, 240))
    draw.text((label_x, room_y), room, fill=(255, 255, 255, 255), font=font_room)

# Save
floor_plan.save(output_file, 'PNG')
print(f"✅ TV-optimized map saved: {output_file}")

print(f"\nStats:")
print(f"  Total employees: {len(employees)}")
print(f"  Placed on map: {stats['ocr'] + stats['interpolated'] + stats['zone']}")
print(f"  Exact OCR: {stats['ocr']}")
print(f"  Interpolated: {stats['interpolated']}")
print(f"  Zone-based: {stats['zone']}")
