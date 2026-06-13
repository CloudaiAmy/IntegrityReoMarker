"""Annotation parsing and filtering logic."""

from typing import Optional

import fitz

from geometry import rect_center
from models import Markup, MarkupCollection

# PDF annotation types that represent rectangle markups (Square is standard for Bluebeam)
RECT_TYPES = {fitz.PDF_ANNOT_SQUARE}
RECT_TYPE_NAMES = {"square", "rect"}

# Structural subject tags (case-insensitive substring match)
STRUCTURAL_SUBJECTS = ("COLUMN", "BOUNDARY")


def _matches_structural_subject(subject: str) -> bool:
    upper = subject.upper()
    return any(tag in upper for tag in STRUCTURAL_SUBJECTS)


def _iter_annotations(page: fitz.Page):
    """Yield all annotations on a page."""
    annot = page.first_annot
    while annot:
        yield annot
        annot = annot.next


def _is_rectangle(annot: fitz.Annot) -> bool:
    return annot.type[0] in RECT_TYPES or annot.type[1].lower() in RECT_TYPE_NAMES


def _annotation_fields(annot: fitz.Annot) -> tuple[str, str]:
    """
    Return (subject, comment) from a PDF annotation.

    PyMuPDF maps Bluebeam fields as:
      info['subject']  -> /Subj  (Bluebeam Subject, e.g. COLUMN)
      info['content']  -> /Contents (Bluebeam Comment)
      info['title']    -> /T     (Bluebeam Author — not Subject)
    """
    info = annot.info
    subject = (info.get("subject") or "").strip()
    comment = (info.get("content") or "").strip()

    # Fallback for PDFs that stored markup type in /T via set_info(title=...)
    if not subject:
        title = (info.get("title") or "").strip()
        if title and _matches_structural_subject(title):
            subject = title

    return subject, comment


def is_column_markup(markup: Markup) -> bool:
    """True for column rectangle markups (excludes BOUNDARY / slab edge)."""
    return markup.is_column


def column_markups(collection: MarkupCollection) -> list[Markup]:
    return collection.columns()


def extract_markups(doc: fitz.Document, source_path: Optional[str] = None) -> MarkupCollection:
    """
    Extract rectangle markups from all pages into a MarkupCollection.

    Filters for square/rectangle annotations with a structural subject
    (COLUMN or BOUNDARY) or a non-empty comment.
    """
    collection = MarkupCollection(source_path=source_path)

    for page_number, page in enumerate(doc, start=1):
        for annot in _iter_annotations(page):
            if not _is_rectangle(annot):
                continue

            subject, comment = _annotation_fields(annot)

            if not subject and not comment:
                continue

            if subject and not _matches_structural_subject(subject):
                continue

            rect = tuple(annot.rect)
            markup = Markup(
                subject=subject,
                comment=comment,
                rect=rect,
                page=page_number,
            )

            if subject.upper() == "COLUMN":
                cx, cy = rect_center(rect)
                markup.center_x = round(cx, 1)
                markup.center_y = round(cy, 1)

            collection.add(markup)

    return collection
