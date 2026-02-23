"""Entry point for the PDF Ballooner application."""
import sys

from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PDF Ballooner")
    app.setOrganizationName("PDFBallooner")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
