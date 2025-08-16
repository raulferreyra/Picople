# src/picople/app/main.py
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication
from picople.app.main_window import MainWindow


def main():
    QCoreApplication.setOrganizationName("Picople")
    QCoreApplication.setOrganizationDomain("picople.local")
    QCoreApplication.setApplicationName("Picople")

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
