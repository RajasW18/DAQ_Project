# SpectraSoft System Updates

This document outlines the recent modifications made to the SpectraSoft application to address display sizing, data formatting, and High Voltage (HV) channel addressing issues.

## 1. CSV Data Storage Organization by Channel

**What:** 
The mock data storage format in `sequence_data.csv` was restructured to use the hardware channel number (ITG number) as the primary index rather than the element name. The CSV reader and exporter were updated to handle this new layout.

**Where:**
- `sequence_data.csv`: Added `Channel No` as the primary key column (first column).
- `core/csv_override.py`: Refactored `load_st_values()` and `list_st_numbers()` to natively parse the new channel-based format while gracefully supporting the legacy element-based format.
- `ui/analysis/analysis_run_job5.py`: Updated the `_on_export` CSV writing routine to export data strictly ordered and keyed by `Channel No`.

**Why:**
Relying on element names as primary identifiers can cause issues if element names change or if multiple channels refer to variations of the same element. Re-orienting the logic around physical channel numbers tightly aligns the software's data structures with the physical architecture of the hardware.

## 2. High Voltage (HV) HEX Address System

**What:** 
Implemented a dedicated High Voltage controller module to process UART commands properly with exact hexadecimal formatting.

**Where:**
- `core/hv_controller.py` **[NEW]**: Created a robust controller dedicated to sending proper `O,A,<hex_addr>` commands over UART for HV channels.
- `core/sequence_engine.py` & `core/attenuator_programmer.py`: Added explicit inline documentation defending the Python format `{:02X}` syntax.
- *Note on UI Hook:* The integration hook inside `ui/main_window.py` (which connected the UI's HV toggle button to this controller) was previously implemented but appears to have been recently reverted in your editor, reverting it back to a software simulation toggle.

**Why:**
Channels 10–15 mathematically map to hex addresses `09–0E`. There was an issue where hex values `0A` through `0E` (containing characters A-F) could be mistakenly identified as invalid if processed by decimal-only validators. The new controller strictly isolates and handles these values properly as strings.

## 3. Display Form & Frame Resizability

**What:**
Modified the application's root window to allow the user to resize and maximize the desktop application interface.

**Where:**
- `ui/main_window.py` *(Note: This change appears to have been recently reverted back to `setFixedSize(1100, 680)` in your editor)*.

**Why:**
The application interface was hardcoded using `self.setFixedSize()`, preventing any manual adjustment. Migrating to `self.setMinimumSize()` allows the inner layouts to dynamically stretch/shrink natively using Qt layout properties, granting better accessibility across different monitor resolutions.
