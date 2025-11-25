#!/usr/bin/env python3
"""
Utility module for fetching employee positions from the DSV Clickmap service.

This module provides functions to:
1. Fetch all placement positions from the Clickmap API
2. Convert Leaflet coordinates to pixel coordinates for the floor plan image
3. Match employees to their positions by name
"""

from dsv_wrapper import ClickmapClient

# Floor plan image dimensions
FLOOR_PLAN_WIDTH = 3056
FLOOR_PLAN_HEIGHT = 3056


def names_match(daisy_name: str, clickmap_name: str) -> bool:
    """Check if names match, handling middle names and variations.

    Clickmap often has shorter names (no middle names) than Daisy.
    E.g., Daisy: "Jozef Zbigniew Swiatycki", Clickmap: "Jozef Swiatycki"

    Args:
        daisy_name: Full name from Daisy (may include middle names)
        clickmap_name: Name from Clickmap (often first + last only)

    Returns:
        True if names match
    """
    # Exact match
    if daisy_name == clickmap_name:
        return True

    # Normalize for comparison
    daisy_lower = daisy_name.lower().strip()
    clickmap_lower = clickmap_name.lower().strip()

    if daisy_lower == clickmap_lower:
        return True

    # Check if clickmap name parts are all in daisy name (in order)
    # This handles "Jozef Swiatycki" matching "Jozef Zbigniew Swiatycki"
    clickmap_parts = clickmap_lower.split()
    daisy_parts = daisy_lower.split()

    if len(clickmap_parts) >= 2 and len(daisy_parts) >= 2:
        # Check first name and last name match
        if clickmap_parts[0] == daisy_parts[0] and clickmap_parts[-1] == daisy_parts[-1]:
            return True

    return False


# Clickmap uses Leaflet with bounds: top_left = LatLng(10, 0), bottom_right = LatLng(0, 10)
# So latitude 10->0 maps to y 0->3056, and longitude 0->10 maps to x 0->3056
LEAFLET_MAX = 10.0


def leaflet_to_pixel(latitude: float, longitude: float) -> tuple[int, int]:
    """Convert Leaflet lat/lng coordinates to pixel coordinates.

    Args:
        latitude: Leaflet latitude (0-10, where 10 is top)
        longitude: Leaflet longitude (0-10, where 10 is right)

    Returns:
        Tuple of (x, y) pixel coordinates for the 3056x3056 floor plan
    """
    x = int(longitude * (FLOOR_PLAN_WIDTH / LEAFLET_MAX))
    y = int((LEAFLET_MAX - latitude) * (FLOOR_PLAN_HEIGHT / LEAFLET_MAX))
    return (x, y)


def fetch_clickmap_positions() -> dict[str, tuple[int, int]]:
    """Fetch all positions from Clickmap and convert to pixel coordinates.

    Returns:
        Dictionary mapping place_name to (x, y) pixel coordinates.
        Place names can be room numbers like "66109" or zone positions like "6:7".
    """
    positions = {}

    with ClickmapClient() as client:
        placements = client.get_placements()

        for placement in placements:
            place_name = placement.place_name.strip()
            if not place_name:
                continue

            x, y = leaflet_to_pixel(placement.latitude, placement.longitude)
            positions[place_name] = (x, y)

    return positions


def fetch_clickmap_positions_by_person() -> dict[str, tuple[int, int, str]]:
    """Fetch positions from Clickmap indexed by person name.

    Returns:
        Dictionary mapping person_name to (x, y, place_name) tuples.
        Only includes occupied positions (positions with a person assigned).
    """
    positions = {}

    with ClickmapClient() as client:
        placements = client.get_placements()

        for placement in placements:
            if not placement.is_occupied:
                continue

            person_name = placement.person_name.strip()
            place_name = placement.place_name.strip()

            x, y = leaflet_to_pixel(placement.latitude, placement.longitude)
            positions[person_name] = (x, y, place_name)

    return positions


def get_position_for_employee(
    employee_name: str,
    employee_room: str | None,
    clickmap_positions: dict[str, tuple[int, int]],
    clickmap_by_person: dict[str, tuple[int, int, str]] | None = None,
) -> tuple[int, int, str] | None:
    """Get the position for an employee using clickmap data.

    First tries to match by room/place name, then falls back to person name matching.

    Args:
        employee_name: The employee's name
        employee_room: The employee's room number (can be "66109" or "6:7" format)
        clickmap_positions: Dictionary from fetch_clickmap_positions()
        clickmap_by_person: Optional dictionary from fetch_clickmap_positions_by_person()

    Returns:
        Tuple of (x, y, method) where method is "clickmap", or None if not found.
    """
    # First try matching by room/place name
    if employee_room and employee_room in clickmap_positions:
        x, y = clickmap_positions[employee_room]
        return (x, y, "clickmap")

    # Try with stripped room name (some clickmap entries have trailing spaces)
    if employee_room:
        room_stripped = employee_room.strip()
        for place_name, (x, y) in clickmap_positions.items():
            if place_name.strip() == room_stripped:
                return (x, y, "clickmap")

    # Fall back to person name matching if provided
    if clickmap_by_person and employee_name:
        # Try exact match
        if employee_name in clickmap_by_person:
            x, y, _place = clickmap_by_person[employee_name]
            return (x, y, "clickmap")

        # Try case-insensitive match
        employee_name_lower = employee_name.lower()
        for person_name, (x, y, _place) in clickmap_by_person.items():
            if person_name.lower() == employee_name_lower:
                return (x, y, "clickmap")

    return None


if __name__ == "__main__":
    # Test the module
    print("Fetching clickmap positions...")
    positions = fetch_clickmap_positions()
    print(f"Found {len(positions)} positions")

    # Show some examples
    print("\nSample positions:")
    for place_name, (x, y) in list(positions.items())[:10]:
        print(f"  {place_name}: ({x}, {y})")

    print("\nFetching positions by person...")
    by_person = fetch_clickmap_positions_by_person()
    print(f"Found {len(by_person)} occupied positions")

    print("\nSample occupied positions:")
    for person_name, (x, y, place) in list(by_person.items())[:10]:
        print(f"  {person_name} @ {place}: ({x}, {y})")
