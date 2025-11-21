#!/usr/bin/env python3
"""
Test collision detection by generating a debug image showing collision boxes
"""
import json
import math
from PIL import Image, ImageDraw, ImageFont
import os

# Load test data
with open('temp_test_act.json', 'r') as f:
    employees = json.load(f)

with open("/Users/edwin/dsv-map/room_positions_easyocr.json", "r", encoding="utf-8") as f:
    ocr_rooms = json.load(f)

zone_centers = {
    1: (1521, 1064), 2: (1720, 1269), 3: (2203, 551), 4: (1687, 2218),
    5: (1683, 2522), 6: (2633, 2519), 7: (1951, 1570), 8: (2401, 1821),
}

manual_positions = {}
try:
    with open("/Users/edwin/dsv-map/manual_positions.json", "r") as f:
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
employees_by_zone = {}

for emp in employees:
    room = emp.get('room')
    person_id = emp['person_id']

    if person_id in manual_positions:
        x, y = manual_positions[person_id]
        employee_coords[person_id] = (x, y, 'manual', None)
        continue

    if not room or room == "None":
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
        continue

    result = interpolate_room_position(room, ocr_rooms)
    if result:
        x, y, method = result
        employee_coords[person_id] = (x, y, method, None)
        continue

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

print(f"Placed {len(employee_coords)} employees")

# Load floor plan
floor_plan_original = Image.open('floor_plan.png').convert('RGBA')
img_width, img_height = floor_plan_original.size

TARGET_WIDTH = 3840
TARGET_HEIGHT = 2160
SIDE_PANEL_WIDTH = 800
MAP_AREA_WIDTH = TARGET_WIDTH - SIDE_PANEL_WIDTH
MAP_AREA_HEIGHT = TARGET_HEIGHT

scale = min(MAP_AREA_WIDTH / img_width, MAP_AREA_HEIGHT / img_height) * 0.85
new_map_width = int(img_width * scale)
new_map_height = int(img_height * scale)

map_offset_x = (MAP_AREA_WIDTH - new_map_width) // 2
map_offset_y = (MAP_AREA_HEIGHT - new_map_height) // 2

canvas = Image.new('RGB', (TARGET_WIDTH, TARGET_HEIGHT), (255, 255, 255))
floor_plan_resized = floor_plan_original.resize((new_map_width, new_map_height), Image.Resampling.LANCZOS)
canvas.paste(floor_plan_resized, (map_offset_x, map_offset_y), floor_plan_resized)

draw = ImageDraw.Draw(canvas)

try:
    font_name = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
    font_room = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
except:
    font_name = ImageFont.load_default()
    font_room = ImageFont.load_default()

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

# Reserve space for profile pictures
occupied_rects = []
for emp in employees:
    person_id = emp['person_id']
    if person_id in employee_coords:
        x, y, method, zone = employee_coords[person_id]
        x_canvas = map_offset_x + int(x * scale)
        y_canvas = map_offset_y + int(y * scale)
        pic_rect = (x_canvas - 48, y_canvas - 48, x_canvas + 48, y_canvas + 48)
        occupied_rects.append(pic_rect)

print(f"Reserved {len(occupied_rects)} profile picture spaces")

# Sort by density
employees_with_density = []
for emp in employees:
    person_id = emp['person_id']
    if person_id in employee_coords:
        x, y, method, zone = employee_coords[person_id]
        density = count_nearby(x, y, employee_coords)
        employees_with_density.append((density, emp))

employees_with_density.sort(reverse=True, key=lambda x: x[0])

# Place labels and check for collisions
label_data = []
collision_count = 0
overlapping_pairs = []

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

    padding_box = 15
    label_width = max(name_width, room_width) + (padding_box * 2)
    label_height = (padding_box + name_height + padding_box) + 10 + (padding_box + room_height + padding_box)

    if density >= 5:
        distances_to_try = [300, 400, 500, 600, 700, 800]
    elif density >= 3:
        distances_to_try = [250, 350, 450, 550, 650]
    else:
        distances_to_try = [180, 250, 320, 400, 500]

    placed = False
    for dist in distances_to_try:
        for angle_deg in angle_preferences:
            angle_rad = math.radians(angle_deg)
            label_x = x_canvas + dist * math.cos(angle_rad)
            label_y = y_canvas + dist * math.sin(angle_rad)

            if (label_x < 50 or label_x + label_width > MAP_AREA_WIDTH - 50 or
                label_y < 50 or label_y + label_height > TARGET_HEIGHT - 50):
                continue

            label_rect = (label_x, label_y, label_x + label_width, label_y + label_height)

            collision_margin = 80 if density >= 5 else (70 if density >= 3 else 60)
            collision = False
            for occupied in occupied_rects:
                if rectangles_overlap(label_rect, occupied, margin=collision_margin):
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

    if not placed:
        print(f"⚠️  Could not place label for: {name}")

print(f"Placed {len(label_data)} labels")

# Now check for actual overlaps in the placed labels
print("\nChecking for actual overlaps...")
for i, (pid1, x1, y1, lx1, ly1, m1, name1, room1) in enumerate(label_data):
    name_bbox1 = draw.textbbox((0, 0), name1, font=font_name)
    room_bbox1 = draw.textbbox((0, 0), room1, font=font_room)
    nw1 = name_bbox1[2] - name_bbox1[0]
    nh1 = name_bbox1[3] - name_bbox1[1]
    rw1 = room_bbox1[2] - room_bbox1[0]
    rh1 = room_bbox1[3] - room_bbox1[1]

    padding = 15
    name_box1 = (lx1 - padding, ly1 - padding, lx1 + nw1 + padding, ly1 + nh1 + padding)
    room_y1 = ly1 + nh1 + padding + 10
    room_box1 = (lx1 - padding, room_y1 - padding, lx1 + rw1 + padding, room_y1 + rh1 + padding)

    for j, (pid2, x2, y2, lx2, ly2, m2, name2, room2) in enumerate(label_data[i+1:], i+1):
        name_bbox2 = draw.textbbox((0, 0), name2, font=font_name)
        room_bbox2 = draw.textbbox((0, 0), room2, font=font_room)
        nw2 = name_bbox2[2] - name_bbox2[0]
        nh2 = name_bbox2[3] - name_bbox2[1]
        rw2 = room_bbox2[2] - room_bbox2[0]
        rh2 = room_bbox2[3] - room_bbox2[1]

        name_box2 = (lx2 - padding, ly2 - padding, lx2 + nw2 + padding, ly2 + nh2 + padding)
        room_y2 = ly2 + nh2 + padding + 10
        room_box2 = (lx2 - padding, room_y2 - padding, lx2 + rw2 + padding, room_y2 + rh2 + padding)

        # Check all combinations
        if rectangles_overlap(name_box1, name_box2, margin=0):
            print(f"❌ OVERLAP: {name1} (name) overlaps with {name2} (name)")
            collision_count += 1
            overlapping_pairs.append(((name1, 'name'), (name2, 'name')))
        if rectangles_overlap(name_box1, room_box2, margin=0):
            print(f"❌ OVERLAP: {name1} (name) overlaps with {name2} (room: {room2})")
            collision_count += 1
            overlapping_pairs.append(((name1, 'name'), (name2, 'room')))
        if rectangles_overlap(room_box1, name_box2, margin=0):
            print(f"❌ OVERLAP: {name1} (room: {room1}) overlaps with {name2} (name)")
            collision_count += 1
            overlapping_pairs.append(((name1, 'room'), (name2, 'name')))
        if rectangles_overlap(room_box1, room_box2, margin=0):
            print(f"❌ OVERLAP: {name1} (room: {room1}) overlaps with {name2} (room: {room2})")
            collision_count += 1
            overlapping_pairs.append(((name1, 'room'), (name2, 'room')))

print(f"\n{'='*60}")
if collision_count == 0:
    print("✅ No overlaps detected!")
else:
    print(f"❌ Found {collision_count} overlaps")
print(f"{'='*60}")
