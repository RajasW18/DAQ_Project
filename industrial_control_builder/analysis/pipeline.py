"""
Linkable Mathematical Pipeline
Enables dynamic chaining of filters, regressions, calibrations, and numerical methods.
"""

from typing import List, Dict, Any, Callable
from .math_blocks import MathBlocks

class AnalysisPipeline:
    """A modular computational pipeline composed of linkable transformation blocks."""

    def __init__(self, name: str = "Sensor Data Pipeline"):
        self.name = name
        self.steps: List[Dict[str, Any]] = []

    def add_filter_median(self, window_size: int = 5) -> "AnalysisPipeline":
        self.steps.append({
            "type": "FILTER_MEDIAN",
            "params": {"window_size": window_size}
        })
        return self

    def add_filter_moving_average(self, window_size: int = 5) -> "AnalysisPipeline":
        self.steps.append({
            "type": "FILTER_MOVING_AVG",
            "params": {"window_size": window_size}
        })
        return self

    def add_calibration_scale(self, gain: float, offset: float = 0.0) -> "AnalysisPipeline":
        """Converts raw ADC (0-1023) to physical units: physical = raw * gain + offset"""
        self.steps.append({
            "type": "CALIBRATION",
            "params": {"gain": gain, "offset": offset}
        })
        return self

    def add_statistics(self) -> "AnalysisPipeline":
        self.steps.append({"type": "STATISTICS", "params": {}})
        return self

    def add_linear_regression(self) -> "AnalysisPipeline":
        self.steps.append({"type": "LINEAR_REGRESSION", "params": {}})
        return self

    def add_polynomial_regression(self) -> "AnalysisPipeline":
        self.steps.append({"type": "POLY_REGRESSION", "params": {}})
        return self

    def add_numerical_derivative(self) -> "AnalysisPipeline":
        self.steps.append({"type": "DERIVATIVE", "params": {}})
        return self

    def add_numerical_integral(self) -> "AnalysisPipeline":
        self.steps.append({"type": "INTEGRAL", "params": {}})
        return self

    def add_peak_detection(self, threshold: float = 0.5) -> "AnalysisPipeline":
        self.steps.append({"type": "PEAK_DETECTION", "params": {"threshold": threshold}})
        return self

    def execute(self, y_data: List[float], x_data: List[float] = None) -> Dict[str, Any]:
        """Executes all linked computational steps sequentially."""
        if not y_data:
            return {"error": "Empty dataset"}

        if x_data is None or len(x_data) != len(y_data):
            x_data = [float(i) for i in range(len(y_data))]

        current_y = list(y_data)
        current_x = list(x_data)
        results: Dict[str, Any] = {
            "pipeline_name": self.name,
            "input_count": len(y_data),
            "step_outputs": {}
        }

        for idx, step in enumerate(self.steps):
            stype = step["type"]
            params = step.get("params", {})
            step_key = f"step_{idx+1}_{stype.lower()}"

            if stype == "FILTER_MEDIAN":
                current_y = MathBlocks.median_filter(current_y, params.get("window_size", 5))
                results["step_outputs"][step_key] = {"data_preview": current_y[:8]}

            elif stype == "FILTER_MOVING_AVG":
                current_y = MathBlocks.moving_average_filter(current_y, params.get("window_size", 5))
                results["step_outputs"][step_key] = {"data_preview": current_y[:8]}

            elif stype == "CALIBRATION":
                gain = params.get("gain", 1.0)
                offset = params.get("offset", 0.0)
                current_y = [val * gain + offset for val in current_y]
                results["step_outputs"][step_key] = {"calibrated_preview": current_y[:8], "gain": gain, "offset": offset}

            elif stype == "STATISTICS":
                stats = MathBlocks.calculate_statistics(current_y)
                results["step_outputs"][step_key] = stats

            elif stype == "LINEAR_REGRESSION":
                reg = MathBlocks.linear_regression(current_x, current_y)
                results["step_outputs"][step_key] = reg

            elif stype == "POLY_REGRESSION":
                reg = MathBlocks.polynomial_regression_2nd(current_x, current_y)
                results["step_outputs"][step_key] = reg

            elif stype == "DERIVATIVE":
                dydx = MathBlocks.numerical_derivative(current_x, current_y)
                results["step_outputs"][step_key] = {"dy_dx_preview": dydx[:8]}

            elif stype == "INTEGRAL":
                area = MathBlocks.numerical_integral_trapezoidal(current_x, current_y)
                results["step_outputs"][step_key] = {"accumulated_integral": area}

            elif stype == "PEAK_DETECTION":
                peaks = MathBlocks.find_peaks(current_y, params.get("threshold", 0.5))
                results["step_outputs"][step_key] = {"detected_peaks": peaks, "peak_count": len(peaks)}

        results["final_y"] = current_y
        return results
