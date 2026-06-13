"""Entry point for PDF annotation extraction."""

import argparse
import sys

from annotation_extractor import extract_markups
from excel_extractor import build_registry
from geometry import parse_scale
from pdf_reader import detect_page_size, open_pdf
from summary import build_summary, get_validation_warning_message
from ui import run_ui


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract Bluebeam-style rectangle markups from a PDF."
    )
    parser.add_argument(
        "pdf",
        nargs="?",
        help="Path to the input PDF file (omit to launch the UI)",
    )
    parser.add_argument(
        "--excel",
        help="Path to reinforcement spreadsheet (.xlsx)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON instead of console format",
    )
    parser.add_argument(
        "--scale",
        default="100",
        help="Drawing scale denominator (default: 100, e.g. 1:100)",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Launch the graphical interface",
    )
    args = parser.parse_args()

    # No arguments → launch UI (same as double-clicking the .exe)
    if args.ui or not args.pdf:
        run_ui()
        return

    try:
        scale = parse_scale(args.scale)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    registry = None
    if args.excel:
        try:
            registry = build_registry(args.excel)
        except Exception as e:
            print(f"Error reading spreadsheet: {e}", file=sys.stderr)
            sys.exit(1)

    try:
        doc = open_pdf(args.pdf)
    except Exception as e:
        print(f"Error opening PDF: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        page_size = detect_page_size(doc)
        markups = extract_markups(doc, source_path=args.pdf)
        print(
            build_summary(
                markups,
                page_size=page_size,
                scale=scale,
                registry=registry,
                as_json=args.json,
            )
        )
        if registry is not None:
            validation = get_validation_warning_message(markups, registry)
            if validation:
                print(f"Validation Warning: {validation}", file=sys.stderr)
    finally:
        doc.close()


if __name__ == "__main__":
    main()
