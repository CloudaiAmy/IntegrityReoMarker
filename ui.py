"""Simple desktop UI for PDF annotation extraction."""

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from annotation_extractor import extract_markups
from excel_extractor import build_registry
from geometry import parse_scale
from pdf_reader import detect_page_size, open_pdf
from models import MarkupCollection, ReinforcementRegistry
from summary import build_summary, get_validation_warning_message
from vertical_bar_markup import (
    apply_vertical_bars,
    default_vertical_bars_output_path,
)


class ExtractorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PDF Annotation Extractor")
        self.geometry("720x620")
        self.minsize(560, 520)
        self._center_window()

        self.pdf_path = tk.StringVar()
        self.excel_path = tk.StringVar()
        self.scale = tk.StringVar(value="100")

        self._collection: MarkupCollection | None = None
        self._registry: ReinforcementRegistry | None = None

        self._build_widgets()

    def _center_window(self) -> None:
        self.update_idletasks()
        w, h = 720, 620
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_widgets(self) -> None:
        padding = {"padx": 10, "pady": 6}

        pdf_frame = ttk.LabelFrame(self, text="PDF File")
        pdf_frame.pack(fill="x", **padding)

        ttk.Entry(pdf_frame, textvariable=self.pdf_path).pack(
            side="left", fill="x", expand=True, padx=(10, 6), pady=10
        )
        ttk.Button(pdf_frame, text="Browse…", command=self._browse_pdf).pack(
            side="right", padx=(0, 10), pady=10
        )

        excel_frame = ttk.LabelFrame(self, text="Reinforcement Spreadsheet")
        excel_frame.pack(fill="x", **padding)

        ttk.Entry(excel_frame, textvariable=self.excel_path).pack(
            side="left", fill="x", expand=True, padx=(10, 6), pady=10
        )
        ttk.Button(excel_frame, text="Browse…", command=self._browse_excel).pack(
            side="right", padx=(0, 10), pady=10
        )

        scale_frame = ttk.LabelFrame(self, text="Drawing Scale")
        scale_frame.pack(fill="x", **padding)

        ttk.Label(scale_frame, text="Scale (e.g. 100 or 1:100 for 1:100):").pack(
            anchor="w", padx=10, pady=(10, 4)
        )
        ttk.Entry(scale_frame, textvariable=self.scale, width=20).pack(
            anchor="w", padx=10, pady=(0, 10)
        )

        ttk.Button(self, text="Extract Markups", command=self._run_extraction).pack(
            **padding
        )

        ttk.Button(
            self,
            text="Add Vertical Bars (Interior)",
            command=self._run_vertical_bars,
        ).pack(**padding)

        output_frame = ttk.LabelFrame(self, text="Summary")
        output_frame.pack(fill="both", expand=True, **padding)

        self.output = scrolledtext.ScrolledText(
            output_frame, wrap="word", font=("Consolas", 10)
        )
        self.output.pack(fill="both", expand=True, padx=10, pady=10)

    def _browse_pdf(self) -> None:
        path = filedialog.askopenfilename(
            title="Select PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if path:
            self.pdf_path.set(path)

    def _browse_excel(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Spreadsheet",
            filetypes=[
                ("Excel files", "*.xlsx *.xlsm"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.excel_path.set(path)

    def _run_extraction(self) -> None:
        pdf_path = self.pdf_path.get().strip()
        if not pdf_path:
            messagebox.showwarning("Missing file", "Please choose a PDF file.")
            return

        try:
            scale = parse_scale(self.scale.get())
        except ValueError as e:
            messagebox.showwarning("Invalid scale", str(e))
            return

        excel_path = self.excel_path.get().strip()
        registry = None

        if excel_path:
            try:
                registry = build_registry(excel_path)
            except Exception as e:
                messagebox.showerror("Error", f"Could not read spreadsheet:\n{e}")
                return

        try:
            doc = open_pdf(pdf_path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open PDF:\n{e}")
            return

        try:
            page_size = detect_page_size(doc)
            markups = extract_markups(doc, source_path=pdf_path)
            self._collection = markups
            self._registry = registry
            summary = build_summary(
                markups,
                page_size=page_size,
                scale=scale,
                registry=registry,
            )
            validation_message = (
                get_validation_warning_message(markups, registry)
                if registry is not None
                else None
            )
        finally:
            doc.close()

        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, summary)

        if validation_message:
            messagebox.showwarning("Validation Warning", validation_message)

    def _run_vertical_bars(self) -> None:
        pdf_path = self.pdf_path.get().strip()
        if not pdf_path:
            messagebox.showwarning("Missing file", "Please choose a PDF file.")
            return

        if self._collection is None:
            messagebox.showwarning(
                "Not ready",
                "Run Extract Markups first to load column positions.",
            )
            return

        if self._registry is None:
            messagebox.showwarning(
                "Missing spreadsheet",
                "Please choose a reinforcement spreadsheet and extract first.",
            )
            return

        try:
            scale = parse_scale(self.scale.get())
        except ValueError as e:
            messagebox.showwarning("Invalid scale", str(e))
            return

        output_path = default_vertical_bars_output_path(pdf_path)
        try:
            interior, edge_corner, warnings = apply_vertical_bars(
                pdf_path,
                output_path,
                self._collection,
                self._registry,
                scale,
            )
        except Exception as e:
            messagebox.showerror("Error", f"Could not write vertical bars:\n{e}")
            return

        lines = [
            f"Added {interior} interior vertical bar(s).",
            f"Added {edge_corner} Edge Along X / Corner vertical bar(s).",
            f"Saved to:\n{output_path}",
        ]
        if warnings:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(warnings)
        messagebox.showinfo("Vertical Bars", "\n".join(lines))


def run_ui() -> None:
    app = ExtractorApp()
    app.mainloop()
