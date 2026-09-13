"""
SpectraSoft — CSV Override Loader
===================================
Reads sequence_data.csv and returns pre-stored ADC values for a given
ST Number.  Used in Demo Mode: hardware still executes the full burn
sequence, but the results returned to the GUI are the known-good CSV
values for the selected sample — not live ADC readings.

CSV format (from Major-Project):
    Row 1:  ST No. ->,  ABCD,  DEFG,  DEFAULT, DEFAULT, DEFAULT, ...
    Row 2:  Sequence ->, , ,   Seq1,   Seq2,    Seq3,   Seq1, ...
    Row 3+: <element>, <value>, ...

The function load_st_values() returns a flat dict:
    { element_display_name: adc_value (int), ... }
combining all three sequences for the given ST Number.
"""

import csv
import os
from typing import Dict, Optional

# Path relative to the project root (same folder as main.py)
CSV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "sequence_data.csv")


def list_st_numbers(csv_path: str = CSV_FILE):
    """
    Return a list of unique ST Numbers found in the CSV header.
    Ignores empty/blank ST entries (columns used for element labels etc.).
    """
    if not os.path.isfile(csv_path):
        return []

    try:
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header1 = next(reader, None)   # ST No. -> row
            if header1 is None or len(header1) < 2:
                return []

            seen = set()
            result = []
            for cell in header1[1:]:
                st = cell.strip()
                if st and st not in seen:
                    seen.add(st)
                    result.append(st)
            return result
    except Exception:
        return []


def load_st_values(st_number: str, csv_path: str = CSV_FILE) -> Dict[str, int]:
    """
    Load all ADC values for the given ST Number from sequence_data.csv.

    Combines Seq1 + Seq2 + Seq3 columns for that ST into one flat dict:
        { "C": 1162, "Si": 1395, ..., "Ele12": 1432, ... }

    If the ST Number is not found, returns an empty dict.
    Elements with no value for a given sequence are skipped.
    """
    if not os.path.isfile(csv_path):
        print(f"  [csv_override] CSV not found: {csv_path}")
        return {}

    try:
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header1 = next(reader, None)  # ST No. -> row
            header2 = next(reader, None)  # Sequence -> row

            if header1 is None or header2 is None:
                return {}

            # Find column indices for this ST Number (may be Seq1/Seq2/Seq3)
            target_cols = []
            for col_idx in range(1, len(header1)):
                st_cell = header1[col_idx].strip() if col_idx < len(header1) else ""
                if st_cell == st_number:
                    target_cols.append(col_idx)

            if not target_cols:
                print(f"  [csv_override] ST '{st_number}' not found in CSV.")
                return {}

            # Read data rows
            results = {}
            for row in reader:
                if not row:
                    continue
                ele_name = row[0].strip()
                if not ele_name:
                    continue

                for col_idx in target_cols:
                    if col_idx < len(row):
                        cell = row[col_idx].strip()
                        if cell:
                            try:
                                results[ele_name] = float(cell)
                                break   # Use first non-empty sequence value found
                            except ValueError:
                                pass    # Skip non-numeric cells

            print(f"  [csv_override] Loaded {len(results)} elements for ST '{st_number}'")
            return results

    except Exception as e:
        print(f"  [csv_override] Error reading CSV: {e}")
        return {}
