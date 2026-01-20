# DSV Staff Map - Project Documentation for AI Assistants

> **IMPORTANT:** Always keep this file up to date when making changes to the project structure, architecture, or key concepts.

## Project Overview

This project generates interactive HTML maps and 16:9 TV displays showing DSV staff locations on a floor plan. It scrapes employee data from Daisy (DSV's internal system), fetches positions from DSV Clickmap, and generates both interactive web maps and TV-optimized displays with QR codes.

**Key Features:**
- Scrapes employee data and profile pictures from Daisy
- Fetches employee positions from DSV Clickmap service
- Generates interactive HTML maps with search and filtering
- Creates 16:9 TV displays with QR codes for location updates
- Automated daily builds via GitHub Actions
- User-submitted location corrections via GitHub Issues

## Architecture

### Data Flow

1. **Scraping** → `get_all_dsv_employees.py` scrapes employee data from Daisy (including units via dsv-wrapper)
2. **Pictures** → `download_all_dsv_pictures.py` downloads profile pictures
3. **Name Fixing** → `fix_all_dsv_names.py` cleans up employee names
4. **Positions** → `clickmap_positions.py` fetches positions from DSV Clickmap service
5. **Map Generation** → `main.py` generates interactive HTML maps
6. **TV Images** → `create_tv_16x9_with_qr.py` creates TV-optimized displays
7. **Upload** → `upload_and_add_to_show.py` uploads to ACT Lab display system

### Authentication

- All authentication is handled by the `dsv-wrapper` library
- `AsyncDaisyClient` for Daisy access (employee data, profile pictures)
- `ClickmapClient` for DSV Clickmap access (employee positions)
- `ACTLabClient` for ACT Lab display system uploads
- No manual cookie management needed - dsv-wrapper handles sessions internally
- **IMPORTANT:** This project uses Daisy, Clickmap, and ACT Lab systems

### Positioning System

Employees are positioned on the floor plan using:

1. **Location Overrides** - User-submitted corrections via GitHub Issues (stored in `data/location_overrides.json`) - takes precedence
2. **DSV Clickmap** - All positions fetched from the Clickmap service via `ClickmapClient`

The Clickmap service provides positions for all rooms including zone-based positions (like "2:X", "6:7").

**Name Matching:**
- Employees are matched by name between Daisy and Clickmap
- Fuzzy matching handles middle names (e.g., "Jozef Zbigniew Swiatycki" matches "Jozef Swiatycki")
- Matching logic: first name + last name must match

**Coordinate Conversion:**
- Clickmap uses Leaflet coordinates (lat 0-10, lng 0-10)
- Floor plan is 3056×3056 pixels
- Conversion: `x = longitude * 305.6`, `y = (10 - latitude) * 305.6`

## File Organization

```
assets/          - Image assets (floor plan, QR codes, logos)
  ├── events/    - Seasonal event decorations (see Event System below)
  │   └── <event_name>/
  │       ├── config.json  - Event configuration
  │       └── image.png    - Event image
  └── overrides/ - Date-based display override images
      └── *.png  - Override images (referenced by display_overrides.json)
data/            - Configuration and data files
  ├── location_overrides.json  - User-submitted location updates
  └── display_overrides.json   - Date-based display overrides
output/          - Generated files (gitignored)
  ├── html/      - Interactive HTML maps
  └── tv/        - TV display images
profile_pictures/ - Downloaded employee photos (gitignored)
.github/workflows/ - Automation workflows
```

### Key Scripts

- **main.py** - Main orchestrator, runs all steps and generates HTML map
- **clickmap_positions.py** - Utility module for fetching positions from DSV Clickmap
- **get_all_dsv_employees.py** - Scrapes employee data (including units) using dsv-wrapper
- **download_all_dsv_pictures.py** - Downloads profile pictures using dsv-wrapper
- **fix_all_dsv_names.py** - Cleans up employee names
- **create_tv_16x9_with_qr.py** - Generates 16:9 TV images with QR codes
- **upload_and_add_to_show.py** - Uploads to ACT Lab display system using dsv-wrapper (manual use)
- **ci_slide_manager.py** - Manages CI build progress indicator on ACT Lab display (used by GitHub Actions)
- **event_utils.py** - Loads active events and their profile processors dynamically

### Data Files

- **data/location_overrides.json** - User-submitted location and unit overrides (GitHub automation)
- **data/display_overrides.json** - Date-based display overrides (replaces map with custom image)

### Assets

- **assets/floor_plan.png** - Base floor plan image (3056×3056px)
- **assets/qr_fix_location.png** - QR code linking to location update issue template
- **assets/repo_qr.png** - QR code linking to repository
- **assets/SU_logotyp_Landscape_Invert_1000px.png** - Stockholm University logo
- **assets/Orienteringskarta_plan3.pdf** - Original floor plan PDF
- **assets/ci-build-in-progress.png** - CI build progress indicator for ACT Lab display

## Location Override System

**How it works:**

1. User submits GitHub Issue using "Update My Location" template
2. `.github/workflows/location-update.yml` validates submission
3. Workflow updates `data/location_overrides.json` via `jq`
4. Workflow creates Pull Request with changes
5. Once PR is merged, next map generation applies the update

**Override Format:**

```json
{
  "person_id": {"room": "room_number", "unit": "unit_name"}
}
```

Both `room` and `unit` fields are optional - you can override just one or both:
- `{"room": "2:X"}` - Override room only
- `{"unit": "ACT"}` - Override unit only
- `{"room": "61302", "unit": "ACT"}` - Override both

**Important:** Location and unit overrides take precedence over Clickmap positions and dsv-wrapper data.

## Display Override System

Allows replacing the generated map with a custom image on specific dates (e.g., for conferences, events).

**How it works:**

1. CI workflow checks `data/display_overrides.json` for today's date
2. If override exists, skips normal build and uploads the override image instead
3. Override images stored in `assets/overrides/`

**Override Format (`data/display_overrides.json`):**

```json
{
  "2026-01-22": {
    "image": "assets/overrides/act_conference.jpg",
    "name": "ACT Conference"
  }
}
```

**CI Slide Manager Commands:**

- `python ci_slide_manager.py check` - Check if today has an override (exit 0=yes, 1=no)
- `python ci_slide_manager.py override` - Upload today's override image

**Creating Override Images:**

1. Create HTML in `assets/overrides/` (1920x1080 for 16:9 displays)
2. Render to PNG using playwright or similar
3. Add entry to `data/display_overrides.json`

## QR Code System

**IMPORTANT:** QR codes are **pre-generated PNG images**, NOT generated by code.
- The `qrcode` library dependency was removed
- QR codes are loaded from `assets/` directory
- To update QR codes, replace the PNG files directly

## Event System

Seasonal decorations are loaded from `assets/events/<event_name>/`. Each event folder contains:

- **config.json** - Event configuration
- **Image files** - Decoration images (if any)

### Adding a New Event

1. Create folder: `assets/events/<event_name>/`
2. Add image file(s) if needed
3. Create `config.json`:

```json
{
  "start_month": 12,
  "start_day": 1,
  "end_month": 12,
  "end_day": 25,
  "assets": [
    {
      "type": "image",
      "file": "tree.png",
      "scale": 1.7,
      "position": "bottom-left",
      "padding": 30
    },
    {
      "type": "message",
      "texts": ["Merry Christmas!", "God Jul!"],
      "color": [178, 34, 34],
      "font_size": 36,
      "position": "bottom-left",
      "padding": 30,
      "offset_y": -50
    }
  ]
}
```

### Config Options

**Event-level (required):**

| Field | Description |
|-------|-------------|
| `start_month`, `start_day` | Event start date (inclusive) |
| `end_month`, `end_day` | Event end date (inclusive) |
| `assets` | Array of asset objects |

**Shared asset options:**

| Field | Description | Default |
|-------|-------------|---------|
| `type` | `image` or `message` | `image` |
| `position` | `bottom-left`, `bottom-right`, `top-left`, `top-right` | `bottom-left` |
| `padding` | Pixels from edge | `30` |
| `offset_x` | Additional X offset | `0` |
| `offset_y` | Additional Y offset | `0` |

**Image-specific options:**

| Field | Description | Default |
|-------|-------------|---------|
| `file` | Image filename | `image.png` |
| `scale` | Image scale factor | `1.0` |

**Message-specific options:**

| Field | Description | Default |
|-------|-------------|---------|
| `texts` | Array of messages (one chosen randomly) | Required |
| `color` | RGB array | `[0, 0, 0]` |
| `font_size` | Font size in pixels | `36` |
| `align` | Text alignment: `left`, `center`, `right` | `left` |

**Note:** Date ranges can wrap around year boundaries (e.g., Dec 15 - Jan 5).

### Profile Processors

Events can include a custom Python script to process profile pictures. This is used for seasonal effects like Santa hats during Christmas.

**Config options:**

| Field | Description |
|-------|-------------|
| `profile_processor` | Python script filename (e.g., `profile_processor.py`) |
| `profile_processor_config` | Configuration dict passed to the processor |

**Processor interface:** The script must implement a `process(image, config)` function:
- `image`: PIL Image (RGBA)
- `config`: dict from `profile_processor_config`
- Returns: PIL Image (RGBA)

**Example (Christmas Santa hats):**

```json
{
  "profile_processor": "profile_processor.py",
  "profile_processor_config": {
    "enabled": true,
    "file": "santa_hat.png",
    "scale_factor": 1.3,
    "vertical_offset": 0.15
  }
}
```

The Christmas event includes a profile processor that uses OpenCV Haar Cascade for face detection to add Santa hats. See `assets/events/christmas/profile_processor.py` for implementation details.

**Integration:** Profile processors are loaded by `event_utils.py` and called from `main.py` and `create_tv_16x9_with_qr.py` when an active event has a `profile_processor` configured.

### Configured Events

Events are stored in `assets/events/` folders. Browse the folder to see all configured events. Date ranges can wrap around year boundaries (e.g., Dec 26 - Jan 9 for New Year).

## Automation

### Daily Build (2:00 AM UTC)
- `.github/workflows/build-release.yml`
- Shows "Build in Progress" indicator on ACT Lab display during build
- Runs `main.py` to regenerate all maps
- On success: uploads new map, removes progress indicator
- On failure: removes progress indicator, keeps previous map as fallback (CI still fails)
- Requires `SU_USERNAME` and `SU_PASSWORD` secrets

**CI Slide Management Flow:**
1. `ci_slide_manager.py start` - Disables auto-delete on current slide, uploads progress indicator
2. Build runs (`main.py`)
3. On success: `ci_slide_manager.py success` - Uploads new map, removes old slides
4. On failure: `ci_slide_manager.py failure` - Removes progress indicator, old slide remains

### Location Update Requests
- `.github/workflows/location-update.yml`
- Triggered when issue with `location-update` label is created
- Validates person ID and room number
- Creates PR with changes to `data/location_overrides.json`

## Common Tasks

### Adding a New Data File

1. Create JSON file in `data/` directory
2. Update all scripts that need to load it (usually `main.py` and `create_tv_16x9_with_qr.py`)
3. Use `os.path.join(script_dir, "data", "filename.json")` for path
4. Update this CLAUDE.md file

### Adding a New Asset

1. Place file in `assets/` directory
2. Update scripts to reference `assets/filename.ext`
3. Update this CLAUDE.md file

## Important Notes & Gotchas

### Error Handling
- **DO NOT** use `return False` for errors in main execution paths
- **USE** `sys.exit(1)` or raise exceptions for proper error handling
- Example: `upload_and_add_to_show.py` was fixed to use `sys.exit(1)` instead of `return False`

### Path References
- Always use `os.path.join(script_dir, "data", "file.json")` for data files
- Always use `os.path.join(script_dir, "assets", "file.png")` for assets
- Never hardcode paths relative to current directory

### Authentication & dsv-wrapper
- All authentication handled by `dsv-wrapper` library (https://github.com/Edwinexd/dsv-wrapper)
- `AsyncDaisyClient` provides async access to Daisy with automatic authentication
- `ClickmapClient` provides sync access to DSV Clickmap with automatic authentication
- `ACTLabClient` provides sync access to ACT Lab with automatic authentication
- Credentials from environment variables (`SU_USERNAME` and `SU_PASSWORD`)
- No manual session/cookie management needed
- **IMPORTANT:** dsv-wrapper provides all employee data including units and positions - no manual scraping or coordinate handling needed

### Dependencies
- **DO NOT** add `qrcode` library - QR codes are pre-generated images
- Check `requirements.txt` before adding new dependencies
- Remove unused dependencies

### JSON Comment Fields
- Fields starting with `_` are comments/metadata
- Always filter them out when loading: `if not k.startswith("_")`

### Git Workflow (per user's preferences)
- Never commit unless explicitly told to do so
- When committing: short, single-line commit messages (no co-authored-by Claude)
- Keep requirements.txt up to date
- Use Python venv stored under `venv/`

## Testing Changes

After making changes, test by running:

```bash
python3 main.py
```

This will:
1. Scrape employee data (including units via dsv-wrapper)
2. Download profile pictures
3. Fix employee names
4. Fetch positions from DSV Clickmap
5. Generate HTML map
6. Generate TV images for all units

**Output locations:**
- `output/html/staff_map_unified.html` - Interactive map
- `output/tv/*.png` - TV display images

## Need to Update This File?

When you make structural changes to the project:
- ✅ Add/remove/move files → Update "File Organization" section
- ✅ Change data formats → Update relevant sections
- ✅ Add new workflows → Update "Automation" section
- ✅ Add new positioning methods → Update "Positioning System" section
- ✅ Change dependencies → Update "Dependencies" notes
- ✅ Add new gotchas → Update "Important Notes & Gotchas" section

**Keep this file current!** Future AI assistants and developers depend on accurate documentation.
