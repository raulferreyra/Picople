from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication

from picople.app.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Picople")

    # Tema por defecto: oscuro (se puede persistir con QSettings en un hito próximo)
    window = MainWindow(start_dark=True)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
