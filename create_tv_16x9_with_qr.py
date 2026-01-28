#!/usr/bin/env python3
"""
Create TV-optimized 16:9 version with QR code and info panel
Usage: python3 create_tv_16x9_with_qr.py <employee_json> <output_png> [--title <title>]
"""

import argparse
import json
import math
import os
import random
from datetime import date

from PIL import Image, ImageDraw, ImageFont

import bluelight_filter
import event_utils


def main(employee_json, output_png, title=None, bluelight_filter_force=None):
    employee_file = employee_json
    output_file = output_png

    # Load employee data
    with open(employee_file, encoding="utf-8") as f:
        employees = json.load(f)

    # Get script directory for loading resource files
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Check if coordinates are pre-computed in the JSON (from main.py)
    has_precomputed_coords = any("x" in emp and "y" in emp for emp in employees)

    employee_coords = {}
    stats = {"placed": 0, "no_position": 0}

    if has_precomputed_coords:
        # Use pre-computed coordinates from JSON
        print("Using pre-computed coordinates from input data...")
        for emp in employees:
            person_id = emp["person_id"]
            if "x" in emp and "y" in emp:
                employee_coords[person_id] = (emp["x"], emp["y"], "precomputed", None)
                stats["placed"] += 1
            else:
                stats["no_position"] += 1
    else:
        # Fallback: fetch from Clickmap (for standalone usage)
        import clickmap_positions

        print("Fetching positions from DSV Clickmap...")
        clickmap_by_person = clickmap_positions.fetch_clickmap_positions_by_person()
        print(f"  Found {len(clickmap_by_person)} occupied positions in Clickmap")

        # Location overrides (user-submitted room changes)
        location_overrides = {}
        try:
            location_overrides_file = os.path.join(script_dir, "data", "location_overrides.json")
            with open(location_overrides_file) as f:
                data = json.load(f)
                location_overrides = {k: v for k, v in data.items() if not k.startswith("_")}
        except FileNotFoundError:
            pass

        print(f"Processing {len(employees)} employees...")

        for emp in employees:
            person_id = emp["person_id"]
            name = emp["name"]

            # Look up position in Clickmap by person name (with fuzzy matching)
            matched = False
            for clickmap_name, (x, y, place_name) in clickmap_by_person.items():
                if clickmap_positions.names_match(name, clickmap_name):
                    emp["room"] = place_name  # Update room from clickmap
                    employee_coords[person_id] = (x, y, "clickmap", None)
                    stats["placed"] += 1
                    matched = True
                    break
            if not matched:
                stats["no_position"] += 1

        # Apply location overrides (these take precedence)
        clickmap_pos = clickmap_positions.fetch_clickmap_positions()
        for emp in employees:
            person_id = emp["person_id"]
            if person_id in location_overrides:
                override = location_overrides[person_id]
                # Handle new dict format: {"room": "...", "unit": "..."}
                override_room = override.get("room") if isinstance(override, dict) else override
                if override_room:
                    emp["room"] = override_room
                    if override_room in clickmap_pos:
                        x, y = clickmap_pos[override_room]
                        was_placed = person_id in employee_coords
                        employee_coords[person_id] = (x, y, "clickmap", None)
                        if not was_placed:
                            stats["placed"] += 1
                            stats["no_position"] -= 1
                    print(f"Applied override for {emp['name']}: room={override_room}")

    print(f"Placed {stats['placed']}/{len(employees)} employees")

    # Spread out overlapping employees
    print("\nSpreading out overlapping employees...")
    min_distance = 150
    max_iterations = 100
    spread_factor = 0.3

    def get_distance(p1, p2):
        return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

    def clamp(value, min_val, max_val):
        return max(min_val, min(max_val, value))

    def spread_overlapping_employees(boundary_width, boundary_height):
        # Define map boundaries for clamping (with margin for profile pictures)
        map_margin = 100  # Keep employees this far from edges
        min_map_x = map_margin
        max_map_x = boundary_width - map_margin
        min_map_y = map_margin
        max_map_y = boundary_height - map_margin

        coords_list = [
            (pid, x, y, method, zone) for pid, (x, y, method, zone) in employee_coords.items()
        ]

        for iteration in range(max_iterations):
            moved = False

            for i, (pid1, x1, y1, method1, zone1) in enumerate(coords_list):
                force_x = 0
                force_y = 0

                for j, (_pid2, x2, y2, _method2, _zone2) in enumerate(coords_list):
                    if i == j:
                        continue

                    dist = get_distance((x1, y1), (x2, y2))

                    if dist < min_distance and dist > 0:
                        dx = x1 - x2
                        dy = y1 - y2
                        overlap = min_distance - dist
                        force_magnitude = overlap / min_distance
                        force_x += (dx / dist) * force_magnitude
                        force_y += (dy / dist) * force_magnitude

                if abs(force_x) > 0.01 or abs(force_y) > 0.01:
                    new_x = x1 + force_x * spread_factor * min_distance
                    new_y = y1 + force_y * spread_factor * min_distance
                    # Clamp to map boundaries
                    new_x = clamp(new_x, min_map_x, max_map_x)
                    new_y = clamp(new_y, min_map_y, max_map_y)
                    coords_list[i] = (pid1, new_x, new_y, method1, zone1)
                    employee_coords[pid1] = (new_x, new_y, method1, zone1)
                    moved = True

            if not moved:
                print(f"  Converged after {iteration + 1} iterations")
                break

        if moved:
            print(f"  Completed {max_iterations} iterations")

    # Floor plan is 3056x3056 pixels, coordinates are in that space
    spread_overlapping_employees(3056, 3056)
    print("✓ Spread out overlapping employees")

    # Load floor plan
    print("Loading floor plan...")
    floor_plan_path = os.path.join(script_dir, "assets", "floor_plan.png")
    floor_plan_original = Image.open(floor_plan_path).convert("RGBA")
    img_width, img_height = floor_plan_original.size

    # Calculate 16:9 dimensions
    # Target aspect ratio 16:9
    # We'll make the main map area fit nicely and add a side panel
    target_width = 3840  # 4K width (or 1920 for Full HD)
    target_height = 2160  # 4K height (or 1080 for Full HD)
    side_panel_width = 800  # Width of the info panel on the right

    # Calculate map area dimensions (left side of the image)
    map_area_width = target_width - side_panel_width
    map_area_height = target_height

    # Scale floor plan to fit in the map area while maintaining aspect ratio
    scale = min(map_area_width / img_width, map_area_height / img_height) * 0.85
    new_map_width = int(img_width * scale)
    new_map_height = int(img_height * scale)

    # Center the map in the map area
    map_offset_x = (map_area_width - new_map_width) // 2
    map_offset_y = (map_area_height - new_map_height) // 2

    # Create the final 16:9 canvas
    canvas = Image.new("RGB", (target_width, target_height), (255, 255, 255))

    # Resize and paste floor plan
    floor_plan_resized = floor_plan_original.resize(
        (new_map_width, new_map_height), Image.Resampling.LANCZOS
    )
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
            except OSError:
                continue
        # Fallback to default
        print("Warning: Could not load any fonts, using default (size will be small)")
        return ImageFont.load_default()

    # Load seasonal events from assets/events/
    today = date.today()
    events_dir = os.path.join(script_dir, "assets", "events")
    if os.path.isdir(events_dir):
        for event_name in os.listdir(events_dir):
            event_path = os.path.join(events_dir, event_name)
            config_path = os.path.join(event_path, "config.json")
            if not os.path.isfile(config_path):
                continue

            try:
                with open(config_path, encoding="utf-8") as f:
                    config = json.load(f)

                # Check if event is active
                start = (config["start_month"], config["start_day"])
                end = (config["end_month"], config["end_day"])
                current = (today.month, today.day)

                if start <= end:
                    is_active = start <= current <= end
                else:
                    # Wraps around year (e.g., Dec 15 - Jan 5)
                    is_active = current >= start or current <= end

                if not is_active:
                    continue

                def get_position(position, padding, width, height):
                    """Calculate x, y coordinates for an asset based on position string."""
                    offset_x, offset_y = 0, 0
                    if position == "bottom-left":
                        offset_x = padding
                        offset_y = target_height - height - padding
                    elif position == "bottom-right":
                        offset_x = map_area_width - width - padding
                        offset_y = target_height - height - padding
                    elif position == "top-left":
                        offset_x = padding
                        offset_y = padding
                    elif position == "top-right":
                        offset_x = map_area_width - width - padding
                        offset_y = padding
                    return offset_x, offset_y

                # Load event assets
                assets = config.get("assets", [])
                for asset in assets:
                    asset_type = asset.get("type", "image")
                    padding = asset.get("padding", 30)
                    position = asset.get("position", "bottom-left")

                    if asset_type == "image":
                        image_path = os.path.join(event_path, asset.get("file", "image.png"))
                        event_img = Image.open(image_path).convert("RGBA")

                        asset_scale = asset.get("scale", 1.0)
                        img_width = int(event_img.width * asset_scale)
                        img_height = int(event_img.height * asset_scale)
                        event_img = event_img.resize(
                            (img_width, img_height), Image.Resampling.LANCZOS
                        )

                        img_x, img_y = get_position(position, padding, img_width, img_height)
                        img_x += asset.get("offset_x", 0)
                        img_y += asset.get("offset_y", 0)
                        canvas.paste(event_img, (img_x, img_y), event_img)
                        print(f"Added {event_name} image: {asset.get('file', 'image.png')}")

                    elif asset_type == "message":
                        texts = asset.get("texts", [])
                        if not texts:
                            continue
                        text = random.choice(texts)
                        font_size = asset.get("font_size", 36)
                        color = tuple(asset.get("color", [0, 0, 0]))
                        font = load_font(font_size)

                        text_bbox = draw.textbbox((0, 0), text, font=font)
                        text_width = text_bbox[2] - text_bbox[0]
                        text_height = text_bbox[3] - text_bbox[1]

                        text_x, text_y = get_position(position, padding, text_width, text_height)
                        text_x += asset.get("offset_x", 0)
                        text_y += asset.get("offset_y", 0)

                        # Handle text alignment
                        align = asset.get("align", "left")
                        if align == "center":
                            text_x -= text_width // 2
                        elif align == "right":
                            text_x -= text_width

                        draw.text((text_x, text_y), text, fill=color, font=font)
                        print(f"Added {event_name} message: {text}")

            except (OSError, KeyError, json.JSONDecodeError) as e:
                print(f"Warning: Could not load event {event_name}: {e}")

    font_title = load_font(80)
    font_info = load_font(50)
    font_name = load_font(40)
    font_room = load_font(32)

    # Draw side panel background
    panel_x = map_area_width
    draw.rectangle([panel_x, 0, target_width, target_height], fill=(0, 47, 95))

    # Add title to side panel
    display_title = title if title else "DSV Staff Map"
    title_bbox = draw.textbbox((0, 0), display_title, font=font_title)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = panel_x + (side_panel_width - title_width) // 2
    draw.text((title_x, 80), display_title, fill=(255, 255, 255), font=font_title)

    # Load and paste location update QR code (main QR code)
    print("Loading location update QR code...")
    try:
        qr_path = os.path.join(script_dir, "assets", "qr_fix_location.png")
        qr_img = Image.open(qr_path).convert("RGBA")
        qr_size = 500
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
        qr_x = panel_x + (side_panel_width - qr_size) // 2
        qr_y = 250
        canvas.paste(qr_img, (qr_x, qr_y), qr_img)

        # Add instructions below QR code
        instruction_y = qr_y + qr_size + 30
        instruction_lines = ["Missing or in the", "wrong place?", "Scan to update!"]
        for i, line in enumerate(instruction_lines):
            line_bbox = draw.textbbox((0, 0), line, font=font_info)
            line_width = line_bbox[2] - line_bbox[0]
            line_x = panel_x + (side_panel_width - line_width) // 2
            draw.text((line_x, instruction_y + i * 60), line, fill=(255, 255, 255), font=font_info)

    except OSError as e:
        print(f"Warning: Could not load qr_fix_location.png: {e}")

    # Add statistics (smaller font, single line)
    stats_y = qr_y + qr_size + 230
    total_placed = stats["placed"]

    stats_text = f"({total_placed} out of {len(employees)} displayed)"
    stats_bbox = draw.textbbox((0, 0), stats_text, font=font_name)
    stats_width = stats_bbox[2] - stats_bbox[0]
    stats_x = panel_x + (side_panel_width - stats_width) // 2
    draw.text((stats_x, stats_y), stats_text, fill=(255, 255, 255), font=font_name)

    # Add repository QR code and SU logo at the bottom
    print("Loading repository QR code and SU logo...")
    try:
        # Load SU logo
        logo_path = os.path.join(script_dir, "assets", "SU_logotyp_Landscape_Invert_1000px.png")
        logo_img = Image.open(logo_path).convert("RGBA")
        logo_width = 700
        aspect_ratio = logo_img.height / logo_img.width
        logo_height = int(logo_width * aspect_ratio)
        logo_img = logo_img.resize((logo_width, logo_height), Image.Resampling.LANCZOS)

        logo_x = panel_x + (side_panel_width - logo_width) // 2
        logo_y = target_height - logo_height - 100
        canvas.paste(logo_img, (logo_x, logo_y), logo_img)

        # Load repository QR code (same height as logo, positioned above it)
        try:
            repo_qr_path = os.path.join(script_dir, "assets", "repo_qr.png")
            repo_qr_img = Image.open(repo_qr_path).convert("RGBA")
            repo_qr_height = logo_height
            qr_aspect_ratio = repo_qr_img.width / repo_qr_img.height
            repo_qr_width = int(repo_qr_height * qr_aspect_ratio)
            repo_qr_img = repo_qr_img.resize(
                (repo_qr_width, repo_qr_height), Image.Resampling.LANCZOS
            )

            # Position QR above logo with some padding
            repo_qr_y = logo_y - repo_qr_height - 60
            repo_qr_x = panel_x + 50  # Left align with some padding

            canvas.paste(repo_qr_img, (repo_qr_x, repo_qr_y), repo_qr_img)

            # Add GitHub repo text to the right of QR code (three lines)
            repo_lines = ["Github:", "@Edwinexd/", "dsv-map"]
            repo_text_x = repo_qr_x + repo_qr_width + 20
            # Start position to center all three lines vertically with QR
            line_height = 55
            total_text_height = len(repo_lines) * line_height
            repo_text_y = repo_qr_y + (repo_qr_height - total_text_height) // 2

            for i, line in enumerate(repo_lines):
                draw.text(
                    (repo_text_x, repo_text_y + i * line_height),
                    line,
                    fill=(255, 255, 255),
                    font=font_info,
                )

        except OSError as e:
            print(f"Warning: Could not load repo_qr.png: {e}")

    except OSError as e:
        print(f"Warning: Could not load SU_logotyp_Landscape_Invert_1000px.png: {e}")

    # Calculate label positions with multi-attempt optimization
    print("Calculating label positions...")

    def rectangles_overlap(r1, r2, margin=10):
        return not (
            r1[2] + margin < r2[0]
            or r1[0] - margin > r2[2]
            or r1[3] + margin < r2[1]
            or r1[1] - margin > r2[3]
        )

    def count_nearby(x, y, coords, radius=300):
        count = 0
        for _pid, (px, py, _, _) in coords.items():
            dist = math.sqrt((px - x) ** 2 + (py - y) ** 2)
            if dist < radius and dist > 0:
                count += 1
        return count

    # Reserve space for all profile pictures (base rects for all attempts)
    base_occupied_rects = []
    for emp in employees:
        person_id = emp["person_id"]
        if person_id in employee_coords:
            x, y, method, zone = employee_coords[person_id]
            x_canvas = map_offset_x + int(x * scale)
            y_canvas = map_offset_y + int(y * scale)
            pic_rect = (x_canvas - 48, y_canvas - 48, x_canvas + 48, y_canvas + 48)
            base_occupied_rects.append(pic_rect)

    print(f"Reserved space for {len(base_occupied_rects)} profile pictures")

    # Build employee list with density info
    employees_with_info = []
    for emp in employees:
        person_id = emp["person_id"]
        if person_id in employee_coords:
            x, y, method, zone = employee_coords[person_id]
            density = count_nearby(x, y, employee_coords)
            x_canvas = map_offset_x + int(x * scale)
            y_canvas = map_offset_y + int(y * scale)
            employees_with_info.append((density, x_canvas, y_canvas, emp))

    def try_placement(employee_order, angle_prefs, verbose=False):
        """Try a placement configuration, return (label_data, score)."""
        label_data = []
        occupied_rects = list(base_occupied_rects)  # Fresh copy
        score = 0  # Lower is better

        for density, x_canvas, y_canvas, emp in employee_order:
            person_id = emp["person_id"]
            x, y, method, zone = employee_coords[person_id]
            name = emp["name"]
            room = emp.get("room", "")

            name_bbox = draw.textbbox((0, 0), name, font=font_name)
            room_bbox = draw.textbbox((0, 0), room, font=font_room)
            name_width = name_bbox[2] - name_bbox[0]
            name_height = name_bbox[3] - name_bbox[1]
            room_width = room_bbox[2] - room_bbox[0]
            room_height = room_bbox[3] - room_bbox[1]

            padding_box = 15
            label_width = max(name_width, room_width) + (padding_box * 2)
            label_height = (
                (padding_box + name_height + padding_box)
                + 10
                + (padding_box + room_height + padding_box)
            )

            if density >= 5:
                distances_to_try = [300, 400, 500, 600, 700, 800]
            elif density >= 3:
                distances_to_try = [250, 350, 450, 550, 650]
            else:
                distances_to_try = [180, 250, 320, 400, 500]

            placed = False

            # Try direct placement
            for dist in distances_to_try:
                for angle_deg in angle_prefs:
                    angle_rad = math.radians(angle_deg)
                    label_x = x_canvas + dist * math.cos(angle_rad)
                    label_y = y_canvas + dist * math.sin(angle_rad)

                    if (
                        label_x - padding_box < 50
                        or label_x + label_width + padding_box > map_area_width - 50
                        or label_y - padding_box < 50
                        or label_y + label_height + padding_box > target_height - 50
                    ):
                        continue

                    label_rect = (
                        label_x - padding_box,
                        label_y - padding_box,
                        label_x + label_width + padding_box,
                        label_y + label_height + padding_box,
                    )

                    collision_margin = 40 if density >= 5 else (30 if density >= 3 else 20)
                    collision = False
                    for occupied in occupied_rects:
                        if rectangles_overlap(label_rect, occupied, margin=collision_margin):
                            collision = True
                            break

                    if not collision:
                        label_data.append(
                            (
                                person_id,
                                x_canvas,
                                y_canvas,
                                label_x,
                                label_y,
                                method,
                                name,
                                room,
                                None,
                            )
                        )
                        name_box_rect = (
                            label_x - padding_box,
                            label_y - padding_box,
                            label_x + name_width + padding_box,
                            label_y + name_height + padding_box,
                        )
                        room_y_pos = label_y + name_height + padding_box + 10
                        room_box_rect = (
                            label_x - padding_box,
                            room_y_pos - padding_box,
                            label_x + room_width + padding_box,
                            room_y_pos + room_height + padding_box,
                        )
                        occupied_rects.append(name_box_rect)
                        occupied_rects.append(room_box_rect)
                        placed = True
                        break
                if placed:
                    break

            # Extended distance fallback
            if not placed:
                for dist in [600, 700, 800, 900, 1000]:
                    for angle_deg in angle_prefs:
                        angle_rad = math.radians(angle_deg)
                        label_x = x_canvas + dist * math.cos(angle_rad)
                        label_y = y_canvas + dist * math.sin(angle_rad)

                        if (
                            label_x - padding_box < 50
                            or label_x + label_width + padding_box > map_area_width - 50
                            or label_y - padding_box < 50
                            or label_y + label_height + padding_box > target_height - 50
                        ):
                            continue

                        label_rect = (
                            label_x - padding_box,
                            label_y - padding_box,
                            label_x + label_width + padding_box,
                            label_y + label_height + padding_box,
                        )

                        collision = False
                        for occupied in occupied_rects:
                            if rectangles_overlap(label_rect, occupied, margin=20):
                                collision = True
                                break

                        if not collision:
                            label_data.append(
                                (
                                    person_id,
                                    x_canvas,
                                    y_canvas,
                                    label_x,
                                    label_y,
                                    method,
                                    name,
                                    room,
                                    None,
                                )
                            )
                            name_box_rect = (
                                label_x - padding_box,
                                label_y - padding_box,
                                label_x + name_width + padding_box,
                                label_y + name_height + padding_box,
                            )
                            room_y_pos = label_y + name_height + padding_box + 10
                            room_box_rect = (
                                label_x - padding_box,
                                room_y_pos - padding_box,
                                label_x + room_width + padding_box,
                                room_y_pos + room_height + padding_box,
                            )
                            occupied_rects.append(name_box_rect)
                            occupied_rects.append(room_box_rect)
                            placed = True
                            score += 1  # Penalty for extended
                            break
                    if placed:
                        break

            # Elbow line fallback
            if not placed:
                elbow_routes = [
                    (0, -150, -300, -150),
                    (0, -200, -400, -200),
                    (0, -200, -600, -200),
                    (0, -200, -800, -200),
                    (0, -200, -1000, -200),
                    (0, -300, -500, -300),
                    (0, -300, -700, -300),
                    (0, -300, -900, -300),
                    (0, -400, -600, -400),
                    (0, -400, -800, -400),
                    (0, -400, -1000, -400),
                    (0, 150, -300, 150),
                    (0, 200, -400, 200),
                    (0, 200, -600, 200),
                    (0, 200, -800, 200),
                    (0, 200, -1000, 200),
                    (0, 300, -500, 300),
                    (0, 300, -700, 300),
                    (0, 300, -900, 300),
                    (0, 400, -600, 400),
                    (0, 400, -800, 400),
                    (0, 400, -1000, 400),
                    (0, -200, 400, -200),
                    (0, -200, 600, -200),
                    (0, 200, 400, 200),
                    (0, 200, 600, 200),
                    (-200, 0, -400, -200),
                    (-200, 0, -400, 200),
                    (-300, 0, -500, -250),
                    (-300, 0, -500, 250),
                    (-400, 0, -600, -300),
                    (-400, 0, -600, 300),
                    (-500, 0, -700, -350),
                    (-500, 0, -700, 350),
                    (300, 0, 300, -250),
                    (300, 0, 300, 250),
                ]

                for elbow_dx, elbow_dy, label_dx, label_dy in elbow_routes:
                    elbow_x = x_canvas + elbow_dx
                    elbow_y = y_canvas + elbow_dy
                    label_x = x_canvas + label_dx
                    label_y = y_canvas + label_dy

                    if not (
                        label_x - padding_box >= 50
                        and label_x + label_width + padding_box <= map_area_width - 50
                        and label_y - padding_box >= 50
                        and label_y + label_height + padding_box <= target_height - 50
                    ):
                        continue

                    if not (
                        elbow_x >= 50
                        and elbow_x <= map_area_width - 50
                        and elbow_y >= 50
                        and elbow_y <= target_height - 50
                    ):
                        continue

                    label_rect = (
                        label_x - padding_box,
                        label_y - padding_box,
                        label_x + label_width + padding_box,
                        label_y + label_height + padding_box,
                    )

                    collision = False
                    for occupied in occupied_rects:
                        if rectangles_overlap(label_rect, occupied, margin=15):
                            collision = True
                            break

                    if not collision:
                        label_data.append(
                            (
                                person_id,
                                x_canvas,
                                y_canvas,
                                label_x,
                                label_y,
                                method,
                                name,
                                room,
                                (elbow_x, elbow_y),
                            )
                        )
                        name_box_rect = (
                            label_x - padding_box,
                            label_y - padding_box,
                            label_x + name_width + padding_box,
                            label_y + name_height + padding_box,
                        )
                        room_y_pos = label_y + name_height + padding_box + 10
                        room_box_rect = (
                            label_x - padding_box,
                            room_y_pos - padding_box,
                            label_x + room_width + padding_box,
                            room_y_pos + room_height + padding_box,
                        )
                        occupied_rects.append(name_box_rect)
                        occupied_rects.append(room_box_rect)
                        placed = True
                        score += 5  # Higher penalty for elbow
                        if verbose:
                            print(f"  Placed {name} with elbow line (route to left)")
                        break

            # Extreme fallbacks
            if not placed:
                # Try straight lines with collision check
                for dist in [200, 300, 400, 500, 600, 700, 800]:
                    for angle_deg in [180, 225, 135, 270, 90, 315, 45, 0]:
                        angle_rad = math.radians(angle_deg)
                        label_x = x_canvas + dist * math.cos(angle_rad)
                        label_y = y_canvas + dist * math.sin(angle_rad)

                        if not (
                            label_x - padding_box >= 50
                            and label_x + label_width + padding_box <= map_area_width - 50
                            and label_y - padding_box >= 50
                            and label_y + label_height + padding_box <= target_height - 50
                        ):
                            continue

                        label_rect = (
                            label_x - padding_box,
                            label_y - padding_box,
                            label_x + label_width + padding_box,
                            label_y + label_height + padding_box,
                        )
                        collision = False
                        for occupied in occupied_rects:
                            if rectangles_overlap(label_rect, occupied, margin=10):
                                collision = True
                                break

                        if not collision:
                            label_data.append(
                                (
                                    person_id,
                                    x_canvas,
                                    y_canvas,
                                    label_x,
                                    label_y,
                                    method,
                                    name,
                                    room,
                                    None,
                                )
                            )
                            occupied_rects.append(label_rect)
                            placed = True
                            score += 10
                            if verbose:
                                print(f"    Placed at angle {angle_deg}° distance {dist}")
                            break
                    if placed:
                        break

            # Extreme elbow routes
            if not placed:
                extreme_routes = [
                    (0, -300, -1200, -500),
                    (0, -400, -1000, -600),
                    (0, -500, -800, -700),
                    (0, 300, -1200, 500),
                    (0, 400, -1000, 600),
                    (0, 500, -800, 700),
                    (-200, 0, -1000, -100),
                    (-200, 0, -1000, 100),
                    (-300, 0, -1200, -150),
                    (-300, 0, -1200, 150),
                ]
                for elbow_dx, elbow_dy, label_dx, label_dy in extreme_routes:
                    elbow_x = x_canvas + elbow_dx
                    elbow_y = y_canvas + elbow_dy
                    label_x = x_canvas + label_dx
                    label_y = y_canvas + label_dy

                    if not (
                        label_x - padding_box >= 50
                        and label_x + label_width + padding_box <= map_area_width - 50
                        and label_y - padding_box >= 50
                        and label_y + label_height + padding_box <= target_height - 50
                    ):
                        continue

                    if not (
                        elbow_x >= 50
                        and elbow_x <= map_area_width - 50
                        and elbow_y >= 50
                        and elbow_y <= target_height - 50
                    ):
                        continue

                    label_rect = (
                        label_x - padding_box,
                        label_y - padding_box,
                        label_x + label_width + padding_box,
                        label_y + label_height + padding_box,
                    )
                    collision = False
                    for occupied in occupied_rects:
                        if rectangles_overlap(label_rect, occupied, margin=5):
                            collision = True
                            break

                    if not collision:
                        label_data.append(
                            (
                                person_id,
                                x_canvas,
                                y_canvas,
                                label_x,
                                label_y,
                                method,
                                name,
                                room,
                                (elbow_x, elbow_y),
                            )
                        )
                        occupied_rects.append(label_rect)
                        placed = True
                        score += 20
                        if verbose:
                            print("    Placed with extreme elbow route to corner")
                        break

            # Grid scan fallback
            if not placed:
                for scan_y in range(100, target_height - 200, 80):
                    for scan_x in range(100, map_area_width // 3, 80):
                        label_rect = (
                            scan_x - padding_box,
                            scan_y - padding_box,
                            scan_x + label_width + padding_box,
                            scan_y + label_height + padding_box,
                        )
                        collision = False
                        for occupied in occupied_rects:
                            if rectangles_overlap(label_rect, occupied, margin=5):
                                collision = True
                                break
                        if not collision:
                            if scan_y < y_canvas:
                                elbow_y = scan_y + 100
                            else:
                                elbow_y = scan_y - 100
                            elbow_x = x_canvas
                            label_data.append(
                                (
                                    person_id,
                                    x_canvas,
                                    y_canvas,
                                    scan_x,
                                    scan_y,
                                    method,
                                    name,
                                    room,
                                    (elbow_x, elbow_y),
                                )
                            )
                            occupied_rects.append(label_rect)
                            placed = True
                            score += 50
                            if verbose:
                                print(f"    Found free space at ({scan_x}, {scan_y})")
                            break
                    if placed:
                        break

            # Ultimate fallback
            if not placed:
                if verbose:
                    print(f"    WARNING: No free space found for {name}, forcing placement")
                label_x = 100
                label_y = 100 + len(label_data) * 100
                label_y = min(label_y, target_height - 200)
                label_data.append(
                    (
                        person_id,
                        x_canvas,
                        y_canvas,
                        label_x,
                        label_y,
                        method,
                        name,
                        room,
                        (x_canvas, label_y),
                    )
                )
                score += 100  # Heavy penalty

        return label_data, score

    # Try multiple placement configurations

    angle_configs = [
        [315, 45, 270, 225, 0, 135, 90, 180],  # Default (top-right preference)
        [225, 315, 180, 270, 135, 45, 90, 0],  # Bottom-left preference
        [180, 225, 135, 270, 90, 315, 45, 0],  # Left preference
        [270, 225, 315, 180, 0, 135, 45, 90],  # Top preference
        [45, 315, 0, 90, 270, 135, 225, 180],  # Right preference
    ]

    sort_configs = [
        ("density_desc", lambda x: (-x[0], x[1], x[2])),  # High density first
        ("density_asc", lambda x: (x[0], x[1], x[2])),  # Low density first
        ("left_to_right", lambda x: (x[1], x[2])),  # Left to right
        ("right_to_left", lambda x: (-x[1], x[2])),  # Right to left
        ("top_to_bottom", lambda x: (x[2], x[1])),  # Top to bottom
    ]

    best_label_data = None
    best_score = float("inf")
    best_config = None

    num_attempts = min(len(angle_configs) * len(sort_configs), 15)  # Cap attempts
    print(f"Trying {num_attempts} placement configurations...")

    attempt = 0
    for angle_prefs in angle_configs:
        for sort_name, sort_key in sort_configs:
            if attempt >= num_attempts:
                break
            attempt += 1

            sorted_employees = sorted(employees_with_info, key=sort_key)
            label_data, score = try_placement(sorted_employees, angle_prefs, verbose=False)

            if score < best_score:
                best_score = score
                best_label_data = label_data
                best_config = (sort_name, angle_prefs[0])

        if attempt >= num_attempts:
            break

    print(f"Best configuration: {best_config} with score {best_score}")

    # Run final placement with verbose output
    if best_config:
        sort_name = best_config[0]
        for name, key in sort_configs:
            if name == sort_name:
                sorted_employees = sorted(employees_with_info, key=key)
                break
        angle_prefs = None
        for ap in angle_configs:
            if ap[0] == best_config[1]:
                angle_prefs = ap
                break
        if angle_prefs:
            label_data, _ = try_placement(sorted_employees, angle_prefs, verbose=True)
        else:
            label_data = best_label_data
    else:
        label_data = best_label_data

    print(f"Calculated {len(label_data)} label positions")

    # Draw lines (supporting both straight and elbow/bent lines)
    line_color = (0, 47, 95, 200)
    line_width = 6
    for entry in label_data:
        _person_id, x, y, label_x, label_y, _method, _name, _room, elbow = entry
        if elbow is not None:
            # Draw bent line: employee -> elbow -> label
            elbow_x, elbow_y = elbow
            # First segment: from edge of profile picture to elbow
            dx1 = elbow_x - x
            dy1 = elbow_y - y
            dist1 = math.sqrt(dx1 * dx1 + dy1 * dy1)
            if dist1 > 0:
                edge_x = x + (dx1 / dist1) * 48
                edge_y = y + (dy1 / dist1) * 48
                draw.line([(edge_x, edge_y), (elbow_x, elbow_y)], fill=line_color, width=line_width)
            # Second segment: from elbow to label
            draw.line([(elbow_x, elbow_y), (label_x, label_y)], fill=line_color, width=line_width)
        else:
            # Straight line
            dx = label_x - x
            dy = label_y - y
            distance_actual = math.sqrt(dx * dx + dy * dy)
            if distance_actual > 0:
                edge_x = x + (dx / distance_actual) * 48
                edge_y = y + (dy / distance_actual) * 48
                draw.line([(edge_x, edge_y), (label_x, label_y)], fill=line_color, width=line_width)

    # Draw profile pictures
    profile_positions = []  # Store positions for overlay rendering
    for entry in label_data:
        person_id, x, y, _label_x, _label_y, _method, _name, _room, _elbow = entry
        pic_path = os.path.join(script_dir, "profile_pictures", f"{person_id}.jpg")
        if os.path.exists(pic_path):
            try:
                profile_pic = Image.open(pic_path).convert("RGBA")
                profile_pic = profile_pic.resize((90, 90), Image.Resampling.LANCZOS)

                mask = Image.new("L", (90, 90), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, 90, 90), fill=255)

                border_size = 96
                border_img = Image.new("RGBA", (border_size, border_size), (0, 0, 0, 0))
                border_draw = ImageDraw.Draw(border_img)
                border_color = (0, 47, 95, 255)
                border_draw.ellipse((0, 0, border_size - 1, border_size - 1), fill=border_color)

                border_img.paste(profile_pic, (3, 3), mask)

                paste_x = int(x - border_size // 2)
                paste_y = int(y - border_size // 2)
                canvas.paste(border_img, (paste_x, paste_y), border_img)

                # Store position for overlay rendering
                profile_positions.append((pic_path, int(x), int(y), border_size))
            except OSError as e:
                print(f"Error loading profile for {person_id}: {e}")

    # Draw labels
    for entry in label_data:
        _person_id, _x, _y, label_x, label_y, _method, name, room, _elbow = entry
        name_bbox = draw.textbbox((0, 0), name, font=font_name)
        name_width = name_bbox[2] - name_bbox[0]
        name_height = name_bbox[3] - name_bbox[1]

        padding_box = 15
        name_box = [
            label_x - padding_box,
            label_y - padding_box,
            label_x + name_width + padding_box,
            label_y + name_height + padding_box,
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
            room_y + room_height + padding_box,
        ]
        draw.rounded_rectangle(room_box, radius=8, fill=(255, 107, 53, 240))
        draw.text((label_x, room_y), room, fill=(255, 255, 255, 255), font=font_room)

    # Draw event overlays (e.g., Santa hats) on top of everything
    for pic_path, center_x, center_y, pic_size in profile_positions:
        overlay = event_utils.get_tv_overlay_params(
            pic_path, (center_x, center_y), (pic_size, pic_size)
        )
        if overlay:
            canvas.paste(overlay["image"], (overlay["x"], overlay["y"]), overlay["image"])

    # Apply blue-light filter if it's night time in Stockholm (or forced)
    canvas = bluelight_filter.maybe_apply_bluelight_filter(
        canvas, intensity=0.6, force=bluelight_filter_force
    )

    # Save
    canvas.save(output_file, "PNG")
    print(f"✅ 16:9 TV map with QR code saved: {output_file}")
    print(f"   Dimensions: {target_width}x{target_height} (16:9)")

    print("\nStats:")
    print(f"  Total employees: {len(employees)}")
    print(f"  Placed on map: {stats['placed']}")


if __name__ == "__main__":
    # Parse arguments
    parser = argparse.ArgumentParser(description="Create 16:9 TV map with QR code")
    parser.add_argument("employee_json", help="Path to employee JSON file")
    parser.add_argument("output_png", help="Output PNG file path")
    parser.add_argument("--title", default=None, help="Title for the image")
    parser.add_argument(
        "--bluelight",
        choices=["auto", "on", "off"],
        default="auto",
        help="Blue-light filter: auto (based on time), on (always), off (never)",
    )
    args = parser.parse_args()

    bluelight_force = None
    if args.bluelight == "on":
        bluelight_force = True
    elif args.bluelight == "off":
        bluelight_force = False

    main(
        args.employee_json,
        args.output_png,
        title=args.title,
        bluelight_filter_force=bluelight_force,
    )
