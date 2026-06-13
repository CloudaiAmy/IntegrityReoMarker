"""PDF loading, page iteration, and page-size detection."""

import fitz

from geometry import PT_TO_MM
from models import PageSize

# Common page sizes in PDF points (portrait), tolerance ±2 pt
_STANDARD_SIZES: dict[str, tuple[float, float]] = {
    "A4": (595, 842),
    "A3": (842, 1191),
    "A2": (1191, 1684),
    "A1": (1684, 2384),
    "A0": (2384, 3370),
    "Letter": (612, 792),
    "Legal": (612, 1008),
    "Tabloid": (792, 1224),
}


def open_pdf(path: str) -> fitz.Document:
    """Open a PDF file and return the document object."""
    return fitz.open(path)


def iter_pages(doc: fitz.Document):
    """Yield (page_number, page) for each page in the document (1-based page numbers)."""
    for i in range(doc.page_count):
        yield i + 1, doc[i]


def _match_standard_name(width_pt: float, height_pt: float) -> str:
    short, long = sorted((width_pt, height_pt))
    for name, (w, h) in _STANDARD_SIZES.items():
        if abs(short - w) <= 2 and abs(long - h) <= 2:
            return name
    return "Custom"


def detect_page_size(doc: fitz.Document) -> PageSize:
    """Detect page size from the first page of the document."""
    rect = doc[0].rect
    width_pt = rect.width
    height_pt = rect.height
    return PageSize(
        width_pt=width_pt,
        height_pt=height_pt,
        width_mm=width_pt * PT_TO_MM,
        height_mm=height_pt * PT_TO_MM,
        name=_match_standard_name(width_pt, height_pt),
    )
