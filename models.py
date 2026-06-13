"""Data structures for extracted PDF markups and reinforcement data."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Markup:
    """A single rectangle markup extracted from a PDF annotation."""

    subject: str
    comment: str
    rect: tuple[float, float, float, float]
    page: int = 1
    center_x: Optional[float] = None
    center_y: Optional[float] = None

    @property
    def is_column(self) -> bool:
        return "COLUMN" in self.subject.upper()

    @property
    def is_boundary(self) -> bool:
        return "BOUNDARY" in self.subject.upper()

    @property
    def label(self) -> str:
        """Display label — comment if set, otherwise subject (e.g. Boundary)."""
        return self.comment or self.subject

    def format_summary_line(self) -> str:
        """Format like the UI summary: C2 → (239.1, 152.0) or Boundary → rect (...)."""
        if self.center_x is not None and self.center_y is not None:
            return f"{self.label} → ({self.center_x}, {self.center_y})"
        x1, y1, x2, y2 = self.rect
        return f"{self.label} → rect ({x1:.1f}, {y1:.1f}, {x2:.1f}, {y2:.1f})"

    def to_dict(self) -> dict:
        data = {
            "subject": self.subject,
            "comment": self.comment,
            "rect": list(self.rect),
            "page": self.page,
        }
        if self.center_x is not None:
            data["center_x"] = self.center_x
        if self.center_y is not None:
            data["center_y"] = self.center_y
        return data


@dataclass
class MarkupCollection:
    """
    In-memory store of PDF markups from annotation extraction.

    Holds column centre points and boundary rectangles for later markup tasks.
    """

    markups: list[Markup] = field(default_factory=list)
    source_path: Optional[str] = None

    def add(self, markup: Markup) -> None:
        self.markups.append(markup)

    def columns(self) -> list[Markup]:
        return [m for m in self.markups if m.is_column]

    def boundaries(self) -> list[Markup]:
        return [m for m in self.markups if m.is_boundary]

    def format_lines(self) -> list[str]:
        return [m.format_summary_line() for m in self.markups]

    def lookup_comment(self, comment: str) -> Optional[Markup]:
        """Find a column markup by comment (case-insensitive)."""
        key = comment.strip()
        for markup in self.columns():
            if markup.comment.strip() == key:
                return markup
        key_upper = key.upper()
        for markup in self.columns():
            if markup.comment.strip().upper() == key_upper:
                return markup
        return None

    def column_comments(self) -> list[str]:
        """Unique column comment labels in extraction order."""
        seen: set[str] = set()
        comments: list[str] = []
        for markup in self.columns():
            comment = markup.comment.strip()
            if not comment:
                continue
            key = comment.upper()
            if key in seen:
                continue
            seen.add(key)
            comments.append(comment)
        return comments

    def duplicate_column_comments(self) -> list[str]:
        """Column comments that appear on more than one markup."""
        counts: dict[str, int] = {}
        display: dict[str, str] = {}
        for markup in self.columns():
            comment = markup.comment.strip()
            if not comment:
                continue
            key = comment.upper()
            counts[key] = counts.get(key, 0) + 1
            display.setdefault(key, comment)
        return [display[key] for key, count in counts.items() if count > 1]

    def to_dict(self) -> list[dict]:
        return [m.to_dict() for m in self.markups]


@dataclass
class PageSize:
    """Physical page dimensions detected from the PDF."""

    width_pt: float
    height_pt: float
    width_mm: float
    height_mm: float
    name: str

    @property
    def label(self) -> str:
        return f"{self.name} ({self.width_mm:.1f} × {self.height_mm:.1f} mm)"


@dataclass
class ColumnReinforcement:
    """Normalized reinforcement design data for one column (one spreadsheet row)."""

    reference: str
    dimension_x: Optional[int | float] = None
    dimension_y: Optional[int | float] = None
    edge_condition: Optional[str] = None
    slab_reaction_n: Optional[int | float] = None
    fc_slab: Optional[int | float] = None
    fsy: Optional[int | float] = None
    bar_diameter: Optional[int | float] = None
    as_required: Optional[int | float] = None
    as_total: Optional[int | float] = None
    as_min: Optional[int | float] = None
    bars_required_x: Optional[int] = None
    bars_required_y: Optional[int] = None
    bar_length_x: Optional[int] = None
    bar_length_y: Optional[int] = None

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "ColumnReinforcement":
        """Build from a normalized extract_row dictionary."""
        data = dict(record)
        reference = str(data.pop("mark")).strip()
        return cls(reference=reference, **data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference": self.reference,
            **self.fields(),
        }

    def fields(self) -> dict[str, Any]:
        """Design fields only (excludes reference), for matched output."""
        return {
            "dimension_x": self.dimension_x,
            "dimension_y": self.dimension_y,
            "edge_condition": self.edge_condition,
            "slab_reaction_n": self.slab_reaction_n,
            "fc_slab": self.fc_slab,
            "fsy": self.fsy,
            "bar_diameter": self.bar_diameter,
            "as_required": self.as_required,
            "as_total": self.as_total,
            "as_min": self.as_min,
            "bars_required_x": self.bars_required_x,
            "bars_required_y": self.bars_required_y,
            "bar_length_x": self.bar_length_x,
            "bar_length_y": self.bar_length_y,
        }


@dataclass
class ReinforcementRegistry:
    """
    In-memory store of column reinforcement data loaded from a spreadsheet.

    Keyed by Reference for lookup during markup tasks.
    """

    columns: dict[str, ColumnReinforcement] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    duplicate_references: list[str] = field(default_factory=list)
    source_path: Optional[str] = None

    def lookup(self, reference: str) -> Optional[ColumnReinforcement]:
        """Find a column by Reference (case-insensitive)."""
        key = reference.strip()
        if key in self.columns:
            return self.columns[key]

        key_upper = key.upper()
        for ref, column in self.columns.items():
            if ref.strip().upper() == key_upper:
                return column
        return None

    def references(self) -> list[str]:
        return list(self.columns.keys())

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Serialize all columns keyed by Reference."""
        return {ref: col.to_dict() for ref, col in self.columns.items()}

    def subset(self, references: list[str]) -> dict[str, ColumnReinforcement]:
        """Return columns for the given references (preserves canonical keys)."""
        matched: dict[str, ColumnReinforcement] = {}
        for reference in references:
            column = self.lookup(reference)
            if column is not None:
                canonical = reference
                for ref in self.columns:
                    if ref.strip().upper() == reference.strip().upper():
                        canonical = ref
                        break
                matched[canonical] = column
        return matched
