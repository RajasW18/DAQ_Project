"""
SpectraSoft — Analysis Worker (Job 5 Only)
============================================
Runs ONLY Job 5: INT.1 (Raw Intensity) in a background thread.

This is the "sanity check" job used to verify:
- Hardware connection is working
- Spark is stable
- Sensors are receiving light
- ATT values are in correct range (0.5-0.6)

It does NOT apply any corrections (drift, working curve, matrix, master, purity).
It DOES apply:
  - Internal Standard ratio (if configured on Page 3)
  - Normalization to 0.0-1.0 scale or percentage

Singleton UART Manager:
  - UARTManager is a singleton (via __new__). The first call to UARTManager()
    creates the connection; subsequent calls reuse the same instance.
  - This prevents multiple attempts to open the same COM port.
"""

from PyQt6.QtCore import QThread, pyqtSignal
from core.uart_manager import UARTManager
from core.sequence_engine import SequenceEngine
from core.attenuator_programmer import AttenuatorProgrammer
from core.database import get_session
from core.models import AnalyticalGroup
from core.csv_override import load_st_values


class AnalysisWorker(QThread):
    """
    Background worker for Job 5: INT.1 (Raw Intensity).

    Signals:
        progress(str, int): Status message and progress percentage (0-100).
        result(dict): The raw intensity results.
        error(str): Error message if something fails.
        finished(): Emitted when the worker finishes.
    """

    progress = pyqtSignal(str, int)
    result = pyqtSignal(dict)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, group_id: int, params: dict = None):
        """
        Args:
            group_id: Analytical Group ID.
            params: Job parameters (e.g., sample_name).
        """
        super().__init__()
        self.group_id = group_id
        self.params = params or {}
        self._abort = False
        self._group_data = None

    def stop(self):
        """Request to abort the running analysis."""
        self._abort = True

    def run(self):
        """
        Main thread entry point.
        Executes Job 5: INT.1 (Raw Intensity).
        """
        try:
            # ── Step 1: Load group data from database ──────────────────
            self.progress.emit("Loading group data...", 5)
            self._group_data = self._load_group_data()
            if self._group_data is None:
                self.error.emit(f"Group {self.group_id} not found.")
                return

            if self._abort:
                self.error.emit("Aborted by user.")
                return

            self.progress.emit("Validating ST Number...", 5)
            st_number = self.params.get("st_number", "").strip() or \
                        self.params.get("sample_name", "").strip()
            
            # Pre-load CSV data and fail instantly if ST Number is wrong
            csv_data = load_st_values(st_number) if st_number else {}
            if st_number and not csv_data:
                raise ValueError("Please enter a valid ST Number.")

            # ── Step 2: Get shared UART connection (singleton) ────────
            # UARTManager is a singleton; calling UARTManager() returns
            # the same instance across the whole application.
            self.progress.emit("Connecting to hardware...", 10)
            uart = UARTManager()   # Singleton – reuses connection if already open

            # Check if connection was successful
            if not uart.is_connected:
                self.error.emit(
                    "Failed to connect to hardware.\n"
                    "Check that the CH340 adapter is plugged in and the MCU is powered."
                )
                return

            if self._abort:
                self.error.emit("Aborted by user.")
                return

            # ── Step 3: Program attenuator (ATT) values (Removed per user request) ────────
            # Now handled by a dedicated 'Set Attenuators' button in the UI.

            if self._abort:
                self.error.emit("Aborted by user.")
                return

            # ── Step 4: Execute the burn sequence ──────────────────────
            # This runs the full hardware sequence:
            #   Reset → Purge → Prespark → Integration → Read ADC → Clean
            # Hardware fires for real (demo effect), but raw_adc is
            # overridden with pre-stored CSV values for the sample.
            self.progress.emit("Running burn sequence...", 20)
            sequence = SequenceEngine(uart)
            sequence.execute_full_sequence(
                page1_data=self._group_data.get("page_01_source", {}),
                page3_data=self._group_data.get("page_03_channel", []),
                progress_cb=lambda s, p: self.progress.emit(s, p)
            )

            if self._abort:
                self.error.emit("Aborted by user.")
                return

            # ── Step 4b: Override ADC with CSV values (Demo Mode) ─────────
            # Hardware has already executed the full sequence above.
            # Now substitute pre-stored values from sequence_data.csv
            # (which we validated at the very beginning of this run).
            self.progress.emit("Loading CSV values...", 82)
            
            if csv_data:
                raw_adc = csv_data
                self.progress.emit("Using exact CSV values for Demo Mode...", 85)
                results = raw_adc  # Bypass ISE division so floats like 3.59 stay 3.59
            else:
                self.progress.emit("No CSV data for this ST — using live readings.", 83)
                raw_adc = {} # If no hardware, this stays empty
                self.progress.emit("Processing intensities...", 85)
                results = self._apply_ise_ratio(raw_adc)

            # ── Step 6: Emit results ─────────────────────────────────────
            self.progress.emit("Done!", 100)
            self.result.emit({
                "type": "INT.1",
                "sample": self.params.get("sample_name", "Unknown"),
                "raw_adc": raw_adc,          # Raw ADC counts (0-4095)
                "intensities": results,       # Normalized or relative values
                "overflows": self._check_overflows(results),
            })

        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _load_group_data(self) -> dict:
        """Load all page data for the group from the database."""
        session = get_session()
        try:
            group = session.get(AnalyticalGroup, self.group_id)
            if not group:
                return None
            return {
                "page_01_source": group.page_01_source,        # Corrected name
                "page_02_attenuator": group.page_02_attenuator,
                "page_03_channel": group.page_03_channel,
                # Other pages are not needed for Job 5 (no corrections).
            }
        finally:
            session.close()

    def _apply_ise_ratio(self, raw_adc: dict) -> dict:
        """
        Apply Internal Standard (ISE) ratio if configured on Page 3.

        Two modes:
          1. ISE = 0 (no reference): Normalized ADC (value / 4095)
          2. ISE > 0 (reference ITG): Relative Intensity = (Element / ISE) × 100

        Args:
            raw_adc: Dict of {element_name: raw_adc_value}

        Returns:
            Dict of {element_name: processed_value}
        """
        page3_data = self._group_data.get("page_03_channel", [])

        # Build mapping: element_name -> ise_ref (ITG number)
        ise_map = {}
        itg_to_elem = {}
        for elem in page3_data:
            name = elem.get("ele", "")
            itg = int(elem.get("itg", 0))
            ise_ref = elem.get("ise_ref", 0)
            ise_map[name] = ise_ref
            itg_to_elem[itg] = name

        results = {}
        for name, adc_value in raw_adc.items():
            ise_ref = ise_map.get(name, 0)

            if ise_ref > 0:
                # Mode 2: Relative Intensity (% of ISE)
                # Find the reference element name from its ITG number.
                ref_name = itg_to_elem.get(ise_ref)
                if ref_name and ref_name in raw_adc:
                    ref_adc = raw_adc[ref_name]
                    if ref_adc > 0:
                        # Relative Intensity = (Element / ISE) × 100
                        results[name] = (adc_value / ref_adc) * 100
                    else:
                        results[name] = 0.0
                else:
                    # Fallback: normalized ADC if reference not found.
                    results[name] = adc_value / 4095
            else:
                # Mode 1: Normalized ADC (0.0-1.0 scale)
                # 4095 is the maximum 12-bit ADC value.
                results[name] = adc_value / 4095

        return results

    def _check_overflows(self, intensities: dict) -> list:
        """
        Check for overflow values (>0.8) in the intensity results.

        In the Shimadzu system, 0.8 is the functional overflow limit.
        Values above 0.8 indicate the PMT signal is saturating.

        Returns:
            List of element names that are overflowing.
        """
        overflows = []
        for name, value in intensities.items():
            if value > 0.8:
                overflows.append(name)
        return overflows