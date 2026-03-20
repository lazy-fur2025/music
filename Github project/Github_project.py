import sys
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QLabel,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor


class ModernWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("毛玻璃窗口")
        self.resize(520, 420)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(255, 255, 255, 150))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)

        self.drag_position = QPoint()

        self.bg_index = 0
        self.bg_colors = [
            "rgba(40, 40, 40, 200)",
            "rgba(20, 40, 80, 200)",
            "rgba(80, 50, 30, 200)",
            "rgba(60, 30, 80, 200)",
            "rgba(0, 60, 80, 200)",
        ]

        self.setStyleSheet(f"""
            QWidget {{
                background: {self.bg_colors[0]};
                border-radius: 15px;
                color: white;
            }}
        """)

        self.title_label = QLabel("毛玻璃窗口", self)
        self.title_label.move(50, 15)
        self.title_label.setStyleSheet(
            "background: none; color: white; font-size: 14px;"
        )

        self.close_btn = QPushButton("", self)
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.move(480, 12)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 80, 80, 200);
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background: rgba(255, 60, 60, 230); }
        """)
        self.close_btn.clicked.connect(self.close)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.y() < 50:
            self.drag_position = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and event.y() < 50:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    demo = ModernWindow()
    demo.show()
    sys.exit(app.exec())
