# IntegrityReoMarker

Python tool for structural engineering workflows: extract Bluebeam PDF rectangle markups (COLUMN / BOUNDARY), load column reinforcement data from Excel, match by column name, and generate marked-up PDFs with vertical reinforcement bars.

## Features

- Extract COLUMN and BOUNDARY rectangle markups from PDF annotations (PyMuPDF)
- Load reinforcement design data from Excel (Reference, dimensions, edge condition, bar lengths, etc.)
- Match PDF column comments to Excel Reference values
- Validation for duplicate names and mismatches between PDF and spreadsheet
- Add green vertical bar markups based on edge condition:
  - **Interior** — centred on column, length from `bar_length_y`
  - **Edge Along X / Corner** — from nearest slab boundary through column centre, plus 600 mm horizontal tick at boundary
- Tkinter GUI and CLI entry points
- Optional Windows executable via PyInstaller

## Requirements

- Python 3.10+
- See `requirements.txt` (`PyMuPDF`, `openpyxl`)

## Usage

### GUI

```bash
python app.py
```

1. Choose PDF and reinforcement spreadsheet
2. Enter drawing scale (e.g. `100` or `1:100`)
3. **Extract Markups**
4. **Add Vertical Bars (Interior)** — writes `{input}_vertical_bars.pdf`

### CLI

```bash
python main.py sample.pdf --scale 100
```

## Build executable (Windows)

```bash
build_exe.bat
```

Output: `dist/PDF Annotation Extractor.exe`

## Project layout

| Module | Purpose |
|--------|---------|
| `annotation_extractor.py` | PDF markup extraction |
| `excel_extractor.py` | Spreadsheet loading |
| `models.py` | Data structures |
| `geometry.py` | Scale and coordinate math |
| `vertical_bar_markup.py` | Vertical bar PDF markup |
| `summary.py` | Summary and validation |
| `ui.py` | Tkinter interface |

## Sample files

- `sample.pdf` — test COLUMN + BOUNDARY markups
- `sample_columns.xlsx` — sample reinforcement data
