"""Add vertical bar markups to a copy of the input PDF."""

from pathlib import Path

import fitz

from geometry import (
    closest_boundary_point_vertical,
    horizontal_line_to_left,
    real_world_mm_to_pdf_points,
    vertical_line_centered,
    vertical_line_from_boundary_through_center,
)
from models import Markup, MarkupCollection, ReinforcementRegistry

GREEN = (0, 0.75, 0)
LINE_WIDTH = 1.5
EDGE_BOUNDARY_HORIZONTAL_MM = 600


def default_vertical_bars_output_path(input_path: str) -> str:
    """Default output path beside the input PDF."""
    path = Path(input_path)
    return str(path.parent / f"{path.stem}_vertical_bars.pdf")


def _normalize_edge(edge_condition: str | None) -> str:
    return (edge_condition or "").strip().lower()


def _is_interior(edge_condition: str | None) -> bool:
    return _normalize_edge(edge_condition) == "interior"

def _is_edge_along_y(edge_condition: str | None) -> bool:
    return _normalize_edge(edge_condition) == "edge along y"

def _is_edge_along_x(edge_condition: str | None) -> bool:
    return _normalize_edge(edge_condition) == "edge along x"


def _is_corner(edge_condition: str | None) -> bool:
    return _normalize_edge(edge_condition) == "corner"


def _nearest_boundary(
    collection: MarkupCollection,
    column: Markup,
) -> Markup | None:
    """Boundary on the same page whose closest vertical point is nearest to the column."""
    if column.center_x is None or column.center_y is None:
        return None

    best: Markup | None = None
    best_distance = float("inf")
    cx, cy = column.center_x, column.center_y

    for boundary in collection.boundaries():
        if boundary.page != column.page:
            continue
        _, boundary_y = closest_boundary_point_vertical(boundary.rect, cx, cy)
        distance = abs(boundary_y - cy)
        if distance < best_distance:
            best_distance = distance
            best = boundary

    return best


def _add_green_line(
    page: fitz.Page,
    start: tuple[float, float],
    end: tuple[float, float],
) -> None:
    annot = page.add_line_annot(fitz.Point(*start), fitz.Point(*end))
    annot.set_colors(stroke=GREEN)
    annot.set_border(width=LINE_WIDTH)
    annot.update()


def apply_vertical_bars(
    input_path: str,
    output_path: str,
    collection: MarkupCollection,
    registry: ReinforcementRegistry,
    scale: int,
) -> tuple[int, int, list[str]]:
    """
    Copy the input PDF and add green vertical lines for supported edge conditions.

    Interior: line centred on the column with length bar_length_y.
    Edge Along X / Corner: vertical line from nearest boundary through the column centre,
    plus a 600 mm horizontal line at the boundary intersection extending left.

    Returns (interior_added, edge_corner_added, warnings).
    """
    warnings: list[str] = []
    interior_added = 0
    edge_corner_added = 0

    doc = fitz.open(input_path)
    try:
        for markup in collection.columns():
            comment = markup.comment.strip()
            if not comment:
                warnings.append("Skipped column markup with empty comment.")
                continue

            if markup.center_x is None or markup.center_y is None:
                warnings.append(f"Skipped '{comment}': no centre coordinates.")
                continue

            reinforcement = registry.lookup(comment)
            if reinforcement is None:
                warnings.append(f"Skipped '{comment}': no reinforcement data.")
                continue

            edge = reinforcement.edge_condition
            is_interior = _is_interior(edge)
            is_edge_along_y = _is_edge_along_y(edge)
            is_edge_corner = _is_edge_along_x(edge) or _is_corner(edge)
            if not is_interior and not is_edge_along_y and not is_edge_corner:
                continue

            if reinforcement.bar_length_y is None:
                warnings.append(f"Skipped '{comment}': bar_length_y is missing.")
                continue

            length_pts = real_world_mm_to_pdf_points(reinforcement.bar_length_y, scale)
            if length_pts <= 0:
                warnings.append(f"Skipped '{comment}': invalid bar_length_y.")
                continue

            page_index = max(markup.page - 1, 0)
            if page_index >= doc.page_count:
                warnings.append(f"Skipped '{comment}': page {markup.page} not in PDF.")
                continue

            if is_edge_corner:
                boundary = _nearest_boundary(collection, markup)
                if boundary is None:
                    warnings.append(
                        f"Skipped '{comment}': no BOUNDARY markup on page {markup.page}."
                    )
                    continue
                start, end = vertical_line_from_boundary_through_center(
                    boundary.rect,
                    markup.center_x,
                    markup.center_y,
                    length_pts,
                )
                page = doc[page_index]
                _add_green_line(page, start, end)
                horiz_pts = real_world_mm_to_pdf_points(EDGE_BOUNDARY_HORIZONTAL_MM, scale)
                if horiz_pts > 0:
                    h_start, h_end = horizontal_line_to_left(start[0], start[1], horiz_pts)
                    _add_green_line(page, h_start, h_end)
                edge_corner_added += 1
            else:
                start, end = vertical_line_centered(
                    markup.center_x,
                    markup.center_y,
                    length_pts,
                )
                interior_added += 1
                page = doc[page_index]
                _add_green_line(page, start, end)

        doc.save(output_path, garbage=4, deflate=True)
    finally:
        doc.close()

    return interior_added, edge_corner_added, warnings
