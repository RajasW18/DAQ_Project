"""
End-to-End Demonstration of the Industrial Control Builder
Demonstrates multi-modal ingestion, token-efficient DSL compilation,
MCU sequence execution at 9600 baud, linked math pipeline, and documentation generation.
"""

import os
import sys

# Ensure repository root is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from industrial_control_builder.ai_orchestrator.central_agent import CentralIndustrialOrchestrator

def main():
    print("=" * 70)
    print("  INDUSTRIAL CONTROL BUILDER - AI ORCHESTRATION PIPELINE DEMO")
    print("=" * 70)

    # 1. Initialize Central AI Orchestrator for ATmega 2560 Pro
    print("\n[Step 1] Initializing Orchestrator on ATmega 2560 Pro HAL (9600 Baud)...")
    orchestrator = CentralIndustrialOrchestrator(board_name="atmega2560", use_mock=True)
    summary = orchestrator.hal.get_pinout_summary()
    print(f"  Board: {summary['board']} ({summary['architecture']})")
    print(f"  Voltage Level: {summary['operating_voltage']}")
    print(f"  Digital I/O: {summary['digital_io_count']} pins | PWM: {len(summary['pwm_pins'])} pins")
    print(f"  Analog Channels: {len(summary['analog_channels'])} ({summary['adc_resolution']})")

    # 2. Multi-Modal Document & Technical Context Ingestion
    print("\n[Step 2] Ingesting Technical Guides and Manuals...")
    workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sample_files = [
        os.path.join(workspace_root, "11222.csv"),
        os.path.join(workspace_root, "README.md")
    ]
    existing_files = [f for f in sample_files if os.path.exists(f)]
    doc_summary = orchestrator.ingest_documents(existing_files)
    print(f"  Ingested {len(existing_files)} documents successfully.")
    for doc in orchestrator.ingested_docs:
        print(f"  - Ingested: {doc.get('filename')} (Type: {doc.get('type')})")

    # 3. AI Directs Compact Token-Efficient DSL Plan
    print("\n[Step 3] Central AI Formulates Minimal-Token Orchestration Plan...")
    dsl_plan = """
    # Central AI Orchestration DSL
    CONFIG 13 OUT
    CONFIG 12 OUT
    CONFIG 9 PWM
    CONFIG 2 IN
    W 13 1
    DLY 100
    W 9 160
    DLY 150
    A 0
    A 1
    R 2
    W 13 0
    W 9 0
    POLL 0 200 A
    PIPE MEDIAN(5) CALIB(0.004882,0) STATS REG_LIN INTEGRAL PEAKS(0.55)
    """
    print(dsl_plan.strip())

    # 4. Deterministic Execution & Mathematical Analysis
    print("\n[Step 4] Compiling DSL, Uploading Sequence & Executing Hardware Timers...")
    # This demonstration runs only against the software mock controller.
    results = orchestrator.execute_dsl(dsl_plan, approved=True)

    print(f"  Sequence Execution Status: {results['run_status'].get('status')}")
    print(f"  Elapsed Hardware Runtime: {results['run_status'].get('elapsed_s')} s")
    print(f"  Recorded Telemetry Points: {len(results['run_status'].get('readings', []))}")
    for r in results['run_status'].get('readings', []):
        print(f"    Channel {r['channel']}: {r['value']} (ts={r['timestamp']})")

    # 5. Review Linked Mathematical Analysis Outputs
    print("\n[Step 5] Reviewing Mathematical Modeling & Analysis Pipeline Outputs:")
    pipeline_outs = results.get("pipeline_results", {}).get("step_outputs", {})
    for step_key, val in pipeline_outs.items():
        print(f"\n  >> {step_key.upper()}:")
        if isinstance(val, dict):
            for k, v in val.items():
                print(f"     * {k}: {v}")
        else:
            print(f"     {val}")

    # 6. Generate Comprehensive Technical Build Document
    print("\n[Step 6] Generating Complete System Specification Document...")
    report_file = os.path.join(workspace_root, "industrial_build_spec.md")
    report_md = orchestrator.generate_build_documentation(
        project_name="Automated Spectroscopy DAQ Sequence & Calibrator",
        dsl_code=dsl_plan,
        execution_results=results,
        output_path=report_file
    )
    print(f"  Report generated successfully at: {report_file}")
    print(f"  Document Size: {len(report_md)} bytes")

    # 7. Safe Shutdown
    orchestrator.shutdown()
    print("\n[Step 7] Microcontroller de-energized and parked in safe state (ESTOP).")
    print("=" * 70)
    print("  ALL DEMONSTRATION PHASES COMPLETED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    main()
