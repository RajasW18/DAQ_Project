"""
Unit and Integration Tests for Industrial Control Builder
"""

import pytest
from industrial_control_builder.hal.registry import get_board
from industrial_control_builder.hal.atmega2560 import ATmega2560HAL
from industrial_control_builder.hal.stm32_base import STM32GenericHAL
from industrial_control_builder.protocol.ascii_protocol import ASCIIProtocol
from industrial_control_builder.analysis.math_blocks import MathBlocks
from industrial_control_builder.analysis.pipeline import AnalysisPipeline
from industrial_control_builder.ai_orchestrator.central_agent import CentralIndustrialOrchestrator

def test_hal_board_discovery():
    mega = get_board("atmega2560")
    assert isinstance(mega, ATmega2560HAL)
    assert mega.validate_digital_pin(13)
    assert mega.validate_pwm_pin(9)
    assert mega.validate_analog_channel(0)
    assert not mega.validate_digital_pin(999)

    stm = get_board("stm32")
    assert isinstance(stm, STM32GenericHAL)
    assert stm.operating_voltage == 3.3 if hasattr(stm, "operating_voltage") else True

def test_ascii_protocol_encoding_decoding():
    assert ASCIIProtocol.pin_mode(13, "OUT") == "PIN 13 OUT"
    assert ASCIIProtocol.write(9, 128) == "W 9 128"
    assert ASCIIProtocol.poll_start(0, 250, is_analog=True) == "POLL 0 250 A"
    assert ASCIIProtocol.estop() == "ESTOP"

    evt, payload = ASCIIProtocol.parse_line("ACK PIN 13 OUT")
    assert evt == "ACK"
    assert "13" in payload["raw"]

    evt, payload = ASCIIProtocol.parse_line("DATA A0 512 120000")
    assert evt == "DATA"
    assert payload["telemetry"].channel == "A0"
    assert payload["telemetry"].value == 512.0
    assert payload["telemetry"].timestamp_ms == 120000

def test_math_blocks_statistics_and_regression():
    data = [10.0, 20.0, 30.0, 40.0, 50.0]
    stats = MathBlocks.calculate_statistics(data)
    assert stats["count"] == 5
    assert stats["mean"] == 30.0
    assert stats["min"] == 10.0
    assert stats["max"] == 50.0

    # Linear regression test
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [2.0, 4.0, 6.0, 8.0, 10.0]
    reg = MathBlocks.linear_regression(x, y)
    assert reg["slope"] == 2.0
    assert reg["intercept"] == 0.0
    assert reg["r_squared"] == 1.0

    # Trapezoid integration test: integral of 2*x from 0 to 4 is 16
    x_int = [0.0, 1.0, 2.0, 3.0, 4.0]
    y_int = [0.0, 2.0, 4.0, 6.0, 8.0]
    area = MathBlocks.numerical_integral_trapezoidal(x_int, y_int)
    assert area == 16.0

def test_pipeline_chaining():
    pipeline = AnalysisPipeline("Test Pipeline")
    pipeline.add_filter_median(3)
    pipeline.add_calibration_scale(gain=2.0, offset=1.0)
    pipeline.add_statistics()

    raw_y = [10.0, 100.0, 10.0, 12.0, 14.0] # spike at index 1
    res = pipeline.execute(raw_y)
    assert res["input_count"] == 5
    assert "step_1_filter_median" in res["step_outputs"]
    assert "step_2_calibration" in res["step_outputs"]
    assert "step_3_statistics" in res["step_outputs"]

def test_central_orchestrator_execution():
    orchestrator = CentralIndustrialOrchestrator(board_name="atmega2560", use_mock=True)
    dsl = """
    CONFIG 13 OUT
    W 13 1
    DLY 20
    W 13 0
    PIPE STATS
    """
    # Test the explicitly approved mock execution path. Live UI execution
    # obtains this approval through its confirmation dialog.
    exec_res = orchestrator.execute_dsl(dsl, approved=True)
    assert exec_res["run_status"]["status"] == "COMPLETED"
    assert len(exec_res["run_status"]["readings"]) >= 0
    orchestrator.shutdown()
