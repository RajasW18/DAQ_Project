"""Launch the Industrial Control Builder as a standalone desktop application.

This entry point reuses the builder package without starting SpectraSoft or
loading its analytical-workspace UI.
"""

import sys

from PyQt6.QtWidgets import QApplication, QMainWindow

from ui.standalone_builder_page import StandaloneBuilderPage


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Industrial Control Builder")
    app.setOrganizationName("Industrial Control Builder")

    window = QMainWindow()
    window.setWindowTitle("Industrial Control Builder")
    window.setMinimumSize(960, 680)
    window.resize(1280, 900)
    window.setCentralWidget(StandaloneBuilderPage())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
