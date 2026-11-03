"""
Mathematical & Algorithmic Blocks for Industrial Data Analysis
Includes: Statistical profiling, noise filtering, linear/poly regression,
numerical calculus (integration/differentiation), and peak detection.
"""

import math
from typing import List, Dict, Any, Tuple, Optional

class MathBlocks:
    """Library of pure linkable mathematical and data analysis algorithms."""

    # ─────────────────────────────────────────────────────────────────────────
    # 1. STATISTICAL ANALYSIS
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def calculate_statistics(data: List[float]) -> Dict[str, float]:
        """Calculates central tendency, spread, and distribution shape."""
        if not data:
            return {"count": 0, "mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}

        n = len(data)
        mean_val = sum(data) / n
        variance = sum((x - mean_val) ** 2 for x in data) / (n - 1 if n > 1 else 1)
        std_dev = math.sqrt(variance)

        sorted_data = sorted(data)
        median_val = sorted_data[n // 2] if n % 2 != 0 else (sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2.0

        return {
            "count": n,
            "mean": round(mean_val, 4),
            "median": round(median_val, 4),
            "std": round(std_dev, 4),
            "variance": round(variance, 4),
            "min": round(min(data), 4),
            "max": round(max(data), 4),
            "range": round(max(data) - min(data), 4)
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 2. FILTERING & SIGNAL SMOOTHING
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def moving_average_filter(data: List[float], window_size: int = 5) -> List[float]:
        """Applies a moving average smoothing filter with edge padding."""
        if len(data) < window_size or window_size <= 1:
            return list(data)

        filtered = []
        half = window_size // 2
        for i in range(len(data)):
            start_idx = max(0, i - half)
            end_idx = min(len(data), i + half + 1)
            window = data[start_idx:end_idx]
            filtered.append(sum(window) / len(window))
        return filtered

    @staticmethod
    def median_filter(data: List[float], window_size: int = 5) -> List[float]:
        """Applies a median filter to strip impulse/spike noise from sensor readings."""
        if len(data) < window_size or window_size <= 1:
            return list(data)

        filtered = []
        half = window_size // 2
        for i in range(len(data)):
            start_idx = max(0, i - half)
            end_idx = min(len(data), i + half + 1)
            window = sorted(data[start_idx:end_idx])
            filtered.append(window[len(window) // 2])
        return filtered

    @staticmethod
    def exponential_smoothing(data: List[float], alpha: float = 0.25) -> List[float]:
        """Applies single exponential smoothing (EMA) for real-time sensor streams."""
        if not data:
            return []
        smoothed = [data[0]]
        for val in data[1:]:
            s = alpha * val + (1.0 - alpha) * smoothed[-1]
            smoothed.append(s)
        return smoothed

    # ─────────────────────────────────────────────────────────────────────────
    # 3. REGRESSION & CURVE FITTING
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def linear_regression(x: List[float], y: List[float]) -> Dict[str, Any]:
        """
        Fits y = slope * x + intercept.
        Returns: slope, intercept, R-squared (R2), and residuals.
        """
        n = min(len(x), len(y))
        if n < 2:
            return {"slope": 0.0, "intercept": 0.0, "r_squared": 0.0, "error": "Insufficient points"}

        x_slice = x[:n]
        y_slice = y[:n]

        x_bar = sum(x_slice) / n
        y_bar = sum(y_slice) / n

        ss_xx = sum((xi - x_bar) ** 2 for xi in x_slice)
        ss_yy = sum((yi - y_bar) ** 2 for yi in y_slice)
        ss_xy = sum((x_slice[i] - x_bar) * (y_slice[i] - y_bar) for i in range(n))

        if ss_xx == 0:
            return {"slope": 0.0, "intercept": y_bar, "r_squared": 0.0, "error": "Zero variance in X"}

        slope = ss_xy / ss_xx
        intercept = y_bar - slope * x_bar

        # Compute R2
        y_pred = [slope * xi + intercept for xi in x_slice]
        ss_res = sum((y_slice[i] - y_pred[i]) ** 2 for i in range(n))
        r2 = 1.0 - (ss_res / ss_yy) if ss_yy != 0 else 1.0

        return {
            "model_type": "linear",
            "slope": round(slope, 6),
            "intercept": round(intercept, 6),
            "r_squared": round(max(0.0, min(1.0, r2)), 6),
            "equation": f"y = {round(slope, 4)}*x + {round(intercept, 4)}"
        }

    @staticmethod
    def polynomial_regression_2nd(x: List[float], y: List[float]) -> Dict[str, Any]:
        """
        Fits 2nd-order polynomial: y = a*x^2 + b*x + c using normal equations.
        """
        n = min(len(x), len(y))
        if n < 3:
            return {"error": "Need at least 3 points for quadratic fit"}

        # Construct sums for normal matrix
        s0 = n
        s1 = sum(xi for xi in x[:n])
        s2 = sum(xi**2 for xi in x[:n])
        s3 = sum(xi**3 for xi in x[:n])
        s4 = sum(xi**4 for xi in x[:n])

        t0 = sum(yi for yi in y[:n])
        t1 = sum(x[i] * y[i] for i in range(n))
        t2 = sum((x[i]**2) * y[i] for i in range(n))

        # Solve 3x3 system via Cramer's rule
        # | s4 s3 s2 |   | a |   | t2 |
        # | s3 s2 s1 | * | b | = | t1 |
        # | s2 s1 s0 |   | c |   | t0 |
        det = (s4 * (s2 * s0 - s1 * s1) -
               s3 * (s3 * s0 - s1 * s2) +
               s2 * (s3 * s1 - s2 * s2))

        if abs(det) < 1e-12:
            return {"error": "Singular matrix in polynomial fit"}

        det_a = (t2 * (s2 * s0 - s1 * s1) -
                 s3 * (t1 * s0 - s1 * t0) +
                 s2 * (t1 * s1 - s2 * t0))

        det_b = (s4 * (t1 * s0 - s1 * t0) -
                 t2 * (s3 * s0 - s1 * s2) +
                 s2 * (s3 * t0 - t1 * s2))

        det_c = (s4 * (s2 * t0 - t1 * s1) -
                 s3 * (s3 * t0 - t1 * s2) +
                 t2 * (s3 * s1 - s2 * s2))

        a = det_a / det
        b = det_b / det
        c = det_c / det

        y_bar = t0 / n
        ss_tot = sum((yi - y_bar) ** 2 for yi in y[:n])
        ss_res = sum((y[i] - (a * x[i]**2 + b * x[i] + c)) ** 2 for i in range(n))
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 1.0

        return {
            "model_type": "polynomial_quadratic",
            "a": round(a, 6),
            "b": round(b, 6),
            "c": round(c, 6),
            "r_squared": round(max(0.0, min(1.0, r2)), 6),
            "equation": f"y = {round(a, 4)}*x^2 + {round(b, 4)}*x + {round(c, 4)}"
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 4. NUMERICAL METHODS (CALCULUS & PEAKS)
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def numerical_derivative(x: List[float], y: List[float]) -> List[float]:
        """Calculates dy/dx using central differences with boundary one-sided differences."""
        n = min(len(x), len(y))
        if n < 2:
            return [0.0] * n

        dydx = []
        # Forward difference for first point
        dx0 = x[1] - x[0]
        dydx.append((y[1] - y[0]) / dx0 if dx0 != 0 else 0.0)

        # Central difference for interior points
        for i in range(1, n - 1):
            dxi = x[i + 1] - x[i - 1]
            dydx.append((y[i + 1] - y[i - 1]) / dxi if dxi != 0 else 0.0)

        # Backward difference for last point
        dxn = x[n - 1] - x[n - 2]
        dydx.append((y[n - 1] - y[n - 2]) / dxn if dxn != 0 else 0.0)
        return dydx

    @staticmethod
    def numerical_integral_trapezoidal(x: List[float], y: List[float]) -> float:
        """Computes integral of y dx via the trapezoidal rule (e.g. total volume, peak area)."""
        n = min(len(x), len(y))
        if n < 2:
            return 0.0

        total_area = 0.0
        for i in range(n - 1):
            dx = x[i + 1] - x[i]
            avg_y = (y[i] + y[i + 1]) / 2.0
            total_area += avg_y * dx
        return round(total_area, 4)

    @staticmethod
    def find_peaks(y: List[float], threshold_ratio: float = 0.5) -> List[Dict[str, Any]]:
        """Finds local maxima above threshold (useful for spectroscopy, pressure spikes)."""
        if len(y) < 3:
            return []

        max_val = max(y)
        min_val = min(y)
        cutoff = min_val + (max_val - min_val) * threshold_ratio

        peaks = []
        for i in range(1, len(y) - 1):
            if y[i] > y[i - 1] and y[i] > y[i + 1] and y[i] >= cutoff:
                peaks.append({"index": i, "value": y[i]})
        return peaks
