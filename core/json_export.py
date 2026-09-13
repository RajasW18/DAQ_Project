"""
SpectraSoft — JSON Export Utility
===================================
After saving in the GUI, these functions write the updated data back to
the corresponding JSON files in import_data/ so they stay in sync with
the database and can be audited independently.

Files written:
  import_data/master_elements.json   ← Master Elements page
  import_data/source_codes.json      ← Source Codes page
  import_data/attenuator.json        ← Page 2: Attenuator Settings
  import_data/page_01_source.json    ← Page 1: Analytical Condition
  import_data/page_03_channel.json   ← Page 3: Element / Channel Info
  import_data/page_04_drift.json     ← Page 4: Drift Correction
  import_data/page_05_wc.json        ← Page 5: Working Curve
  import_data/page_06_matrix.json    ← Page 6: Matrix Correction
  import_data/page_07_master.json    ← Page 7: Master Correction
  import_data/page_08_display.json   ← Page 8: Display Order
  import_data/page_09_purity.json    ← Page 9: Purity
"""

import json
import os

# Root of the project (same folder as main.py)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IMPORT_DIR   = os.path.join(_PROJECT_ROOT, "import_data")


def _write(filename: str, data: dict):
    """Write data to import_data/<filename> as pretty-printed JSON."""
    os.makedirs(_IMPORT_DIR, exist_ok=True)
    path = os.path.join(_IMPORT_DIR, filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  [json_export] Written → {path}")
    except Exception as e:
        print(f"  [json_export] Failed to write {filename}: {e}")


# ---------------------------------------------------------------------------
# Settings pages
# ---------------------------------------------------------------------------

def export_master_elements(rows: list):
    """Write master elements to import_data/master_elements.json."""
    _write("master_elements.json", {"master_elements": rows})


def export_source_codes(rows: list):
    """Write source codes to import_data/source_codes.json."""
    _write("source_codes.json", {"source_codes": rows})


# ---------------------------------------------------------------------------
# Analytical Group pages (Page 1–9)
# ---------------------------------------------------------------------------

def export_page01_source(data: dict):
    """Write Page 1 (Analytical Condition) to import_data/page_01_source.json."""
    _write("page_01_source.json", data)


def export_attenuator(rows: list):
    """Write Page 2 (Attenuator) to import_data/attenuator.json."""
    _write("attenuator.json", {"attenuator": rows})


def export_page03_channel(data):
    """Write Page 3 (Channel/Element Info) to import_data/page_03_channel.json.
    data may be a list (channel rows) or a dict."""
    if isinstance(data, list):
        payload = {"channels": data}
    else:
        payload = data
    _write("page_03_channel.json", payload)


def export_page04_drift(data: dict):
    """Write Page 4 (Drift Correction) to import_data/page_04_drift.json."""
    _write("page_04_drift.json", data)


def export_page05_wc(data: dict):
    """Write Page 5 (Working Curve) to import_data/page_05_wc.json."""
    _write("page_05_wc.json", data)


def export_page06_matrix(data: dict):
    """Write Page 6 (Matrix Correction) to import_data/page_06_matrix.json."""
    _write("page_06_matrix.json", data)


def export_page07_master(data: dict):
    """Write Page 7 (Master Correction) to import_data/page_07_master.json."""
    _write("page_07_master.json", data)


def export_page08_display(data: dict):
    """Write Page 8 (Display Order) to import_data/page_08_display.json."""
    _write("page_08_display.json", data)


def export_page09_purity(data: dict):
    """Write Page 9 (Purity) to import_data/page_09_purity.json."""
    _write("page_09_purity.json", data)
