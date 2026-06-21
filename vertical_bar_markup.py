"""Add vertical bar markups to a copy of the input PDF."""

from pathlib import Path

import fitz

from geometry import (
    closest_boundary_point_vertical,
    horizontal_line_to_left,
    mm_to_pdf_points,
    real_world_mm_to_pdf_points,
    vertical_line_centered,
    vertical_line_from_boundary_through_center,
)
from models import Markup, MarkupCollection, ReinforcementRegistry

GREEN = (0, 0.75, 0)
RED = (1, 0, 0)
LINE_WIDTH = 1.5
DIMENSION_ARROW_LINE_WIDTH = 0.75
EDGE_BOUNDARY_HORIZONTAL_MM = 600
COLUMN_CENTER_DOT_DIAMETER_MM = 2.2
DIMENSION_ARROW_CHEVRON_MM = COLUMN_CENTER_DOT_DIAMETER_MM


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
    width: float = LINE_WIDTH,
) -> None:
    annot = page.add_line_annot(fitz.Point(*start), fitz.Point(*end))
    annot.set_colors(stroke=GREEN)
    annot.set_border(width=width)
    annot.update()


def _add_red_dot_at_center(
    page: fitz.Page,
    center_x: float,
    center_y: float,
) -> None:
    """Filled red circle at the column centre (2.2 mm diameter on the printed sheet)."""
    diameter_pts = mm_to_pdf_points(COLUMN_CENTER_DOT_DIAMETER_MM)
    radius = diameter_pts / 2
    rect = fitz.Rect(
        center_x - radius,
        center_y - radius,
        center_x + radius,
        center_y + radius,
    )
    annot = page.add_circle_annot(rect)
    annot.set_colors(stroke=RED, fill=RED)
    annot.set_border(width=0)
    annot.update()


def _add_simple_horizontal_arrow(
    page: fitz.Page,
    center_x: float,
    center_y: float,
    length_pts: float,
    pointing_left: bool,
) -> None:
    """Thin shaft with a small open chevron at the tip (<- or ->)."""
    chevron = mm_to_pdf_points(DIMENSION_ARROW_CHEVRON_MM)
    wing_x = chevron * 0.45
    wing_y = chevron * 0.3

    if pointing_left:
        tip_x = center_x - length_pts
        _add_green_line(page, (center_x, center_y), (tip_x, center_y), DIMENSION_ARROW_LINE_WIDTH)
        _add_green_line(
            page, (tip_x + wing_x, center_y - wing_y), (tip_x, center_y), DIMENSION_ARROW_LINE_WIDTH
        )
        _add_green_line(
            page, (tip_x + wing_x, center_y + wing_y), (tip_x, center_y), DIMENSION_ARROW_LINE_WIDTH
        )
    else:
        tip_x = center_x + length_pts
        _add_green_line(page, (center_x, center_y), (tip_x, center_y), DIMENSION_ARROW_LINE_WIDTH)
        _add_green_line(
            page, (tip_x - wing_x, center_y - wing_y), (tip_x, center_y), DIMENSION_ARROW_LINE_WIDTH
        )
        _add_green_line(
            page, (tip_x - wing_x, center_y + wing_y), (tip_x, center_y), DIMENSION_ARROW_LINE_WIDTH
        )


def _add_dimension_x_arrows(
    page: fitz.Page,
    center_x: float,
    center_y: float,
    dimension_x: float | int | None,
    scale: int,
    comment: str,
    warnings: list[str],
) -> None:
    """Left and right horizontal arrows from the column centre, each half of dimension_x."""
    if dimension_x is None:
        warnings.append(f"'{comment}': dimension_x missing — skipped dimension arrows.")
        return

    half_pts = real_world_mm_to_pdf_points(float(dimension_x) / 2, scale)
    if half_pts <= 0:
        warnings.append(f"'{comment}': invalid dimension_x — skipped dimension arrows.")
        return

    _add_simple_horizontal_arrow(page, center_x, center_y, half_pts, pointing_left=True)
    _add_simple_horizontal_arrow(page, center_x, center_y, half_pts, pointing_left=False)


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
    All vertical bars also get left/right dimension arrows (each half of dimension_x),
    then a 2.2 mm red dot at the column centre drawn on top.

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
                _add_dimension_x_arrows(
                    page,
                    markup.center_x,
                    markup.center_y,
                    reinforcement.dimension_x,
                    scale,
                    comment,
                    warnings,
                )
                _add_red_dot_at_center(page, markup.center_x, markup.center_y)
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
                _add_dimension_x_arrows(
                    page,
                    markup.center_x,
                    markup.center_y,
                    reinforcement.dimension_x,
                    scale,
                    comment,
                    warnings,
                )
                _add_red_dot_at_center(page, markup.center_x, markup.center_y)

        doc.save(output_path, garbage=4, deflate=True)
    finally:
        doc.close()

    return interior_added, edge_corner_added, warnings
