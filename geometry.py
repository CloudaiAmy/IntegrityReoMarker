"""Coordinate calculations and scale parsing for PDF markup geometry."""

from typing import Tuple

PT_TO_MM = 25.4 / 72


def rect_center(rect: tuple[float, float, float, float]) -> Tuple[float, float]:
    """Compute the center point of a PDF rectangle (x1, y1, x2, y2)."""
    x1, y1, x2, y2 = rect
    return (x1 + x2) / 2, (y1 + y2) / 2


def mm_to_pdf_points(mm: float) -> float:
    """Convert millimetres on the printed sheet to PDF points."""
    return mm / PT_TO_MM


def real_world_mm_to_pdf_points(length_mm: float, scale: int) -> float:
    """
    Convert a real-world length (mm) to PDF points at the drawing scale.

    At 1:100, a 2700 mm bar is 27 mm on paper.
    """
    paper_mm = length_mm / scale
    return mm_to_pdf_points(paper_mm)


def closest_boundary_point_vertical(
    rect: tuple[float, float, float, float],
    cx: float,
    cy: float,
) -> tuple[float, float]:
    """
    Point on a boundary rectangle closest to (cx, cy) in the vertical direction.

    When the column centre x lies inside the rect width, uses the top or bottom
    edge at that x; otherwise falls back to the nearest corner.
    """
    x1, y1, x2, y2 = rect
    candidates: list[tuple[float, float]] = []
    if x1 <= cx <= x2:
        candidates.append((cx, y1))
        candidates.append((cx, y2))
    candidates.extend([(x1, y1), (x2, y1), (x1, y2), (x2, y2)])
    return min(candidates, key=lambda p: abs(p[1] - cy))


def vertical_line_centered(
    center_x: float,
    center_y: float,
    length_pts: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Vertical line centred on (center_x, center_y) with total length length_pts."""
    half = length_pts / 2
    return (center_x, center_y - half), (center_x, center_y + half)


def vertical_line_from_boundary_through_center(
    boundary_rect: tuple[float, float, float, float],
    center_x: float,
    center_y: float,
    length_pts: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """
    Vertical line at center_x starting at the nearest boundary point (vertical),
    passing through the column centre, with total length length_pts.
    """
    _, boundary_y = closest_boundary_point_vertical(boundary_rect, center_x, center_y)
    if center_y >= boundary_y:
        end_y = boundary_y + length_pts
    else:
        end_y = boundary_y - length_pts
    return (center_x, boundary_y), (center_x, end_y)


def horizontal_line_to_left(
    x: float,
    y: float,
    length_pts: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Horizontal line starting at (x, y) with length_pts extending to the left."""
    return (x, y), (x - length_pts, y)


def parse_scale(value: str) -> int:
    """
    Parse a drawing scale into its denominator.

    Accepts '100', '1:100', or '1/100' for a 1:100 scale.
    """
    text = value.strip()
    if not text:
        raise ValueError("Scale is required.")

    if ":" in text:
        parts = text.split(":", 1)
        if len(parts) != 2 or not parts[1].strip().isdigit():
            raise ValueError("Use format like 1:100.")
        return int(parts[1].strip())

    if "/" in text:
        parts = text.split("/", 1)
        if len(parts) != 2 or not parts[1].strip().isdigit():
            raise ValueError("Use format like 1/100.")
        return int(parts[1].strip())

    if text.isdigit():
        return int(text)

    raise ValueError("Scale must be a number (e.g. 100) or ratio (e.g. 1:100).")
