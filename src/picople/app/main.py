import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import QCoreApplication

from picople.app.main_window import MainWindow
from picople.core.fonts import load_orgon_and_set_default
from picople.core.resources import asset_path


def main():
    QCoreApplication.setOrganizationName("Picople")
    QCoreApplication.setOrganizationDomain("picople.local")
    QCoreApplication.setApplicationName("Picople")

    app = QApplication(sys.argv)

    load_orgon_and_set_default(point_size=13)

    try:
        with asset_path("favicon", "favicon.ico") as iconp:
            if iconp.exists():
                app.setWindowIcon(QIcon(str(iconp)))
    except Exception:
        pass

    win = MainWindow()

    try:
        with asset_path("favicon", "favicon.ico") as iconp:
            if iconp.exists():
                win.setWindowIcon(QIcon(str(iconp)))
    except Exception:
        pass

    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
