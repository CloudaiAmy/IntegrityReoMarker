"""Build extraction summary text for console and UI output."""

import json
from typing import Any, Optional

from models import MarkupCollection, PageSize, ReinforcementRegistry


def format_markup_lines(collection: MarkupCollection) -> list[str]:
    return collection.format_lines()


def find_duplicate_pdf_column_comments(collection: MarkupCollection) -> list[str]:
    return collection.duplicate_column_comments()


def _format_name_list(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def format_validation_warning_message(
    unmatched_pdf: list[str],
    unmatched_spreadsheet: list[str],
    duplicate_pdf_comments: list[str],
    duplicate_excel_references: list[str],
) -> Optional[str]:
    """Summarise mismatches and duplicates for popup / warnings."""
    parts: list[str] = []

    if duplicate_pdf_comments:
        parts.append(
            f"duplicate comments in PDF: {_format_name_list(duplicate_pdf_comments)}"
        )
    if duplicate_excel_references:
        parts.append(
            f"duplicate References in Excel: {_format_name_list(duplicate_excel_references)}."
        )
    if unmatched_pdf:
        parts.append(
            f"{_format_name_list(unmatched_pdf)} exist in PDF, missing from Excel"
        )
    if unmatched_spreadsheet:
        parts.append(
            f"{_format_name_list(unmatched_spreadsheet)} exist in Excel but missing from PDF"
        )

    if not parts:
        return None

    return " and ".join(parts) + ", please double check"


def build_matched_registry(
    collection: MarkupCollection,
    registry: ReinforcementRegistry,
) -> tuple[
    dict[str, dict[str, Any]],
    list[str],
    list[str],
    list[str],
    list[str],
]:
    """
    Match PDF column comments to spreadsheet Reference rows.

    Only COLUMN markups are compared (BOUNDARY / slab edge excluded).

    Returns:
        matched_dict — references with both PDF comment and spreadsheet row
        unmatched_pdf_comments — column comments with no spreadsheet row
        unmatched_spreadsheet_refs — spreadsheet references with no PDF column
        warnings — human-readable messages for all issues
        duplicate_pdf_comments — column comments repeated in the PDF
    """
    matched: dict[str, dict[str, Any]] = {}
    unmatched_pdf: list[str] = []
    unmatched_spreadsheet: list[str] = []
    warnings: list[str] = []
    seen_comments: set[str] = set()
    pdf_comment_keys: set[str] = set()

    duplicate_pdf_comments = find_duplicate_pdf_column_comments(collection)
    for comment in duplicate_pdf_comments:
        warnings.append(f"Duplicate column comment '{comment}' in PDF.")

    for markup in collection.columns():
        comment = (markup.comment or "").strip()
        if not comment:
            continue

        comment_key = comment.upper()
        if comment_key in seen_comments:
            continue
        seen_comments.add(comment_key)
        pdf_comment_keys.add(comment_key)

        column = registry.lookup(comment)
        if column is None:
            unmatched_pdf.append(comment)
            warnings.append(
                f"Column '{comment}' exists in PDF but is missing from Excel."
            )
            continue

        canonical = comment
        for reference in registry.columns:
            if reference.strip().upper() == comment_key:
                canonical = reference
                break
        matched[canonical] = column.fields()

    for reference in registry.columns:
        if reference.strip().upper() not in pdf_comment_keys:
            unmatched_spreadsheet.append(reference)
            warnings.append(
                f"Reference '{reference}' exists in Excel but is missing from PDF."
            )

    return (
        matched,
        unmatched_pdf,
        unmatched_spreadsheet,
        warnings,
        duplicate_pdf_comments,
    )


def get_validation_warning_message(
    collection: MarkupCollection,
    registry: ReinforcementRegistry,
) -> Optional[str]:
    """Return a summary warning for mismatches and duplicates."""
    (
        _,
        unmatched_pdf,
        unmatched_spreadsheet,
        _,
        duplicate_pdf_comments,
    ) = build_matched_registry(collection, registry)
    return format_validation_warning_message(
        unmatched_pdf,
        unmatched_spreadsheet,
        duplicate_pdf_comments,
        registry.duplicate_references,
    )


def _format_drawing_info(page_size: PageSize, scale: int) -> list[str]:
    return [
        f"Page size: {page_size.label}",
        f"Drawing scale: 1:{scale}",
    ]


def build_summary(
    collection: MarkupCollection,
    *,
    page_size: PageSize | None = None,
    scale: int | None = None,
    registry: ReinforcementRegistry | None = None,
    as_json: bool = False,
) -> str:
    """Build the extraction summary, optionally merged with spreadsheet data."""
    matched_registry: dict[str, dict[str, Any]] = {}
    unmatched_pdf: list[str] = []
    unmatched_spreadsheet: list[str] = []
    match_warnings: list[str] = []
    duplicate_pdf_comments: list[str] = []

    if registry is not None:
        (
            matched_registry,
            unmatched_pdf,
            unmatched_spreadsheet,
            match_warnings,
            duplicate_pdf_comments,
        ) = build_matched_registry(collection, registry)

    validation_message = format_validation_warning_message(
        unmatched_pdf,
        unmatched_spreadsheet,
        duplicate_pdf_comments,
        registry.duplicate_references if registry is not None else [],
    )

    if as_json:
        payload: dict[str, Any] = {"markups": collection.to_dict()}
        if page_size is not None and scale is not None:
            payload["page_size"] = {
                "name": page_size.name,
                "width_mm": round(page_size.width_mm, 1),
                "height_mm": round(page_size.height_mm, 1),
            }
            payload["scale"] = f"1:{scale}"
        if registry is not None:
            payload["reinforcement"] = matched_registry
            payload["reinforcement_registry"] = registry.to_dict()
            payload["unmatched_pdf_column_comments"] = unmatched_pdf
            payload["unmatched_spreadsheet_references"] = unmatched_spreadsheet
            payload["duplicate_pdf_column_comments"] = duplicate_pdf_comments
            payload["duplicate_excel_references"] = registry.duplicate_references
            payload["validation_warning_message"] = validation_message
            payload["warnings"] = match_warnings + registry.warnings
        return json.dumps(payload, indent=2)

    sections: list[str] = []

    if page_size is not None and scale is not None:
        sections.append("=== Drawing Info ===")
        sections.extend(_format_drawing_info(page_size, scale))
        sections.append("")

    markup_lines = format_markup_lines(collection)
    sections.append("=== PDF Markups ===")
    sections.append(
        "\n".join(markup_lines) if markup_lines else "No matching markups found."
    )

    if registry is not None:
        sections.append("")
        sections.append("=== Reinforcement Data (matched columns) ===")
        sections.append(json.dumps(matched_registry, indent=2))

        if validation_message:
            sections.append("")
            sections.append("=== Validation Warning ===")
            sections.append(validation_message)

        all_warnings = match_warnings + registry.warnings
        if all_warnings:
            sections.append("")
            sections.append("=== Warnings ===")
            sections.append("\n".join(all_warnings))

    return "\n".join(sections)
