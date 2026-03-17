#激活环境需要执.\env\Scripts\activate
#遇见带有空格的路径需要加引号（cd命令)
import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QColor, QPalette

class ModernWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        # 1. 窗口基础设置
        self.setWindowTitle("原生现代感窗口")
        self.resize(500, 400)
        
        # 设置深色背景主题
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: white;
                font-family: 'Microsoft YaHei';
            }
            QPushButton {
                background-color: #0078d4;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #2b88d8;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)

        # 2. 布局
        layout = QVBoxLayout(self)
        
        self.label = QLabel("正在加载丝滑动画...", self)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        self.btn = QPushButton("开启丝滑缩放动画", self)
        self.btn.clicked.connect(self.start_smooth_animation)
        layout.addWidget(self.btn, 0, Qt.AlignCenter)

    def start_smooth_animation(self):
        # 3. 丝滑动画实现：改变按钮的大小和位置
        self.ani = QPropertyAnimation(self.btn, b"geometry")
        self.ani.setDuration(600)  # 600毫秒
        
        start_rect = self.btn.geometry()
        # 目标：按钮稍微变大一点
        end_rect = QRect(start_rect.x() - 20, start_rect.y() - 5, 
                         start_rect.width() + 40, start_rect.height() + 10)
        
        self.ani.setStartValue(start_rect)
        self.ani.setEndValue(end_rect)
        
        # 关键：使用 OutQuint 曲线实现“丝滑感”
        self.ani.setEasingCurve(QEasingCurve.OutQuint)
        self.ani.start()
        self.label.setText("动画已触发！")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 创建并显示
    demo = ModernWindow()
    demo.show()
    
    sys.exit(app.exec())